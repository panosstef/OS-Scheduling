#include <scx/common.bpf.h>
#include "scx_serverless.h"

char _license[] SEC("license") = "GPL";

static u64 vtime_now;
UEI_DEFINE(uei);

// The DSQ ID for the shared queue. We use because the built-in DSQs cannot be
// used as priority queues.
#define SHARED_DSQ_ID 0

// Maximum amount of tasks enqueued/dispatched between kernel and user-space.
#define MAX_ENQUEUED_TASKS 4096

const volatile s32 usersched_pid;
u64 nr_user_enqueues;

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
	bpf_printk("scx_serverless: [set_usersched_needed] setting user-space scheduler needed flag");
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

	msg->value = 1;
	bpf_ringbuf_submit(msg, 0);

	bpf_printk("send_wake_msg: wakeup sent to userspace\n");

}

static void dispatch_user_scheduler(void) {
	bpf_printk("scx_serverless: [dispatch_user_scheduler] dispatching user scheduler");
	struct task_struct *p;

	p = usersched_task();
	if (p) {
		scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_INF, 0);
		bpf_task_release(p);
	}

	send_wake_msg();
}

static void enqueue_task_in_user_space(struct task_struct *p) {
	bpf_printk("scx_serverless: [enqueue_task_in_user_space] enqueueing task %d in user space", p->pid);
	struct scx_serverless_enqueued_task task = {};

	task.pid = p->pid;

	if (bpf_map_push_elem(&enqueued, &task, 0)) {
		// If we fail to enqueue the task in user space, put it
		// directly on the global DSQ.
		bpf_printk("scx_serverless: [enqueue_task_in_user_space] failed to enqueue task %d in user space, putting it on the global DSQ", p->pid);
		scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_DFL, 0);
	} else {
		__sync_fetch_and_add(&nr_user_enqueues, 1);
		set_usersched_needed();
	}
	bpf_printk("scx_serverless: [enqueue_task_in_user_space] successfully enqueued task %d in user space", p->pid);
}

void BPF_STRUCT_OPS(serverless_enqueue, struct task_struct *p, u64 enq_flags) {
	bpf_printk("scx_serverless: [serverless_enqueue] enqueueing task %d", p->pid);
	if(is_usersched_task(p)) {
		scx_bpf_dsq_insert(p, SCX_DSQ_GLOBAL, SCX_SLICE_INF, enq_flags);
	}
	else {
		struct task_ctx *tctx;
		tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);
		if (!tctx) {
			scx_bpf_error("Failed to lookup task ctx for %d", p->pid);
			return;
		}

		u64 vtime = p->scx.dsq_vtime;
		/*
		* Limit the amount of budget that an idling task can accumulate
		* to one slice.
		*/
		if (time_before(vtime, vtime_now - tctx->slice))
			vtime = vtime_now - tctx->slice;


		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, tctx->slice, vtime, enq_flags);
		bpf_printk("scx_serverless: [serverless_enqueue] successfully enqueued task %d with slice %llu", p->pid, tctx->slice);
	}
}


int BPF_STRUCT_OPS(serverless_dispatch, s32 cpu, struct task_struct *prev) {
	// s32 nr_dsq = scx_bpf_dsq_nr_queued(SHARED_DSQ_ID);
	// bpf_printk("scx_serverless: [serverless_dispatch] number of tasks on the DQQ: %llu", nr_dsq);
	if (test_and_clear_usersched_needed()) {
		bpf_printk("scx_serverless: [serverless_dispatch] user-space scheduler needed, dispatching user scheduler");
		dispatch_user_scheduler();
	}

	struct scx_serverless_dispatched_task u_task;

	bpf_repeat(MAX_ENQUEUED_TASKS) {
		s32 pid;
		struct task_struct *p;

		if (bpf_map_pop_elem(&dispatched, &u_task)) {
			break;
		}
		/*
		 * The task could have exited by the time we get around to
		 * dispatching it. Treat this as a normal occurrence, and simply
		 * move onto the next iteration.
		 */

		pid = u_task.pid;
		p = bpf_task_from_pid(pid);
		bpf_printk("scx_serverless: [serverless_dispatch] popped task %d from dispatched map", pid);
		if (!p)
			continue;

		struct task_ctx *task_ctx = bpf_task_storage_get(&task_ctx_stor, p, 0, 0);
		if (!task_ctx) {
			scx_bpf_error("Failed to lookup task ctx for %d", p->pid);
			bpf_task_release(p);
			continue;
		}

		if(u_task.slice == 0) {
			// If the slice is zero, we use the default slice value.
			bpf_printk("scx_serverless: [serverless_dispatch] task %d has zero slice, using default slice", p->pid);
			u_task.slice = SCX_SLICE_DFL;
		}

		task_ctx->slice = u_task.slice;
		scx_bpf_dsq_insert_vtime(p, SHARED_DSQ_ID, task_ctx->slice, vtime_now, 0);
		bpf_printk("scx_serverless: [serverless_dispatch] successfully dispatched task %d with slice %llu", p->pid, task_ctx->slice);
		bpf_task_release(p);
	}

	return 0;
}

