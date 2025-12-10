#include <scx/common.bpf.h>

char _license[] SEC("license") = "GPL";

// Debug macro: only prints when DEBUG is defined
#ifdef DEBUG
#define DEBUG_PRINTK(fmt, ...) bpf_printk(fmt, ##__VA_ARGS__)
#else
#define DEBUG_PRINTK(fmt, ...) do {} while (0)
#endif

static u64 vtime_now;
volatile u64 nr_enabled;
volatile u64 nr_disabled;
UEI_DEFINE(uei);

// The DSQ ID for the shared queue. We use because the built-in DSQs cannot be
// used as priority queues.
#define SHARED_DSQ_ID 0

// Fibonacci argument to slice mapping
#define FIB_ARG_MIN 24
#define FIB_ARG_MAX 46
#define MAX_CMDLINE_LEN 64
#define MAX_ENQUEUED_TASKS 4096

// Slice mapping table: fib_arg -> slice in nanoseconds
// Index = fib_arg - FIB_ARG_MIN
// Values:
//   - SCX_SLICE_DFL (0) for default slice
//   - SCX_SLICE_INF (1) for infinite slice
static const u64 fib_slice_map[] = {
	1,       // fib 24 -> SCX_SLICE_INF
	1,       // fib 25 -> SCX_SLICE_INF
	1,       // fib 26 -> SCX_SLICE_INF
	1,       // fib 27 -> SCX_SLICE_INF
	1,       // fib 28 -> SCX_SLICE_INF
	1,       // fib 29 -> SCX_SLICE_INF
	1,       // fib 30 -> SCX_SLICE_INF
	1,       // fib 31 -> SCX_SLICE_INF
	1,       // fib 32 -> SCX_SLICE_INF
	1,       // fib 33 -> SCX_SLICE_INF
	1,       // fib 34 -> SCX_SLICE_INF
	1,       // fib 35 -> SCX_SLICE_INF
	0,       // fib 36 -> SCX_SLICE_DFL
	0,       // fib 37 -> SCX_SLICE_DFL
	0,       // fib 38 -> SCX_SLICE_DFL
	0,       // fib 39 -> SCX_SLICE_DFL
	0,       // fib 40 -> SCX_SLICE_DFL
	0,       // fib 41 -> SCX_SLICE_DFL
	0,       // fib 42 -> SCX_SLICE_DFL
	0,       // fib 43 -> SCX_SLICE_DFL
	0,       // fib 44 -> SCX_SLICE_DFL
	0,       // fib 45 -> SCX_SLICE_DFL
	0,       // fib 46 -> SCX_SLICE_DFL
	// Durations in milliseconds for the fibonacci arguments
	// fib      = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,  36,  37,  38,  39,  40,  40,   41,   42,   43,   44,   45,    46]
	// dur_list = [ 4,  5,  5,  6,  7,  8, 11, 15, 21, 31, 47, 72, 113, 179, 286, 459, 740, 739, 1225, 1945, 3192, 5207, 8247, 13186]
};

const volatile s32 usersched_pid;

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
 * Get a time slice to a task based on its cmdline argument.
 * Reads the task's cmdline, extracts the fibonacci argument,
 * and returns the appropriate slice from the mapping table.
 *
 * Returns:
 *   - Slice in nanoseconds based on fib_arg
 *   - 0 (SCX_SLICE_DFL) if cmdline parsing fails or arg is out of range
 *   - 1 (SCX_SLICE_INF) for infinite slice (if configured in mapping)
 */
