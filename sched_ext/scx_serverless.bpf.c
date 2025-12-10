#include <scx/common.bpf.h>
#include "scx_serverless.h"

char _license[] SEC("license") = "GPL";

// Debug macro: only prints when DEBUG is defined
#ifdef DEBUG
#define DEBUG_PRINTK(fmt, ...) bpf_printk(fmt, ##__VA_ARGS__)
#else
#define DEBUG_PRINTK(fmt, ...) do {} while (0)
#endif

static u64 vtime_now;
UEI_DEFINE(uei);

// The DSQ ID for the shared queue. We use because the built-in DSQs cannot be
// used as priority queues.
#define SHARED_DSQ_ID 0

// Maximum amount of tasks enqueued/dispatched between kernel and user-space.
#define MAX_ENQUEUED_TASKS 4096

const volatile s32 usersched_pid;
u64 nr_user_enqueues;
u64 nr_failed_enqueues;

/* Number of tasks that are sent for argument retrieval and slice calculation in userspace.
 *
 * This number is incremented by the BPF component when a task is enabled and sent to the
 * user-space scheduler and it must be decremented by the user-space scheduler
 * when a task is consumed.
 */
volatile u64 nr_userspace_queued;

/*
 * Number of tasks that are waiting for scheduling.
 *
 * This number must be updated by the user-space scheduler to keep track if
 * there is still some scheduling work to do.
 */
volatile u64 nr_userspace_scheduled;

/*
 * The map containing tasks that are enqueued in user space from the kernel.
 *
 * This map is drained by the user space scheduler.
 */
struct {
	__uint(type, BPF_MAP_TYPE_QUEUE);
	__uint(max_entries, MAX_ENQUEUED_TASKS);
	__type(value, struct scx_serverless_enqueued_task);
} enqueued SEC(".maps");

/*
 * The map containing tasks that are dispatched to the kernel from user space.
 *
 * Drained by the kernel in serverless_dispatch().
 */
struct {
	__uint(type, BPF_MAP_TYPE_QUEUE);
	__uint(max_entries, MAX_ENQUEUED_TASKS);
	__type(value, struct scx_serverless_dispatched_task);
} dispatched SEC(".maps");

/* Map holding file descriptor to wake up userspace scheduler */
struct {
	__uint(type, BPF_MAP_TYPE_RINGBUF);
	__uint(max_entries, 1 << 20);   /* 1 MB buffer */
} wake_ringbuf SEC(".maps");

/* Per-task scheduling context (slice in nanoseconds)*/
struct task_ctx {
	u64 slice;
};

/* Map that contains task-local storage. */
struct {
	__uint(type, BPF_MAP_TYPE_TASK_STORAGE);
	__uint(map_flags, BPF_F_NO_PREALLOC);
	__type(key, int);
	__type(value, struct task_ctx);
} task_ctx_stor SEC(".maps");

/*
 * Flag used to wake-up the user-space scheduler.
 */
static volatile u32 usersched_needed;

/*
 * Set user-space scheduler wake-up flag (equivalent to an atomic release
 * operation).
 */
static void set_usersched_needed(void) {
	__sync_fetch_and_or(&usersched_needed, 1);
}

/*
 * Check and clear user-space scheduler wake-up flag (equivalent to an atomic
 * acquire operation).
 */
static bool test_and_clear_usersched_needed(void) {
	return __sync_fetch_and_and(&usersched_needed, 0) == 1;
}

static bool is_usersched_task(const struct task_struct *p) {
	return p->pid == usersched_pid;
}

static struct task_struct *usersched_task(void) {
	struct task_struct *p;

	p = bpf_task_from_pid(usersched_pid);
	/*
	 * Should never happen -- the usersched task should always be managed
	 * by sched_ext.
	 */
	if (!p)
		scx_bpf_error("Failed to find usersched task %d", usersched_pid);

	return p;
}

