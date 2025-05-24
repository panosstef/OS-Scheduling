#!/bin/bash
[ "$EUID" -ne 0 ] && exec sudo "$0" "$@"
set -e

exit_function() {
	trap - EXIT ERR
	rm -rf "$SCRIPT_DIR/tmp" 2>/dev/null
}
trap exit_function EXIT ERR SIGINT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTNAME="$(hostname)"
HOSTNAME="${HOSTNAME:2}"
DATE="$(date +%d-%m-%Y_%H:%M)"
DEFAULT_FILENAME="${HOSTNAME}_${DATE}"

FILENAME="${1:-$DEFAULT_FILENAME}"

#Change open fd limit
ulimit -n 16384

#Run the script with tracing
rm -rf "$SCRIPT_DIR/tmp" 2>/dev/null
mkdir -p "$SCRIPT_DIR/tmp"
cd "$SCRIPT_DIR/tmp"

#Run the script with tracing and move data perf.data
echo "Running perf sched record"
perf sched record ../../exec_workload.py --outputfile "$SCRIPT_DIR/tmp/$FILENAME" --time_log

pids=$(awk '{print $1}' $FILENAME\_pids.txt | paste -sd,)

#Convert the perf.data file to a parsable format, timehist -p $pids filters only for the workload pids
# when running as such the -S option misbehaves and skips somes pids, so I run it without filtering and do the filtering
# in the parsing step (have to split the output on empty lines)s
echo "Converting perf.data to readable format"
perf sched latency -i perf.data -f -p > latency.txt
perf sched timehist -i perf.data -f -p $pids > timehist.txt
perf sched timehist -i perf.data -f -S > timehist_full.txt
awk 'BEGIN{RS=""; ORS="\n\n"; i=1} {if(i==2) print > "timehist_avg.txt"; else if(i>=3) print > "timehist_rest.txt"; i++}' timehist_full.txt
cat timehist_rest.txt >> gen_stats.txt

#Parse the results
echo "Parsing the results"
../../analyze/parse_perf/parse_perf_latency.py latency.txt $FILENAME\_pids.txt $FILENAME\_latencies.csv
../../analyze/parse_perf/parse_perf_timehist.py timehist.txt $FILENAME\_sch_latencies.csv
../../analyze/parse_perf/parse_perf_timehist_avg.py timehist_avg.txt $FILENAME\_sch_latencies_avg.csv

#Combine the results from the latency and timehist_avg
../../analyze/parse_perf/combine_stats_csvs.py $FILENAME\_latencies.csv $FILENAME\_sch_latencies_avg.csv -o $FILENAME\_stats.csv

#Move to the log directory
cp $FILENAME\_sch_latencies.csv ../../log/per_proc_sch_latencies/
cp $FILENAME\_stats.csv ../../log/per_proc_stats/
cp gen_stats.txt ../../log/stats_general/$FILENAME\_stats.txt