static u64 get_task_slice(struct task_struct *p) {
	char cmdline[MAX_CMDLINE_LEN];
	unsigned long arg_start = p->mm->arg_start;
	unsigned long arg_end = p->mm->arg_end;
	unsigned long total_len = arg_end - arg_start;

	// Sanity check
	if (total_len <= 0) {
		return SCX_SLICE_DFL;
	}

	// Read either from start or the last MAX_CMDLINE_LEN bytes
	unsigned long read_start;
	if (total_len > MAX_CMDLINE_LEN) {
		read_start = arg_end - MAX_CMDLINE_LEN;
		total_len = MAX_CMDLINE_LEN;
	} else {
		read_start = arg_start;
	}

	long ret = bpf_probe_read_user(cmdline, MAX_CMDLINE_LEN, (void *)read_start);
	if (ret < 0) return SCX_SLICE_DFL;

	// Force null termination at the very end of our buffer
	cmdline[total_len - 1] = '\0';

	// Parse fib argument from cmdline
	// We are looking for the first digit sequence in this window.
	u64 fib_arg = 0;
	bool found_digit = false;

	#pragma unroll
		for (int i = 0; i < MAX_CMDLINE_LEN - 1; i++) {
			char c = cmdline[i];

			if (i >= total_len - 1) {
				break;
			}

			// Replace null bytes with spaces (making it debug printable for bpf_printk)
			if (c == '\0') {
				cmdline[i] = ' ';
				if (found_digit) break;
				continue;
			}

			if (c >= '0' && c <= '9') {
				found_digit = true;
				// CORRECT LOGIC: Shift existing value left by decimal place, add new digit
				fib_arg = (fib_arg * 10) + (c - '0');
			} else if (found_digit) {
				// We hit a delimiter after finding numbers
				break;
			}
		}

	if (!found_digit) return SCX_SLICE_DFL;

	u64 slice = SCX_SLICE_DFL;

	// Make sure fib_arg is in valid range
	if (fib_arg >= FIB_ARG_MIN && fib_arg <= FIB_ARG_MAX) {
		slice = fib_slice_map[fib_arg - FIB_ARG_MIN];
		switch(slice) {
			case(0):
				slice = SCX_SLICE_DFL;
				break;
			case(1):
				slice = SCX_SLICE_INF;
				break;
		}
	} else {
		DEBUG_PRINTK("fib_arg %d out of range [%d, %d], using default slice",
					fib_arg, FIB_ARG_MIN, FIB_ARG_MAX);
		fib_arg = 0;
	}

	bpf_printk("Task %d cmdline: '%s', fib_arg: %d, assigned slice: %llu ns", p->pid, cmdline, fib_arg, slice);
	return slice;
}

int create_task_ctx(struct task_struct *p, u64 slice) {
	struct task_ctx tctx_init = {
		.slice = slice,
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
		scx_bpf_kick_cpu(cpu, 0);
	}
	return cpu;
}

s32 BPF_STRUCT_OPS(serverless_enqueue, struct task_struct *p, u64 enq_flags) {
	DEBUG_PRINTK("%-30s enqueueing task %d, associated_cpu %d, enq_flags 0x%llx",	"[serverless_enqueue]", p->pid,	scx_bpf_task_cpu(p), (unsigned long long)enq_flags);

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
	scx_bpf_kick_cpu(scx_bpf_task_cpu(p), 0);
	DEBUG_PRINTK("%-30s task %d enqueued ,ran_time %llu, task_slice %llu", "[serverless_enqueue]", p->pid, vtime, tctx->slice);

	return 0;
}

int BPF_STRUCT_OPS(serverless_dispatch, s32 cpu, struct task_struct *prev) {
	// Dequeue tasks that are sent from userspace through *dispatched* map
	// dequeue_tasks_from_userspace();

	// Move tasks from the shared DSQ to the local DSQ, if any.
	int nr_queued = scx_bpf_dsq_nr_queued(SHARED_DSQ_ID);
	if(nr_queued > 0) {
		DEBUG_PRINTK("%-30s there are %d tasks in the shared DSQ", "[serverless_dispatch]", nr_queued);
		if(!scx_bpf_dsq_move_to_local(SHARED_DSQ_ID)) {
			DEBUG_PRINTK("%-30s failed to move tasks from shared DSQ to local DSQ", "[serverless_dispatch]");
		}
	}
	return 0;
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

int BPF_STRUCT_OPS(serverless_enable, struct task_struct *p) {
	u64 slice;
	DEBUG_PRINTK("%-30s enabling task %d", "[serverless_enable]", p->pid);
	p->scx.dsq_vtime = vtime_now;

	slice = get_task_slice(p);

	if (create_task_ctx(p, slice) < 0) {
		return -ENOMEM;
	}

	__sync_fetch_and_add(&nr_enabled, 1);
	return 0;
}

int BPF_STRUCT_OPS(serverless_disable, struct task_struct *p) {
	DEBUG_PRINTK("%-30s disabling task %d", "[serverless_disable]", p->pid);
	bpf_task_storage_delete(&task_ctx_stor, p);
	__sync_fetch_and_add(&nr_disabled, 1);
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
		   .enable			= (void *)serverless_enable,
		   .disable			= (void *)serverless_disable,
		   .init			= (void *)serverless_init,
		   .exit			= (void *)serverless_exit,
		   .flags			= SCX_OPS_ENQ_LAST | SCX_OPS_KEEP_BUILTIN_IDLE | SCX_OPS_SWITCH_PARTIAL,
		   .name			= "serverless");
