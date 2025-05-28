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

#Run the script with tracing
rm -rf "$SCRIPT_DIR/tmp" 2>/dev/null
mkdir -p "$SCRIPT_DIR/tmp"

#Run the script with tracing
echo -e "\nRunning ftrace experiment with filename: $FILENAME"
../capture/trace-cmd.sh --output "$SCRIPT_DIR/tmp/$FILENAME.dat" ../exec_workload.py --outputfile "$SCRIPT_DIR/tmp/$FILENAME" --cpu_log

#Analyze the trace file
trace-cmd report -R -t -w --ts-check -i "$SCRIPT_DIR/tmp/$FILENAME.dat" > "$SCRIPT_DIR/tmp/$FILENAME.txt"

#Parse the results
../analyze/parse_trace.py "$SCRIPT_DIR/tmp/$FILENAME.txt" "$SCRIPT_DIR/tmp/${FILENAME}_pids.txt" "$FILENAME"

#Move to the log directory
cp tmp/workload_times_"$FILENAME".csv ../log/per_proc_times
cp tmp/"$FILENAME"_cpu_util.csv ../log/cpu_util
