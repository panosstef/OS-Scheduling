#!/bin/bash
# Setup CPU isolation using cpusets (legacy method)

MAIN_CPU=${1:-0}
WORKLOAD_CPUS=${2:-"1-$(nproc --ignore=1)"}

echo "Setting up CPU isolation using cpusets:"
echo "  Orchestrator CPU: $MAIN_CPU"
echo "  Workload CPUs: $WORKLOAD_CPUS"

# Mount cpuset if not already mounted
if ! mount | grep -q cpuset; then
    sudo mkdir -p /dev/cpuset
    sudo mount -t cpuset cpuset /dev/cpuset
fi

# Create cpuset directories
sudo mkdir -p /dev/cpuset/loadgen
sudo mkdir -p /dev/cpuset/loadgen/orchestrator
sudo mkdir -p /dev/cpuset/loadgen/workload

# Set CPU affinity for orchestrator
echo "$MAIN_CPU" | sudo tee /dev/cpuset/loadgen/orchestrator/cpuset.cpus > /dev/null
echo "0" | sudo tee /dev/cpuset/loadgen/orchestrator/cpuset.mems > /dev/null

# Set CPU affinity for workload processes
echo "$WORKLOAD_CPUS" | sudo tee /dev/cpuset/loadgen/workload/cpuset.cpus > /dev/null
echo "0" | sudo tee /dev/cpuset/loadgen/workload/cpuset.mems > /dev/null

# Enable cpu_exclusive for better isolation
echo "1" | sudo tee /dev/cpuset/loadgen/orchestrator/cpuset.cpu_exclusive > /dev/null
echo "1" | sudo tee /dev/cpuset/loadgen/workload/cpuset.cpu_exclusive > /dev/null

# Move current process to orchestrator cpuset
echo $$ | sudo tee /dev/cpuset/loadgen/orchestrator/cpuset.procs > /dev/null

echo "Cpuset isolation setup complete!"
