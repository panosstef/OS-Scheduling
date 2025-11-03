#!/bin/bash
[ "$EUID" -ne 0 ] && exec sudo "$0" "$@"
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTNAME="$(hostname)"
HOSTNAME="${HOSTNAME:2}"
DATE="$(date +%d-%m-%Y_%H:%M)"
DEFAULT_FILENAME="${HOSTNAME}_${DATE}"

FILENAME="${1:-$DEFAULT_FILENAME}"
FIFO_ARG="${2:-}"
SCHED_EXT_ARG="${3:-}"

#Run the script with tracing
mkdir -p "$SCRIPT_DIR/tmp"

#Run the script with tracing
echo -e "\nRunning ftrace experiment with filename: $FILENAME"
../capture/trace-cmd.sh --output "$SCRIPT_DIR/tmp/$FILENAME.dat" ../exec_workload.py --outputfile  "$SCRIPT_DIR/tmp/$FILENAME" $FIFO_ARG $SCHED_EXT_ARG --cpu_log

#Analyze the trace file
trace-cmd report -R -t -w --ts-check -i "$SCRIPT_DIR/tmp/$FILENAME.dat" > "$SCRIPT_DIR/tmp/$FILENAME.txt"

#Parse the results
../analyze/parse_trace.py "$SCRIPT_DIR/tmp/$FILENAME.txt" "$SCRIPT_DIR/tmp/${FILENAME}_pids.txt" "$FILENAME"
qsv join --full pid tmp/workload_times_"$FILENAME".csv pid tmp/"$FILENAME"_timings.csv | \
qsv select pid,arg,start_time,startup_latency,exit_time,migrations,request_time,return_time,duration > tmp/joined_workload_times_"$FILENAME".csv
mv tmp/joined_workload_times_"$FILENAME".csv tmp/workload_times_"$FILENAME".csv
mv workload_events.out tmp/workload_events_"$FILENAME".out

#Move to the log directory
cp tmp/workload_times_"$FILENAME".csv ../log/per_proc_times
cp tmp/"$FILENAME"_cpu_util.csv ../log/cpu_util
