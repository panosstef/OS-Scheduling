#!/bin/bash
[ "$EUID" -ne 0 ] && exec sudo "$0" "$@"
set -e

exit_function() {
	trap - EXIT ERR
	rm -rf "$SCRIPT_DIR/tmp" 2>/dev/null
	kill 0 2>/dev/null

}
trap exit_function EXIT ERR SIGINT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTNAME="$(hostname)"
HOSTNAME="${HOSTNAME:2}"
DATE="$(date +%d-%m-%Y_%H:%M)"
FILENAME="${HOSTNAME}_${DATE}"

#Change open fd limit
ulimit -n 16384

#Run the script with tracing
mkdir -p "$SCRIPT_DIR/tmp"
cd "$SCRIPT_DIR/tmp"

#Run the script with tracing and move data perf.data
perf sched record ../exec_workload.py --outputfile $FILENAME

pids=$(awk '{print $1}' $FILENAME\_pids.txt | paste -sd,)

#Convert the perf.data file to a parsable format
perf sched latency -i perf.data -f -p > latency.txt
perf sched timehist -i perf.data -f -p $pids> timehist.txt

#Parse the results
../analyze/parse_perf/parse_perf_latency.py latency.txt $FILENAME\_latencies.csv
../analyze/parse_perf/parse_perf_timehist.py timehist.txt $FILENAME\_sch_latencies.csv

#Move to the log directory
mv $FILENAME\_latencies.csv ../log/per_proc_latencies/
mv $FILENAME\_sch_latencies.csv ../log/sch_latencies/