static void send_wake_msg(void) {
	struct wake_msg *msg;

	msg = bpf_ringbuf_reserve(&wake_ringbuf, sizeof(*msg), 0);
	if (!msg) {
		scx_bpf_error("failed to reserve ringbuf slot\n");
		return;
	}

	// This is just a dummy value for the message, if more than one message types was to be supported,
	// we could use this field to differentiate them. For the time being the value set is just useless so we microptimize it away
	// (1 assembly instruction saved :))
	// msg->value = 1;
	bpf_ringbuf_submit(msg, 0);

	DEBUG_PRINTK("%-30s wakeup sent to userspace", "[send_wake_msg]");

}

static void dispatch_user_scheduler(void) {
	struct task_struct *p;

	p = usersched_task();
	if (p) {
		scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_INF, 0);
		bpf_task_release(p);
	}

	send_wake_msg();
}

static void enqueue_task_in_userspace(struct task_struct *p) {
	struct scx_serverless_enqueued_task task = {};

	task.pid = p->pid;

	if (bpf_map_push_elem(&enqueued, &task, 0) != 0) {
		// If we fail to enqueue the task in user space, put it on the vtime DSQ and just give it DFL time slice.
		__sync_fetch_and_add(&nr_failed_enqueues, 1);
		DEBUG_PRINTK("%-30s failed to enqueue task %d in user space, putting it on the global DSQ (total failed: %llu)", "[enqueue_task_in_userspace]", p->pid, nr_failed_enqueues);
		u64 vtime = p->scx.dsq_vtime;
		// Limit the amount of budget that an idling task can accumulate to one slice.
		if (time_before(vtime, vtime_now - SCX_SLICE_DFL))
			vtime = vtime_now - SCX_SLICE_DFL;
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, SCX_SLICE_DFL, vtime, 0);
		return;
	}

	__sync_fetch_and_add(&nr_user_enqueues, 1);
	DEBUG_PRINTK("%-30s task %d enqueued in userspace (total: %llu)", "[enqueue_task_in_userspace]", p->pid, nr_user_enqueues);
	set_usersched_needed();
}

static void dequeue_tasks_from_userspace(void) {
	struct scx_serverless_dispatched_task u_task;

	bpf_repeat(MAX_ENQUEUED_TASKS) {
		struct task_struct *p;

		if (bpf_map_pop_elem(&dispatched, &u_task) != 0) {
			break;
		}
		/*
		 * The task could have exited by the time we get around to
		 * dispatching it. Treat this as a normal occurrence, and simply
		 * move onto the next iteration.
		 */
		p = bpf_task_from_pid(u_task.pid);
		if (!p) {
			DEBUG_PRINTK("%-30s failed to find task %d, skipping", "[dequeue_tasks_from_userspace]", u_task.pid);
			continue;
		}

		struct task_ctx *tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);

		u64 vtime = p->scx.dsq_vtime;
		u64 slice = tctx ? tctx->slice : SCX_SLICE_DFL;
		p->scx.slice = slice;

		// Limit the amount of budget that an idling task can accumulate to one slice.
		if (time_before(vtime, vtime_now - slice))
			vtime = vtime_now - slice;

		if (!tctx) {
			DEBUG_PRINTK("%-30s failed to get task ctx for task %d", "[dequeue_tasks_from_userspace]", p->pid);
			// Don't have a task context, use default slice, also don't create one, other paths will just use the default slice
			scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, slice, vtime, 0);
			bpf_task_release(p);
			continue;
		}

		// If the slice is zero, we use the default slice value.
		// If the slice is one, we use infinite slice.
		if (u_task.slice <= 1) {
			u_task.slice = (u_task.slice == 0) ? SCX_SLICE_DFL : SCX_SLICE_INF;
			DEBUG_PRINTK("%-30s task %d has %s slice", "[dequeue_tasks_from_userspace]", p->pid, u_task.slice == SCX_SLICE_INF ? "infinite" : "default");
		}

		tctx->slice = u_task.slice;
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, slice, vtime, 0);
		DEBUG_PRINTK("%-30s task %d uspace --> k, task_slice %llu", "[dequeue_tasks_from_userspace]", p->pid, tctx->slice);
		bpf_task_release(p);
	}
}

