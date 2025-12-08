#!/bin/bash

cleanup() {
    # Kill the entire process group to ensure cat gets killed
	trap - EXIT INT TERM
    kill 0 2>/dev/null || true
    stty sane
    exit 0
}

trap cleanup EXIT INT TERM

# Start a new process group for this script
# sudo set -m

# Read character by character and intercept Ctrl+L
stty -icanon -echo
cat /sys/kernel/debug/tracing/trace_pipe \
    | awk '{$2=""; $3=""; sub(/bpf_trace_printk: /,""); print}' &

# Monitor for Ctrl+L
while true; do
    IFS= read -r -n1 char
    if [ "$char" = $'\f' ]; then  # Ctrl+L sends form feed character
        clear
    fi
done