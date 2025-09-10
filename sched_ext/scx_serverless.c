#include <stdio.h>
#include <unistd.h>
#include <sched.h>
#include <signal.h>
#include <assert.h>
#include <libgen.h>
#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <bpf/bpf.h>
#include <sys/mman.h>
#include <sys/queue.h>
#include <sys/syscall.h>

#include <scx/common.h>
#include "scx_serverless.h"
#include "scx_serverless.bpf.skel.h"

const char help_fmt[] =
"Serverless userspacec sched_ext scheduler.\n"
"\n"
"Try to reduce `sysctl kernel.pid_max` if this program triggers OOMs.\n"
"\n"
"Usage: %s [-b BATCH]\n"
"\n"
"  -b BATCH      The number of tasks to batch when dispatching (default: 8)\n"
"  -v            Print libbpf debug messages\n"
"  -h            Display this help and exit\n";

// Fibonacci argument to runtime slice mapping
// Consecutive arguments 29-46 for O(1) direct indexing
struct fib_slice_mapping {
	int fib_arg;
	__u64 runtime_ns;
};

// TODO ARE THESE CORRECT?
// CHANGE TO NS
static const struct fib_slice_mapping fib_slice_map[] = {
	{24, 7000},     // 0.007 ms -> 7 us
	{25, 8000},     // 0.008 ms -> 8 us
	{26, 9000},     // 0.009 ms -> 9 us
	{27, 10000},    // 0.010 ms -> 10 us
	{28, 12000},    // 0.012 ms -> 12 us
	{29, 14000},    // 0.014 ms -> 14 us
	{29, 15077},    // 15.077 ms -> 15077 us
	{30, 17210},    // 17.210 ms -> 17210 us
	{31, 21757},    // 21.757 ms -> 21757 us
	{32, 28737},    // 28.737 ms -> 28737 us
	{33, 39585},    // 39.585 ms -> 39585 us
	{34, 57459},    // 57.459 ms -> 57459 us
	{35, 87158},    // 87.158 ms -> 87158 us
	{36, 133707},   // 133.707 ms -> 133707 us
	{37, 211531},   // 211.531 ms -> 211531 us
	{38, 335664},   // 335.664 ms -> 335664 us
	{39, 538014},   // 538.014 ms -> 538014 us
	{40, 863074},   // 863.074 ms -> 863074 us
	{41, 1391510},  // 1391.510 ms -> 1391510 us
	{42, 2245762},  // 2245.762 ms -> 2245762 us
	{43, 3625336},  // 3625.336 ms -> 3625336 us
	{44, 5856877},  // 5856.877 ms -> 5856877 us
	{45, 9470577},  // 9470.577 ms -> 9470577 us
	{46, 15317228}, // 15317.228 ms -> 15317228 us
};
// Durations in microseconds for the fibonacci arguments
// dur_list = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 839, 1347, 2175, 3512, 5673, 9172, 14835]
// fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 40, 41, 42, 43, 44, 45, 46]

#define FIB_ARG_MIN 24
#define FIB_ARG_MAX 46
#define FIB_SLICE_MAP_SIZE (sizeof(fib_slice_map) / sizeof(fib_slice_map[0]))

/* Defined in UAPI */
#define SCHED_EXT 7

/* Number of tasks to batch when dispatching to user space. */
static __u32 batch_size = 8;

static bool verbose;
static volatile int exit_req;
static int enqueued_fd, dispatched_fd;

static struct ring_buffer *rb;

static struct scx_serverless *skel;
static struct bpf_link *ops_link;

/* Stats collected in user space. */
static __u64 nr_user_to_kernel_enqueues, nr_slice_dispatches, nr_slice_failed;

/* Number of tasks currently enqueued. */
static __u64 nr_curr_enqueued;

/* The data structure containing tasks that are enqueued in user space.
 * From this list the dispatch path takes tasks to dispatch them to the
 * kernel.
*/
struct enqueued_task {
	STAILQ_ENTRY(enqueued_task) entries;
	__u64 slice;
};

// Use a linked list to store tasks.
STAILQ_HEAD(dispatch_head, enqueued_task);
static struct dispatch_head dispatch_head = STAILQ_HEAD_INITIALIZER(dispatch_head);



