#! /usr/bin/env python3
import pandas as pd
import re
import argparse
import os
from colorama import Fore, Style

cwd = os.path.dirname(os.path.realpath(__file__))


def parse_timehist_avg_data(text):
	data_lines = text.strip().split('\n')[4:]

	comms = []
	pids = []
	sched_ins = []
	min_runs = []
	avg_runs = []
	max_runs = []
	migrations = []

	pattern = re.compile(
		r'\s*(\w+)\[(\d+)\]\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)'
	)

	for line in data_lines:
		match = pattern.search(line)
		if match and match.group(1) == 'launch_function':
			comms.append(match.group(1))
			pids.append(int(match.group(2)))
			sched_ins.append(int(match.group(4)))
			min_runs.append(float(match.group(6)))
			avg_runs.append(float(match.group(7)))
			max_runs.append(float(match.group(8)))
			migrations.append(int(match.group(10)))

	df = pd.DataFrame({
		'comm': comms,
		'pid': pids,
		'sched_in_count': sched_ins,
		'min_run_ms': min_runs,
		'avg_run_ms': avg_runs,
		'max_run_ms': max_runs,
		'migrations': migrations
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
		df = parse_timehist_avg_data(f.read())
		df.to_csv(output_path, index=False)
	print(f"{Fore.CYAN}	Workload sched latencies written to: {output_path}{Style.RESET_ALL}")


if __name__ == '__main__':
	main()
