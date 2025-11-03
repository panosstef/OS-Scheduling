#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <sched.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>

#ifndef SCHED_EXT
#define SCHED_EXT 7   // usually defined in newer Linux headers; adjust if needed
#endif

int main(int argc, char *argv[]) {
	if (argc < 2) {
		fprintf(stderr, "Usage: %s <program> [args...]\n", argv[0]);
		exit(EXIT_FAILURE);
	}

	struct sched_param param;
	memset(&param, 0, sizeof(param));

	// You might need to set priority; for SCHED_EXT usually ignored
	param.sched_priority = 0;

	if (sched_setscheduler(0, SCHED_EXT, &param) == -1) {
		fprintf(stderr, "sched_setscheduler failed: %s\n", strerror(errno));
		exit(EXIT_FAILURE);
	}

	execvp(argv[1], &argv[1]);
	perror("execvp failed");
	exit(EXIT_FAILURE);
}