#!/bin/bash

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

./capture/trace-cmd.sh --output "$SCRIPT_DIR/tmp/$FILENAME.dat" ./exec_workload.py --outputfile $FILENAME --main-cpu 0 --child-cpus 1-23

#Analyze the trace file
trace-cmd report -R -t -w --ts-check -i "$SCRIPT_DIR/tmp/$FILENAME.dat" > "$SCRIPT_DIR/tmp/$FILENAME.txt"

#Parse the results
analyze/parse_trace.py "$SCRIPT_DIR/tmp/$FILENAME.txt" "$SCRIPT_DIR/tmp/${FILENAME}_pids.txt" "$FILENAME"