int create_task_ctx(struct task_struct *p) {
	// Use default slice when creating task context
	struct task_ctx tctx_init = {
		.slice = SCX_SLICE_DFL,
	};

	if (!bpf_task_storage_get(&task_ctx_stor, p, &tctx_init, BPF_LOCAL_STORAGE_GET_F_CREATE)) {
		DEBUG_PRINTK("%-30s Failed to create task ctx for %d", "[create_task_ctx]", p->pid);
		scx_bpf_error("Failed to create task ctx for %d", p->pid);
		return -1;
	}

	return 0;
}

s32 BPF_STRUCT_OPS(serverless_select_cpu, struct task_struct *p, s32 prev_cpu, u64 wake_flags) {
	// Decode wakeup flags
	// wake_flags: SCX_WAKE_*, possible values are:
	// SCX_WAKE_FORK (0x02) - Wakeup after exe
	// SCX_WAKE_TTWU (0x04) - Wakeup after fork
	// SCX_WAKE_SYNC (0x08) - Wakeup

	bool is_idle = false;
	s32 cpu = scx_bpf_select_cpu_dfl(p, prev_cpu, wake_flags, &is_idle);

	DEBUG_PRINTK("%-30s select_cpu for task %d, selected_cpu %d, prev_cpu %d, wake_flags 0x%llx", "[serverless_select_cpu]", p->pid, cpu, prev_cpu, (unsigned long long) wake_flags);

	if (is_idle) {
		// Get task context to use correct slice
		struct task_ctx *tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);

		u64 vtime = p->scx.dsq_vtime;
		u64 slice = tctx ? tctx->slice : SCX_SLICE_DFL;
		p->scx.slice = slice;

		if (!tctx) {
			DEBUG_PRINTK("%-30s failed to get task ctx for task %d", "[serverless_select_cpu]", p->pid);
			scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, SCX_SLICE_DFL, vtime, 0);
			return cpu;
		}
		// Limit the amount of budget that an idling task can accumulate to one slice.
		if (time_before(vtime, vtime_now - slice))
			vtime = vtime_now - slice;

		DEBUG_PRINTK("%-30s task %d waking up on idle CPU %d, enqueueing locally, task_slice %llu", "[serverless_select_cpu]", p->pid, cpu, slice);
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, tctx->slice, vtime, 0);
	}
	return cpu;
}

s32 BPF_STRUCT_OPS(serverless_enqueue, struct task_struct *p, u64 enq_flags) {
	DEBUG_PRINTK("%-30s enqueueing task %d, associated_cpu %d, enq_flags 0x%llx",	"[serverless_enqueue]", p->pid,	scx_bpf_task_cpu(p), (unsigned long long)enq_flags);

	if(is_usersched_task(p)) {
		scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_INF, enq_flags);
		return 0;
	}
	struct task_ctx *tctx;
	tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);

	u64 vtime = p->scx.dsq_vtime;
	u64 slice = tctx ? tctx->slice : SCX_SLICE_DFL;
	p->scx.slice = slice;

	// Limit the amount of budget that an idling task can accumulate to one slice.
	if (time_before(vtime, vtime_now - slice))
		vtime = vtime_now - slice;

	if (!tctx) {
		DEBUG_PRINTK("%-30s failed to get task ctx for task %d", "[serverless_enqueue]", p->pid);
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, SCX_SLICE_DFL, vtime_now, enq_flags);
		return 0;
	}



	scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, slice, vtime, enq_flags);
	DEBUG_PRINTK("%-30s task %d enqueued ,ran_time %llu, task_slice %llu", "[serverless_enqueue]", p->pid, vtime, tctx->slice);

	return 0;
}

