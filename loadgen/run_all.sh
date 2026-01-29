#!/bin/bash
# Run all experiments for 20, 50, 80 and  100 scaling factors
set -e

# Parse arguments
FIFO_ARG=""
SCHED_EXT_ARG=""
name=""

while [[ $# -gt 0 ]]; do
	case $1 in
		--fifo)
			FIFO_ARG="--fifo"
			shift
			;;
		--sched_ext)
			SCHED_EXT_ARG="--sched_ext"
			shift
			;;
		--*)
			echo "Error: Unknown argument '$1'"
			echo "Valid arguments: --fifo, --sched_ext"
			exit 1
			;;
		*)
			# First positional argument is experiment name
			if [[ -z "$name" ]]; then
				name="$1"
			fi
			shift
			;;
	esac
done

if [ -z "$name" ]; then
	echo "Please provide a name for this experiment set."
	echo "Usage: $0 [--fifo|--sched_ext] <experiment_name>"
	exit 1
fi

downscale=("1700" "700" "500" "300")
scales=(20 50 80 100)

for i in {0..3}
do
	scale=${scales[$i]}
	echo "Running experiments for scale factor: $scale"
	echo "Experiment set name: ${name}_${scale}"
	dataset/gen_workload.py --downscale "${downscale[$i]}"
	./run_experiment.sh $FIFO_ARG $SCHED_EXT_ARG "${name}_${scale}"
done