/*
 * A CPU is about to change its idle state. If the CPU is going idle, ensure
 * that the user-space scheduler has a chance to run if there is any remaining
 * work to do.
 */
void BPF_STRUCT_OPS(serverless_update_idle, s32 cpu, bool idle) {
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

void BPF_STRUCT_OPS(serverless_running, struct task_struct *p) {
	// Global vtime always progresses forward as tasks start executing. The
	// test and update can be performed concurrently from multiple CPUs and
	// thus racy. Any error should be contained and temporary. Let's just
	// live with it.
	bpf_printk("scx_serverless: [serverless_running] running task %d, with vtime %llu", p->pid, p->scx.dsq_vtime);

	if (time_before(vtime_now, p->scx.dsq_vtime))
		vtime_now = p->scx.dsq_vtime;
}

void BPF_STRUCT_OPS(serverless_stopping, struct task_struct *p, bool runnable) {
	p->scx.dsq_vtime += (SCX_SLICE_DFL - p->scx.slice) * 100 / p->scx.weight;
}

int BPF_STRUCT_OPS(serverless_enable, struct task_struct *p) {
	bpf_printk("scx_serverless: [serverless_enable] enabling task %d", p->pid);
	p->scx.dsq_vtime = vtime_now;

	if (!bpf_task_storage_get(&task_ctx_stor, p, 0, BPF_LOCAL_STORAGE_GET_F_CREATE)) {
		scx_bpf_error("Failed to create task ctx for %d", p->pid);
		return -ENOMEM;
	}

	if(!is_usersched_task(p)) {
		bpf_printk("scx_serverless: [serverless_enable] task %d is not the user scheduler, enqueueing in user space", p->pid);
		enqueue_task_in_user_space(p);
	}
	else if (test_and_clear_usersched_needed()){
		bpf_printk("scx_serverless: [serverless_enable] task %d is the user scheduler", p->pid);
		dispatch_user_scheduler();
	}

	return 0;
}

int BPF_STRUCT_OPS(serverless_init_task, struct task_struct *p, struct scx_init_task_args *args) {
	// bpf_printk("scx_serverless: [serverless_init_task] initializing task %d", p->pid);
	struct task_ctx *tctx;

	tctx = bpf_task_storage_get(&task_ctx_stor, p, 0, BPF_LOCAL_STORAGE_GET_F_CREATE);
	if (!tctx) {
		scx_bpf_error("Failed to create task ctx for %d", p->pid);
		return -ENOMEM;
	}

	// Initialize the slice to a default value.
	tctx->slice = SCX_SLICE_DFL;
	return 0;
}

int BPF_STRUCT_OPS(serverless_exit_task, struct task_struct *p, struct scx_exit_task_args *args) {
	// bpf_printk("scx_serverless: [serverless_exit_task] exiting task %d, args", p->pid);
	if(!bpf_task_storage_delete(&task_ctx_stor, p)) {
		// bpf_printk("scx_serverless: [serverless_exit_task] Failed to delete task ctx for %d", p->pid);
		return -ENOENT;
	}

	return 0;
}

s32 BPF_STRUCT_OPS_SLEEPABLE(serverless_init) {
	bpf_printk("scx_serverless: [serverless_init] initializing");
	if (usersched_pid <= 0) {
		scx_bpf_error("User scheduler pid uninitialized (%d)", usersched_pid);
		return -EINVAL;
	}

	return scx_bpf_create_dsq(SHARED_DSQ_ID, -1);
}

void BPF_STRUCT_OPS(serverless_exit, struct scx_exit_info *ei) {
	bpf_printk("scx_serverless: [serverless_exit] exiting");
	UEI_RECORD(uei, ei);
}

void BPF_STRUCT_OPS(serverless_runnable, struct task_struct *p, u64 enq_flags) {
	bpf_printk("scx_serverless: [serverless_runnable] runnable task %d", p->pid);
}


SCX_OPS_DEFINE(serverless_ops,
	       .enqueue			= (void *)serverless_enqueue,
	       .dispatch		= (void *)serverless_dispatch,
		   .running			= (void *)serverless_running,
		   .stopping		= (void *)serverless_stopping,
	       .update_idle		= (void *)serverless_update_idle,
	       .init_task		= (void *)serverless_init_task,
		   .enable			= (void *)serverless_enable,
		   .exit_task		= (void *)serverless_exit_task,
	       .init			= (void *)serverless_init,
	       .exit			= (void *)serverless_exit,
		   .runnable		= (void *)serverless_runnable,
	       .flags			= SCX_OPS_ENQ_LAST | SCX_OPS_KEEP_BUILTIN_IDLE | SCX_OPS_SWITCH_PARTIAL,
	       .name			= "serverless");
//SCX_OPS_SWITCH_PARTIAL