int BPF_STRUCT_OPS(serverless_dispatch, s32 cpu, struct task_struct *prev) {
	if (test_and_clear_usersched_needed()) {
		dispatch_user_scheduler();
	}

	// Dequeue tasks that are sent from userspace through *dispatched* map
	dequeue_tasks_from_userspace();

	// Move tasks from the shared DSQ to the local DSQ, if any.
	int nr_queued = scx_bpf_dsq_nr_queued(SHARED_DSQ_ID);
	if(nr_queued > 0) {
		DEBUG_PRINTK("%-30s there are %d tasks in the shared DSQ", "[serverless_dispatch]", nr_queued);
		if(!scx_bpf_dsq_move_to_local(SHARED_DSQ_ID)) {
			DEBUG_PRINTK("%-30s failed to move tasks from shared DSQ to local DSQ", "[serverless_dispatch]");
		}
		else {
			DEBUG_PRINTK("%-30s moved task from shared DSQ to local DSQ", "[serverless_dispatch]");
		}
	}
	return 0;
}

/*
 * A CPU is about to change its idle state. If the CPU is going idle, ensure
 * that the user-space scheduler has a chance to run if there is any remaining
 * work to do.
 */
void BPF_STRUCT_OPS(serverless_update_idle, s32 cpu, bool idle) {
	// DEBUG_PRINTK("%-30s cpu %d %s idle", "[serverless_update_idle]", cpu, idle?"entering":"exiting");
	/*
	 * Don't do anything if we exit from and idle state, a CPU owner will
	 * be assigned in .running().
	 */
	if (!idle)
		return;
	/*
	 * A CPU is now available, notify the user-space scheduler that tasks
	 * can be dispatched, if there is at least one task waiting to be
	 * scheduled, either queued (accounted in nr_userspace_queued) or scheduled
	 * (accounted in nr_userspace_scheduled).
	 *
	 * NOTE: nr_userspace_queued is incremented by the BPF component, more exactly in
	 * enqueue(), when a task is sent to the user-space scheduler, then
	 * the scheduler drains the queued tasks (updating nr_userspace_queued) and adds
	 * them to its internal data structures / state; at this point tasks
	 * become "scheduled" and the user-space scheduler will take care of
	 * updating nr_userspace_scheduled accordingly; lastly tasks will be dispatched
	 * and the user-space scheduler will update nr_userspace_scheduled again.
	 *
	 * Checking both counters allows to determine if there is still some
	 * pending work to do for the scheduler: new tasks have been queued
	 * since last check, or there are still tasks "queued" or "scheduled"
	 * since the previous user-space scheduler run. If the counters are
	 * both zero it is pointless to wake-up the scheduler (even if a CPU
	 * becomes idle), because there is nothing to do.
	 *
	 * Keep in mind that update_idle() doesn't run concurrently with the
	 * user-space scheduler (that is single-threaded): this function is
	 * naturally serialized with the user-space scheduler code, therefore
	 * this check here is also safe from a concurrency perspective.
	 */
	if (nr_userspace_queued || nr_userspace_scheduled) {
		/*
		 * Kick the CPU to make it immediately ready to accept
		 * dispatched tasks.
		 */
		set_usersched_needed();
		scx_bpf_kick_cpu(cpu, 0);
	}
}

#ifdef DEBUG
void BPF_STRUCT_OPS(serverless_runnable, struct task_struct *p) {
	DEBUG_PRINTK("%-30s task %d runnable, ran time %llu, rem_slice %llu", "[serverless_runnable]", p->pid, p->scx.dsq_vtime, p->scx.slice);
}
#endif

void BPF_STRUCT_OPS(serverless_running, struct task_struct *p) {
	// Global vtime always progresses forward as tasks start executing. The
	// test and update can be performed concurrently from multiple CPUs and
	// thus racy. Any error should be contained and temporary. Let's just
	// live with it.
	bool cond = time_before(vtime_now, p->scx.dsq_vtime);

	if (cond) {
		vtime_now = p->scx.dsq_vtime;
	}

	DEBUG_PRINTK("%-30s task %d running, ran_time %llu, rem_slice %llu, new global vtime_now %llu, cond=%d", "[serverless_running]", p->pid, p->scx.dsq_vtime, p->scx.slice, vtime_now, cond);

}