/*
 * The main array of tasks. The array is allocated all at once during
 * initialization, based on /proc/sys/kernel/pid_max, to avoid having to
 * dynamically allocate memory on the enqueue path, which could cause a
 * deadlock. A more substantive user space scheduler could e.g. provide a hook
 * for newly enabled tasks that are passed to the scheduler from the
 * .prep_enable() callback to allows the scheduler to allocate on safe paths.
 */
struct enqueued_task *tasks;
static int pid_max;

static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args) {
	if (level == LIBBPF_DEBUG && !verbose)
		return 0;
	return vfprintf(stderr, format, args);
}

static void sigint_handler(int userland) {
	printf("SIGINT received, exiting...\n");
	exit_req = 1;
}

static int get_pid_max(void) {
	FILE *fp;
	int pid_max;

	fp = fopen("/proc/sys/kernel/pid_max", "r");
	if (fp == NULL) {
		fprintf(stderr, "Error opening /proc/sys/kernel/pid_max\n");
		return -1;
	}
	if (fscanf(fp, "%d", &pid_max) != 1) {
		fprintf(stderr, "Error reading from /proc/sys/kernel/pid_max\n");
		fclose(fp);
		return -1;
	}
	fclose(fp);

	return pid_max;
}

static int init_tasks(void) {
	pid_max = get_pid_max();
	if (pid_max < 0)
		return pid_max;

	tasks = calloc(pid_max, sizeof(*tasks));
	if (!tasks) {
		fprintf(stderr, "Error allocating tasks array\n");
		return -ENOMEM;
	}

	size_t allocated = pid_max * sizeof(*tasks);
	printf("Allocated memory: %zu bytes (%.2f KB)\n", allocated, allocated / 1024.0);
	return 0;
}

static __u32 task_pid(const struct enqueued_task *task) {
	return ((uintptr_t)task - (uintptr_t)tasks) / sizeof(*task);
}

static int dispatch_task(struct scx_serverless_dispatched_task d_task) {
	int err;

	if (verbose)
		printf("dispatch_task: called for PID %d with slice %llu\n", d_task.pid, d_task.slice);

	err = bpf_map_update_elem(dispatched_fd, NULL, &d_task, 0);
	if (err) {
		nr_slice_failed++;
		if (verbose)
			printf("dispatch_task: failed for PID %d: %s\n", d_task.pid, strerror(-err));
	} else {
		nr_slice_dispatches++;
		if (verbose)
			printf("dispatch_task: succeeded for PID %d\n", d_task.pid);
	}

	return err;
}

static struct enqueued_task *get_enqueued_task(__s32 pid) {
	if (verbose)
		printf("get_enqueued_task: called for PID %d\n", pid);

	if (pid >= pid_max) {
		if (verbose)
			printf("get_enqueued_task: PID %d >= pid_max %d, returning NULL\n", pid, pid_max);
		return NULL;
	}

	return &tasks[pid];
}

// Read the /proc/<pid>/cmdline into a buffer
int read_cmdline(pid_t pid, char *buf, size_t size) {
	char path[64];

	if (verbose)
		printf("read_cmdline: called for PID %d\n", pid);

	snprintf(path, sizeof(path), "/proc/%d/cmdline", pid);

	FILE *f = fopen(path, "r");
	if (!f) {
		if (verbose)
			printf("read_cmdline: failed to open %s\n", path);
		return -1;
	}

	size_t len = fread(buf, 1, size - 1, f);
	fclose(f);

	if (len == 0) {
		if (verbose)
			printf("read_cmdline: read 0 bytes for PID %d\n", pid);
		return -1;
	}

	// Replace NULs with spaces for printing
	for (size_t i = 0; i < len - 1; ++i) {
		if (buf[i] == '\0')
			buf[i] = ' ';
	}
	buf[len] = '\0';

	if (verbose)
		printf("read_cmdline: success for PID %d: '%s'\n", pid, buf);

	return 0;
}

// Get the slice value for a fibonacci argument
static __u64 get_slice_for_fib_arg(int fib_arg) {
	if (verbose)
		printf("get_slice_for_fib_arg: called with arg %d\n", fib_arg);

	if (fib_arg < FIB_ARG_MIN || fib_arg > FIB_ARG_MAX) {
		if (verbose)
			printf("get_slice_for_fib_arg: arg %d out of range [%d, %d], returning 0\n",
			       fib_arg, FIB_ARG_MIN, FIB_ARG_MAX);
		return 0;
	}

	// Direct array access using offset: fib_arg 29 -> index 0, fib_arg 30 -> index 1, etc.
	__u64 slice = fib_slice_map[fib_arg - FIB_ARG_MIN].runtime_ns;
	if (verbose)
		printf("get_slice_for_fib_arg: returning %llu us for arg %d\n", slice, fib_arg);
	return slice;
}

