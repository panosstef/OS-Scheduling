#!/bin/bash
# setup_cpu_isolation.sh - Set up CPU isolation using cgroups v2

set -e

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Default values
MAIN_CPU=0
NUM_CPUS=$(nproc)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --main_cpu)
            MAIN_CPU="$2"
            shift 2
            ;;
        --child_cpus)
            CHILD_CPUS="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--main_cpu CPU] [--child_cpus CPU_LIST]"
            echo "  --main_cpu CPU        CPU core for orchestrator (default: 0)"
            echo "  --child_cpus CPU_LIST Comma-separated list of CPUs for workloads"
            echo "                        (default: all except main_cpu)"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Generate child CPU list if not provided
if [[ -z "$CHILD_CPUS" ]]; then
    CHILD_CPUS=""
    for ((i=0; i<NUM_CPUS; i++)); do
        if [[ $i -ne $MAIN_CPU ]]; then
            if [[ -n "$CHILD_CPUS" ]]; then
                CHILD_CPUS="$CHILD_CPUS,$i"
            else
                CHILD_CPUS="$i"
            fi
        fi
    done
fi

echo "Setting up CPU isolation:"
echo "  Main CPU (orchestrator): $MAIN_CPU"
echo "  Child CPUs (workloads): $CHILD_CPUS"
echo "  Total CPUs: $NUM_CPUS"

# Check if cgroups v2 is available
if [[ ! -d "/sys/fs/cgroup" ]] || [[ ! -f "/sys/fs/cgroup/cgroup.controllers" ]]; then
    echo "Error: cgroups v2 not available. Please ensure your system supports cgroups v2."
    exit 1
fi

# Check if cpuset controller is available
if ! grep -q "cpuset" /sys/fs/cgroup/cgroup.controllers; then
    echo "Error: cpuset controller not available in cgroups v2"
    echo "Available root controllers:"
    cat /sys/fs/cgroup/cgroup.controllers
    exit 1
fi

# Create loadgen cgroup hierarchy
LOADGEN_CGROUP="/sys/fs/cgroup/loadgen"
MAIN_CGROUP="$LOADGEN_CGROUP/orchestrator"
WORKLOAD_CGROUP="$LOADGEN_CGROUP/workload"

# Remove existing cgroups if they exist
if [[ -d "$LOADGEN_CGROUP" ]]; then
    echo "Removing existing loadgen cgroups..."
    # Move all processes out first
    if [[ -f "$MAIN_CGROUP/cgroup.procs" ]]; then
        while read -r pid; do
            [[ -n "$pid" ]] && echo "$pid" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
        done < "$MAIN_CGROUP/cgroup.procs"
    fi
    if [[ -f "$WORKLOAD_CGROUP/cgroup.procs" ]]; then
        while read -r pid; do
            [[ -n "$pid" ]] && echo "$pid" > /sys/fs/cgroup/cgroup.procs 2>/dev/null || true
        done < "$WORKLOAD_CGROUP/cgroup.procs"
    fi

    rmdir "$MAIN_CGROUP" 2>/dev/null || true
    rmdir "$WORKLOAD_CGROUP" 2>/dev/null || true
    rmdir "$LOADGEN_CGROUP" 2>/dev/null || true
fi

# First, ensure cpuset controller is enabled at the root level
if ! echo "+cpuset" > /sys/fs/cgroup/cgroup.subtree_control 2>/dev/null; then
    echo "Warning: Could not enable cpuset at root level (may already be enabled)"
fi

# Create cgroup hierarchy
mkdir -p "$MAIN_CGROUP"
mkdir -p "$WORKLOAD_CGROUP"

# Enable cpuset controller for loadgen cgroup
if ! echo "+cpuset" > "$LOADGEN_CGROUP/cgroup.subtree_control"; then
    echo "Error: Failed to enable cpuset controller for $LOADGEN_CGROUP"
    echo "This usually means cpuset is not available in the parent cgroup."
    echo "Available controllers at root:"
    cat /sys/fs/cgroup/cgroup.controllers 2>/dev/null || echo "Failed to read root cgroup.controllers"
    echo "Available controllers in loadgen cgroup:"
    cat "$LOADGEN_CGROUP/cgroup.controllers" 2>/dev/null || echo "Failed to read cgroup.controllers"
    exit 1
fi

# Wait for cgroup files to be created and verify they exist
sleep 0.

# Verify cgroup files exist before writing
if [[ ! -f "$MAIN_CGROUP/cpuset.cpus" ]]; then
    echo "Error: $MAIN_CGROUP/cpuset.cpus not available"
    echo "Available files in $MAIN_CGROUP:"
    ls -la "$MAIN_CGROUP/" 2>/dev/null || echo "Directory listing failed"
    exit 1
fi

if [[ ! -f "$WORKLOAD_CGROUP/cpuset.cpus" ]]; then
    echo "Error: $WORKLOAD_CGROUP/cpuset.cpus not available"
    echo "Available files in $WORKLOAD_CGROUP:"
    ls -la "$WORKLOAD_CGROUP/" 2>/dev/null || echo "Directory listing failed"
    exit 1
fi

# Set CPU affinity for orchestrator cgroup
echo "$MAIN_CPU" > "$MAIN_CGROUP/cpuset.cpus"
echo "0" > "$MAIN_CGROUP/cpuset.mems"

# Set CPU affinity for workload cgroup
echo "$CHILD_CPUS" > "$WORKLOAD_CGROUP/cpuset.cpus"
echo "0" > "$WORKLOAD_CGROUP/cpuset.mems"

# Make cgroups writable by current user
if [[ -n "$SUDO_USER" ]]; then
    REAL_USER_ID=$(id -u "$SUDO_USER")
    REAL_GROUP_ID=$(id -g "$SUDO_USER")
    chown -R "$REAL_USER_ID:$REAL_GROUP_ID" "$LOADGEN_CGROUP"
else
    # Make it writable by all users (fallback)
    chmod -R 666 "$LOADGEN_CGROUP"/{orchestrator,workload}/cgroup.procs
fi

#Print the cgroups and export them for use in experiments
export MAIN_CGROUP
export WORKLOAD_CGROUP
echo "Orchestrator cgroup: $MAIN_CGROUP"
echo "Workload cgroup: $WORKLOAD_CGROUP"