void BPF_STRUCT_OPS(serverless_stopping, struct task_struct *p, bool runnable) {
	struct task_ctx *tctx;
	tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);
	if (!tctx) {
		DEBUG_PRINTK("%-30s failed to get task ctx for task %d, what to do now?", "[serverless_stopping]", p->pid);
		scx_bpf_error("Failed to get task ctx for %d", p->pid);
		return;
	}

	DEBUG_PRINTK("%-30s task %d stopping (runnable = %d), rem_slice %llu, task_slice %llu, weight %llu", "[serverless_stopping]", p->pid, runnable, p->scx.slice, tctx->slice, p->scx.weight);

	p->scx.dsq_vtime += (tctx->slice - p->scx.slice) * 100 / p->scx.weight;
}

#ifdef DEBUG
void BPF_STRUCT_OPS(serverless_quiescent, struct task_struct *p, u64 deq_flags) {
	DEBUG_PRINTK("%-30s task %d quiescent, deq_flags 0x%llx", "[serverless_quiescent]", p->pid, (unsigned long long) deq_flags);
}

void BPF_STRUCT_OPS(serverless_tick, struct task_struct *p) {
	u64 slice_ms = p->scx.slice / 1000000ULL;
	DEBUG_PRINTK("%-30s sched tick, running task %d, rem_slice %llu (%llu ms)",
		"[serverless_tick]", p->pid, p->scx.slice, slice_ms);
}
#endif

int BPF_STRUCT_OPS(serverless_init_task, struct task_struct *p, struct scx_init_task_args *args) {
	DEBUG_PRINTK("%-30s init task %d", "[serverless_init_task]", p->pid);
	p->scx.dsq_vtime = vtime_now;

	return 0;
}

int BPF_STRUCT_OPS(serverless_enable, struct task_struct *p) {
	DEBUG_PRINTK("%-30s enabling task %d", "[serverless_enable]", p->pid);
	p->scx.dsq_vtime = vtime_now;

	if (create_task_ctx(p) < 0) {
		return -ENOMEM;
	}

	if(!is_usersched_task(p)) {
		enqueue_task_in_userspace(p);
	}

	return 0;
}

int BPF_STRUCT_OPS(serverless_disable, struct task_struct *p) {
	DEBUG_PRINTK("%-30s disabling task %d", "[serverless_disable]", p->pid);
	bpf_task_storage_delete(&task_ctx_stor, p);
	return 0;
}

s32 BPF_STRUCT_OPS_SLEEPABLE(serverless_init) {
#ifdef DEBUG
	bpf_printk("%-24s Initializing scheduler (DEBUG mode)", "[serverless_init]");
#else
	bpf_printk("%-24s Initializing scheduler (RELEASE mode)", "[serverless_init]");
#endif

	if (usersched_pid <= 0) {
		scx_bpf_error("User scheduler pid uninitialized (%d)", usersched_pid);
		return -EINVAL;
	}

	return scx_bpf_create_dsq(SHARED_DSQ_ID, -1);
}

void BPF_STRUCT_OPS(serverless_exit, struct scx_exit_info *ei) {
	scx_bpf_destroy_dsq(SHARED_DSQ_ID);
	bpf_printk("%-24s Exiting scheduler", "[serverless_exit]");
	UEI_RECORD(uei, ei);
}


SCX_OPS_DEFINE(serverless_ops,
		   .select_cpu		= (void *)serverless_select_cpu,
		   .enqueue			= (void *)serverless_enqueue,
		   .dispatch		= (void *)serverless_dispatch,
		   .running			= (void *)serverless_running,
#ifdef DEBUG
		   .runnable		= (void *)serverless_runnable,
		   .quiescent		= (void *)serverless_quiescent,
		   .tick			= (void *)serverless_tick,
#endif
		   .stopping		= (void *)serverless_stopping,
		   .update_idle		= (void *)serverless_update_idle,
		   .init_task		= (void *)serverless_init_task,
		   .enable			= (void *)serverless_enable,
		   .disable			= (void *)serverless_disable,
		   .init			= (void *)serverless_init,
		   .exit			= (void *)serverless_exit,
		   .flags			= SCX_OPS_ENQ_LAST | SCX_OPS_KEEP_BUILTIN_IDLE | SCX_OPS_SWITCH_PARTIAL,
		   .name			= "serverless");