// Parse fibonacci argument from cmdline string
// Expected format: "/root/loadgen/payload/launch_function.out 42"
static int parse_fib_arg_from_cmdline(const char *cmdline) {
	if (verbose)
		printf("parse_fib_arg_from_cmdline: called with cmdline '%s'\n", cmdline);

	char *last_space = strrchr(cmdline, ' ');
	if (!last_space) {
		if (verbose)
			printf("parse_fib_arg_from_cmdline: no space found in cmdline\n");
		return -1; // No space found, invalid format
	}

	int arg = atoi(last_space + 1);
	if (arg <= 0) {
		if (verbose)
			printf("parse_fib_arg_from_cmdline: invalid arg %d\n", arg);
		return -1; // Invalid argument
	}

	if (verbose)
		printf("parse_fib_arg_from_cmdline: parsed arg %d\n", arg);
	return arg;
}

// Print the fibonacci argument to slice mapping
static void print_slice_mappings(void) {
	printf("Fibonacci Argument to Runtime Slice Mappings:\n");
	printf("============================================\n");
	for (int i = 0; i < FIB_SLICE_MAP_SIZE; i++) {
		printf("Fib arg %2d -> %7llu us (%6.3f ms)\n",
		       fib_slice_map[i].fib_arg,
		       fib_slice_map[i].runtime_ns,
		       fib_slice_map[i].runtime_ns / 1000.0);
	}
	printf("Default slice for unknown args: 0 ns (uses SCX_SLICE_DFL in BPF backend)\n");
}


// Get the tasks cmdline and based on that calculate a slice value.
static int local_enqueue_task(const struct scx_serverless_enqueued_task *bpf_task) {
	struct enqueued_task *curr;
	__u64 slice = 0; // Default slice value, so that BPF backend uses SCX_SLICE_DFL

	if (verbose)
		printf("local_enqueue_task: called for PID %d\n", bpf_task->pid);

	curr = get_enqueued_task(bpf_task->pid);
	if (!curr) {
		if (verbose)
			printf("local_enqueue_task: failed to get task for PID %d\n", bpf_task->pid);
		return ENOENT;
	}

	nr_user_to_kernel_enqueues++;
	nr_curr_enqueued++;

	// Get the cmdline of the task based on its PID.
	char task_arg[64];

	if (!read_cmdline(bpf_task->pid, task_arg, sizeof(task_arg))) {
		if (verbose)
			printf("local_enqueue_task: failed to read cmdline for PID %d\n", bpf_task->pid);
		goto enqueue;
	}

	// Parse fibonacci argument from cmdline
	int fib_arg = parse_fib_arg_from_cmdline(task_arg);
	if (fib_arg < 0) {
			printf("Task %d: invalid cmdline '%s', using default slice\n", bpf_task->pid, task_arg);
			goto enqueue;
		}

	slice = get_slice_for_fib_arg(fib_arg);
	printf("Task %d (fib arg %d): assigned slice %llu us\n", bpf_task->pid, fib_arg, slice);

	// Set the calculated slice in the task
	enqueue:
	curr->slice = slice;

	if (STAILQ_EMPTY(&dispatch_head)) {
		STAILQ_INSERT_HEAD(&dispatch_head, curr, entries);
		if (verbose)
			printf("local_enqueue_task: inserted task %d at head of dispatch queue\n", bpf_task->pid);
		return 0;
	}

	STAILQ_INSERT_TAIL(&dispatch_head, curr, entries);
	if (verbose)
		printf("local_enqueue_task: inserted task %d at tail of dispatch queue\n", bpf_task->pid);

	return 0;
}

