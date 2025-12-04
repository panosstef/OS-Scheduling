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

/* Debug printf macro - only prints when verbose mode is enabled */
#define dprintf(fmt, ...) \
	do { if (verbose) printf(fmt, ##__VA_ARGS__); } while (0)
#ifdef DEBUG_BUILD
#include "scx_serverless_debug.bpf.skel.h"
#define SKEL_NAME scx_serverless_debug
#else
#include "scx_serverless.bpf.skel.h"
#define SKEL_NAME scx_serverless
#endif

// Helper macros to create function names based on build type
#define _SKEL_FUNC(name, func) name##__##func
#define SKEL_FUNC(name, func) _SKEL_FUNC(name, func)
#define SKEL_OPEN() SKEL_FUNC(SKEL_NAME, open)()
#define SKEL_LOAD(skel) SKEL_FUNC(SKEL_NAME, load)(skel)
#define SKEL_ATTACH(skel) SKEL_FUNC(SKEL_NAME, attach)(skel)
#define SKEL_DESTROY(skel) SKEL_FUNC(SKEL_NAME, destroy)(skel)

const char help_fmt[] =
"Serverless userspace sched_ext scheduler.\n"
"\n"
"Try to reduce `sysctl kernel.pid_max` if this program triggers OOMs.\n"
"\n"
"Usage: %s [-b BATCH]\n"
"\n"
"  -s            Print the fibonacci argument to slice mapping and exit\n"
"  -b BATCH      The number of tasks to batch when dispatching (default: 8)\n"
"  -v            Print libbpf debug messages\n"
"  -h            Display this help and exit\n";

/* Defined in UAPI */
#define SCHED_EXT 7

static bool verbose;
static volatile int exit_req;

#ifdef DEBUG_BUILD
static struct scx_serverless_debug *skel;
#else
static struct scx_serverless *skel;
#endif
static struct bpf_link *ops_link;

static int libbpf_print_fn(enum libbpf_print_level level, const char *format, va_list args) {
	if (level == LIBBPF_DEBUG && !verbose)
		return 0;
	return vfprintf(stderr, format, args);
}

static void sigint_handler(int userland) {
	printf("SIGINT received, exiting...\n");
	exit_req = 1;
}

static void pre_bootstrap(int argc, char **argv) {
	__u32 opt;

	libbpf_set_print(libbpf_print_fn);
	signal(SIGINT, sigint_handler);
	signal(SIGTERM, sigint_handler);

	while ((opt = getopt(argc, argv, "v")) != -1) {
		switch (opt) {
		case 'v':
			verbose = true;
			break;
		default:
			fprintf(stderr, help_fmt, basename(argv[0]));
			exit(opt != 'h');
		}
	}
}

static void bootstrap(char *comm) {
#ifdef DEBUG_BUILD
	skel = SCX_OPS_OPEN(serverless_ops, scx_serverless_debug);
#else
	skel = SCX_OPS_OPEN(serverless_ops, scx_serverless);
#endif

	skel->rodata->usersched_pid = getpid();
	assert(skel->rodata->usersched_pid > 0);

	printf("bootstrap: usersched_pid set to %d\n", skel->rodata->usersched_pid);

#ifdef DEBUG_BUILD
	SCX_OPS_LOAD(skel, serverless_ops, scx_serverless_debug, uei);
#else
	SCX_OPS_LOAD(skel, serverless_ops, scx_serverless, uei);
#endif

#ifdef DEBUG_BUILD
	ops_link = SCX_OPS_ATTACH(skel, serverless_ops, scx_serverless_debug);
#else
	ops_link = SCX_OPS_ATTACH(skel, serverless_ops, scx_serverless);
#endif

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

static void sched_main_loop(void) {
	while (!exit_req) {
		// Read statistics from BPF global variables
		u64 enabled_count = skel->bss->nr_enabled;
		u64 disabled_count = skel->bss->nr_disabled;
		u64 active = enabled_count - disabled_count;

		printf("[Stats] Total enabled: %lu | Total disabled: %lu | Active: %lu\n",
		       enabled_count, disabled_count, active);
		fflush(stdout);

		sleep(1);
	}
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
#ifdef DEBUG_BUILD
	scx_serverless_debug__destroy(skel);
#else
	scx_serverless__destroy(skel);
#endif

	if (UEI_ECODE_RESTART(ecode)) {
		printf("main: restarting due to UEI_ECODE_RESTART\n");
		goto restart;
	}
	return 0;
}