#! /usr/bin/env python3
import pandas as pd
import re
import argparse
import os
from colorama import Fore, Style

cwd = os.path.dirname(os.path.realpath(__file__))


def parse_latency_data(text):
	lines = text.strip().split('\n')

	data_lines = [
		line for line in lines if '|' in line and not line.startswith('---')]

	tasks = []
	runtimes = []
	switches = []
	avg_delays = []
	max_delays = []
	max_delay_starts = []
	max_delay_ends = []

	pattern = re.compile(
		r'\s*(.*?)\s*\|\s*([\d.]+)\s*ms\s*\|\s*(\d+)\s*\|'
		r'\s*avg:\s*([\d.]+)\s*ms\s*\|'
		r'\s*max:\s*([\d.]+)\s*ms\s*\|'
		r'\s*max start:\s*([\d.]+)\s*s\s*\|'
		r'\s*max end:\s*([\d.]+)\s*s'
	)

	for line in data_lines:
		match = pattern.search(line)
		if match:
			tasks.append(match.group(1).strip())
			runtimes.append(float(match.group(2)))
			switches.append(int(match.group(3)))
			avg_delays.append(float(match.group(4)))
			max_delays.append(float(match.group(5)))
			max_delay_starts.append(float(match.group(6)))
			max_delay_ends.append(float(match.group(7)))

	df = pd.DataFrame({
		'Task': tasks,
		'Runtime_ms': runtimes,
		'Switches': switches,
		'Avg_delay_ms': avg_delays,
		'Max_delay_ms': max_delays,
		'Max_delay_start_s': max_delay_starts,
		'Max_delay_end_s': max_delay_ends
	})

	# df = df[df['Task'].str.startswith("launch_function")]

	return df


def main():
	parser = argparse.ArgumentParser(description="Parse perf sched latency output")
	parser.add_argument('latencies_file', type=str, help='latency file contaning perf sched latency data')
	parser.add_argument('output_file', type=str, help='output file')
	args = parser.parse_args()

	output_file = args.output_file if args.output_file.endswith('.csv') else f"{args.output_file}.csv"
	output_path = os.path.join(os.getcwd(), output_file)

	df = pd.DataFrame()
	with open(args.latencies_file, 'r') as f:
		df = parse_latency_data(f.read())
		df.to_csv(output_path, index=False)
	print(f"{Fore.CYAN}{Style.BRIGHT}	Workload latencies written to: {output_path}{Style.RESET_ALL}")


if __name__ == '__main__':
	main()