// Get all tasks from the enqueued map and enqueue them to them locally.
// At the end of this function, no task should be left in the enqueued map (from kernel to userspace)
static void drain_enqueued_map(void) {
	if (verbose)
		printf("drain_enqueued_map: called\n");

	while (1) {
		struct scx_serverless_enqueued_task task;
		int err;

		if (bpf_map_lookup_and_delete_elem(enqueued_fd, NULL, &task)) {
			skel->bss->nr_userspace_queued = 0;
			skel->bss->nr_userspace_scheduled = nr_curr_enqueued;
			if (verbose)
				printf("drain_enqueued_map: completed, no more tasks\n");
			return;
		}

		err = local_enqueue_task(&task);
		if (err) {
			fprintf(stderr, "Failed to enqueue task %d: %s\n",
				task.pid, strerror(err));
			if (verbose)
				printf("drain_enqueued_map: exiting due to enqueue error\n");
			exit_req = 1;
			return;
		}
		if (verbose)
			printf("drain_enqueued_map: successfully enqueued task %d\n", task.pid);
	}
}

static void dispatch_batch(void) {
	__u32 i;

	if (verbose)
		printf("dispatch_batch: called with batch_size %d\n", batch_size);

	for (i = 0; i < batch_size; i++) {
		struct enqueued_task *task;
		int err;
		__s32 pid;

		task = STAILQ_FIRST(&dispatch_head);
		if (!task) {
			if (verbose)
				printf("dispatch_batch: no more tasks, dispatched %d tasks\n", i);
			break;
		}

		pid = task_pid(task);
		struct scx_serverless_dispatched_task d_task = {
			.pid = pid,
			.slice = task->slice,
		};
		err = dispatch_task(d_task);
		if (err) {
			printf("dispatch_task: Failed to dispatch task %d\n", pid);
			break;
		}
		STAILQ_REMOVE(&dispatch_head, task, enqueued_task, entries);
		nr_curr_enqueued--;
		if (verbose)
			printf("dispatch_batch: successfully dispatched task %d with slice %llu us\n", pid, d_task.slice);
	}
	skel->bss->nr_userspace_scheduled = nr_curr_enqueued;
	if (verbose)
		printf("dispatch_batch: completed, %lld tasks remaining\n", nr_curr_enqueued);
}

static void *run_stats_printer(void *arg) {
	printf("run_stats_printer: thread started\n");

	// while (!exit_req) {
	// 	__u64 nr_userspace_scheduled, nr_user_enqueues;

	// 	nr_user_enqueues = skel->bss->nr_user_enqueues;
	// 	nr_userspace_scheduled = skel->bss->nr_userspace_scheduled;

	// 	printf("o-----------------------o\n");
	// 	printf("| BPF ENQUEUES          |\n");
	// 	printf("|-----------------------|\n");
	// 	printf("|  user:     %10llu |\n", nr_user_enqueues);
	// 	printf("|  scheduled: %10llu |\n", nr_userspace_scheduled);
	// 	printf("|-----------------------|\n");
	// 	printf("| USER       |\n");
	// 	printf("|-----------------------|\n");
	// 	printf("|  enq:      %10llu |\n", nr_user_to_kernel_enqueues);
	// 	printf("|  disp:     %10llu |\n", nr_slice_dispatches);
	// 	printf("|  failed:   %10llu |\n", nr_slice_failed);
	// 	printf("o-----------------------o\n");
	// 	printf("\n\n");
	// 	fflush(stdout);
	// 	sleep(1);
	// }

	while (!exit_req) {
		// print the contents of the enqueued_fd BPF map
		struct scx_serverless_enqueued_task task;
		while (bpf_map_lookup_and_delete_elem(enqueued_fd, NULL, &task)) {
			printf("enqueued_fd: task %d\n", task.pid);
			fflush(stdout);
			sleep(1);
		}

	}

	return NULL;
}

static int __attribute__((unused))spawn_stats_thread(void) {
	pthread_t stats_printer;

	return pthread_create(&stats_printer, NULL, run_stats_printer, NULL);
}

static int handle_wake_msg(void *ctx, void *data, size_t len) {
	struct wake_msg *msg = data;
	printf("Got wakeup, value=%llu\n", msg->value);
	return 0;
}

struct ring_buffer *init_ring_buffer() {
	/* Setup ringbuf reader */
	struct ring_buffer *rb = ring_buffer__new(
		bpf_map__fd(skel->maps.wake_ringbuf),
		handle_wake_msg, NULL, NULL);
	if (!rb) {
		fprintf(stderr, "failed to create ring buffer\n");
		exit(-1);
	}

	printf("Ring buffer successfully created\n");
	return rb;
}


