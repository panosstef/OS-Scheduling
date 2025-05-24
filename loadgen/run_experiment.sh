#!/bin/bash
[ "$EUID" -ne 0 ] && exec sudo "$0" "$@"
set -e

HOSTNAME="$(hostname)"
HOSTNAME="${HOSTNAME:2}"
DATE="$(date +%d-%m-%Y_%H:%M)"
DEFAULT_FILENAME="${HOSTNAME}_${DATE}"

#Sync the shared folder to the home directory (not doing so makes perf record lose samples)
echo -e "Syncing shared folder to home directory\n"
rsync -av --delete /shared/loadgen ~/
cd ~/loadgen/runners

#Run the ftrace experiment and perf experiment
echo -e "\nRunning ftrace experiment\n"
./run_experiment_ftrace.sh $DEFAULT_FILENAME

echo -e "\nRunning perf experiment\n"
./run_experiment_perf.sh $DEFAULT_FILENAME

#Sync the results back to the shared folder
echo -e "\nSyncing results back to shared folder"
sudo rsync -av --no-owner --no-group ~/loadgen/log /shared/loadgen/