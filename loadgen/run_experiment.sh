#!/bin/bash
[ "$EUID" -ne 0 ] && exec sudo "$0" "$@"
set -e

HOSTNAME="$(hostname)"
HOSTNAME="${HOSTNAME:2}"
DATE="$(date +%d-%m-%Y_%H:%M)"
DEFAULT_FILENAME="${HOSTNAME}_${DATE}"

#Change open fd limit
ulimit -n 16384

#Sync the shared folder to the home directory (not doing so makes perf record lose samples)
echo -e "Syncing shared folder to home directory\n"
rsync -av --delete --exclude 'dataset/trace' --exclude 'log' --exclude '.git' /shared/loadgen ~/
cd ~/loadgen/runners

#Setup cpu isolation
../cpu_isolation/setup_cpu_isolation.sh --main_cpu 0
echo $$ > /sys/fs/cgroup/loadgen/orchestrator/cgroup.procs

#Run the ftrace experiment and perf experiment
./run_experiment_ftrace.sh $DEFAULT_FILENAME

./run_experiment_perf.sh $DEFAULT_FILENAME

#Cleanup cpu isolation
../cpu_isolation/cleanup_cpu_isolation.sh

#Sync the results back to the shared folder
echo -e "\nSyncing results back to shared folder"
sudo rsync -av --no-owner --no-group ~/loadgen/log /shared/loadgen/

#FOR FIFO EXECUTION REMOVE KERNEL RT LIMITS
#or run a kernel with CONFIG_RT_GROUP_SCHED disabled
#sysctl -w kernel.sched_rt_runtime_us=-1