static void pre_bootstrap(int argc, char **argv) {
	int err;
	__u32 opt;

	err = init_tasks();
	if (err) {
		fprintf(stderr, "pre_bootstrap: init_tasks failed with error %d\n", err);
		exit(err);
	}

	libbpf_set_print(libbpf_print_fn);
	signal(SIGINT, sigint_handler);
	signal(SIGTERM, sigint_handler);

	while ((opt = getopt(argc, argv, "b:svh")) != -1) {
		switch (opt) {
		case 'b':
			batch_size = strtoul(optarg, NULL, 0);
			break;
		case 's':
			print_slice_mappings();
			exit(0);
			break;
		case 'v':
			verbose = true;
			break;
		default:
			fprintf(stderr, help_fmt, basename(argv[0]));
			exit(opt != 'h');
		}
	}

	/*
	 * It's not always safe to allocate in a user space scheduler, as an
	 * enqueued task could hold a lock that we require in order to be able
	 * to allocate.
	 */
	STAILQ_INIT(&dispatch_head);
	err = mlockall(MCL_CURRENT | MCL_FUTURE);
	SCX_BUG_ON(err, "Failed to prefault and lock address space");
}

static void bootstrap(char *comm) {
	skel = SCX_OPS_OPEN(serverless_ops, scx_serverless);

	skel->rodata->usersched_pid = getpid();
	assert(skel->rodata->usersched_pid > 0);

	printf("bootstrap: usersched_pid set to %d\n", skel->rodata->usersched_pid);

	SCX_OPS_LOAD(skel, serverless_ops, scx_serverless, uei);

	enqueued_fd = bpf_map__fd(skel->maps.enqueued);
	dispatched_fd = bpf_map__fd(skel->maps.dispatched);
	assert(enqueued_fd > 0);
	assert(dispatched_fd > 0);

	printf("bootstrap: got enqueued_fd=%d, dispatched_fd=%d\n", enqueued_fd, dispatched_fd);

	// SCX_BUG_ON(spawn_stats_thread(), "Failed to spawn stats thread");
	rb = init_ring_buffer();

	ops_link = SCX_OPS_ATTACH(skel, serverless_ops, scx_serverless);

	/*
	 * Enforce that the user scheduler task is managed by sched_ext. The
	 * task eagerly drains the list of enqueued tasks in its main work
	 * loop, and then yields the CPU. The BPF scheduler only schedules the
	 * user space scheduler task when at least one other task in the system
	 * needs to be scheduled.
	 */
	struct sched_param sched_param = {
		.sched_priority = sched_get_priority_max(SCHED_EXT),
	};

	int err = syscall(__NR_sched_setscheduler, getpid(), SCHED_EXT, &sched_param);
	SCX_BUG_ON(err, "Failed to set SCHED_EXT for usersched task");
}

void wait_for_work(struct ring_buffer *rb) {
	printf("Waiting for work...\n");
	int err = ring_buffer__poll(rb, -1); /* block until data */
	printf("[wait_for_work] : Woke up cause of data arrival\n");
	if (err < 0) {
		fprintf(stderr, "ring_buffer__poll failed: %d\n", err);
	}
}


static void sched_main_loop(void) {
	while (!exit_req) {
		printf("sched_main_loop: running main loop\n");
		fflush(stdout);
		/*
		 * Perform the following work in the main user space scheduler
		 * loop:
		 *
		 * 1. Drain all tasks from the enqueued map, and enqueue them
		 *    to the dispatched map.
		 *
		 * 2. Dispatch a batch of tasks from the dispatched map
		 *    down to the kernel.
		 *
		 * 3. Yield the CPU back to the system. The BPF scheduler will
		 *    reschedule the user space scheduler once another task has
		 *    been enqueued to user space.
		 */
		drain_enqueued_map();
		dispatch_batch();
		wait_for_work(rb);
	}

	printf("sched_main_loop: exiting\n");
}

int main(int argc, char **argv) {
	__u64 ecode;

	pre_bootstrap(argc, argv);
restart:
	printf("main: (re)starting scheduler\n");
	bootstrap(argv[0]);
	sched_main_loop();

	exit_req = 1;
	printf("main: cleaning up\n");
	bpf_link__destroy(ops_link);
	ecode = UEI_REPORT(skel, uei);
	scx_serverless__destroy(skel);

	ring_buffer__free(rb);

	if (UEI_ECODE_RESTART(ecode)) {
		printf("main: restarting due to UEI_ECODE_RESTART\n");
		goto restart;
	}
	return 0;
}