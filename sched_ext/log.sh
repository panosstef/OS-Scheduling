#!/bin/sh

cleanup() {
    # Kill the entire process group to ensure cat gets killed
	trap - EXIT INT TERM
    kill 0 2>/dev/null || true
    exit 0
}

trap cleanup EXIT INT TERM

# Start a new process group for this script
# sudo set -m

cat /sys/kernel/debug/tracing/trace_pipe \
    | awk '{$2=""; $3=""; sub(/bpf_trace_printk: /,""); print}'