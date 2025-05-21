#! /usr/bin/env python3
import pandas as pd
import re
import argparse
import os
from colorama import Fore, Style

cwd = os.path.dirname(os.path.realpath(__file__))


def parse_timehist_data(text):
	lines = text.strip().split('\n')

	data_lines = lines[2:]

	times = []
	cpus = []
	tasks = []
	pids = []
	wait_times = []
	sch_delays = []
	run_times = []

	pattern = re.compile(r'\s*(\d+\.\d+)\s+\[(\d+)\]\s+(\S+)\[(\d+)\]\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)')

	for line in data_lines:
		match = pattern.search(line)
		if match:
			times.append(float(match.group(1)))
			cpus.append(int(match.group(2)))
			tasks.append(match.group(3))
			pids.append(int(match.group(4)))
			wait_times.append(float(match.group(5)))
			sch_delays.append(float(match.group(6)))
			run_times.append(float(match.group(7)))

	df = pd.DataFrame({
		'Time': times,
		'CPU': cpus,
		'Task': tasks,
		'PID': pids,
		'Wait_time_ms': wait_times,
		'Sched_delay_ms': sch_delays,
		'Run_time_ms': run_times,
	})

	return df

def main():
	parser = argparse.ArgumentParser(description="Parse perf sched timehist output")
	parser.add_argument('timehist_file', type=str, help='timehist file contaning perf sched timehist data')
	parser.add_argument('output_file', type=str, help='output file')
	args = parser.parse_args()

	output_file = args.output_file if args.output_file.endswith('.csv') else f"{args.output_file}.csv"
	output_path = os.path.join(os.getcwd(), output_file)

	df = pd.DataFrame()
	with open(args.timehist_file, 'r') as f:
		df = parse_timehist_data(f.read())
		df.to_csv(output_path, index=False)
	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload sched latencies written to: {output_path}{Style.RESET_ALL}")


if __name__ == '__main__':
	main()
