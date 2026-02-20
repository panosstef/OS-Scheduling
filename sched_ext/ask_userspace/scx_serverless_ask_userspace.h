// SPDX-License-Identifier: GPL-2.0
/* Copyright (c) 2022 Meta, Inc */

#ifndef __SCX_SERVERLESS_COMMON_H
#define __SCX_SERVERLESS_COMMON_H

/*
 * An instance of a task that has been enqueued by the kernel for consumption
 * by a user space global scheduler thread.
 */
struct scx_serverless_enqueued_task {
	__s32 pid;
};

struct scx_serverless_dispatched_task {
	__s32 pid; // The PID of the task that is being dispatched.
	__u64 slice; // The slice that the task should run with.
};

struct wake_msg {
	__u64 value;
};


#endif  // __SCX_SERVERLESS_COMMON_H