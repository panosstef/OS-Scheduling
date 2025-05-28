#!/bin/bash
# cleanup_cpu_isolation.sh - Clean up CPU isolation cgroups

set -e

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

LOADGEN_CGROUP="/sys/fs/cgroup/loadgen"
MAIN_CGROUP="$LOADGEN_CGROUP/orchestrator"
WORKLOAD_CGROUP="$LOADGEN_CGROUP/workload"

echo "Cleaning up CPU isolation cgroups..."

if [[ -d "$LOADGEN_CGROUP" ]]; then
    # Move all processes back to root cgroup
    echo "Moving processes back to root cgroup..."

    if [[ -f "$MAIN_CGROUP/cgroup.procs" ]]; then
        while read -r pid; do
            if [[ -n "$pid" ]]; then
                echo "$pid" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
            fi
        done < "$MAIN_CGROUP/cgroup.procs"
    fi

    if [[ -f "$WORKLOAD_CGROUP/cgroup.procs" ]]; then
        while read -r pid; do
            if [[ -n "$pid" ]]; then
                echo "$pid" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
            fi
        done < "$WORKLOAD_CGROUP/cgroup.procs"
    fi

    # Remove cgroup directories
    echo "Removing cgroup directories..."
    rmdir "$MAIN_CGROUP" 2>/dev/null || true
    rmdir "$WORKLOAD_CGROUP" 2>/dev/null || true
    rmdir "$LOADGEN_CGROUP" 2>/dev/null || true

    echo "CPU isolation cleanup complete!"
else
    echo "No loadgen cgroups found to clean up."
fi