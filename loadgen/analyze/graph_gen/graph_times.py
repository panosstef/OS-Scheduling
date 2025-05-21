#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import sys
import os

from colorama import Fore, Style


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_data(file_path):
	try:
		data = pd.read_csv(file_path)
		return data, os.path.basename(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, os.path.basename(file_path)


def calculate_timing_metrics(df):
	df.rename(columns={"startup_latency": "response_time"}, inplace=True)
	df['execution_time'] = df['exit_time'] - df['start_time']- df['response_time']
	df['turnaround_time'] = df['exit_time'] - df['start_time']
	df.drop(columns=['start_time', 'exit_time', 'arg'], inplace=True)
	df.set_index('pid', inplace=True)
	return df


def analyze_data(d1, d2):
	cols = ['response_time', 'execution_time', 'turnaround_time']
	# Convert duration list to seconds
	dur_list_ms = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 839, 1347, 2175, 3512, 5673, 9172]
	dur_list_sec = [x / 1000 for x in dur_list_ms]

	for col in cols:
		plt.figure(figsize=(15, 10), dpi=300)
		for (df, label) in [d1, d2]:
			data = np.sort(df[col].values)
			cdf = np.arange(1, len(data)+1) / len(data)
			plt.plot(data, cdf, label=label)
		plt.title(f'Cumulative Distribution Function - {col}')
		plt.xlabel(f"{col}	(s)")
		plt.ylabel('CDF')
		plt.legend()
		plt.grid(True)

		if col == 'turnaround_time (s)' or col == 'execution_time (s)':
			for x in dur_list_sec:
				plt.axvline(x=x, color='gray', linestyle='--', linewidth=0.8)

		plt.tight_layout()
		plt.savefig(f"CDF_{col}.png")
		plt.close()
		printr(f"Saved CDF plot for {col} as CDF_{col}.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV timing data files. Calculate response, execution, turnaround and total time.')
	parser.add_argument('file1', help='Path to the first CSV file')
	parser.add_argument('file2', help='Path to the second CSV file')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	(df1, name1) = load_data(args.file1)
	(df2, name2) = load_data(args.file2)

	# Check if data was loaded successfully
	if df1 is None or df2 is None:
		printr("Failed to load one or both files. Exiting.")
		sys.exit(1)

	# Calculate additional timing metrics
	df1 = calculate_timing_metrics(df1)
	df2 = calculate_timing_metrics(df2)

	# Analyze the data
	analyze_data((df1, name1), (df2, name2))



if __name__ == "__main__":
	main()
