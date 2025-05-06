#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import sys
from colorama import Fore, Style


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_data(file_path):
	try:
		data = pd.read_csv(file_path)
		return data
	except Exception as e:
		printr(f"Error loading {file_path}: {e}")
		return None


def calculate_timing_metrics(df):
	df['response_time'] = df['startup_latency'] / 1e6
	df['execution_time'] = df['exit_time'] - df['start_time']- df['response_time']
	df['turnaround_time'] = df['exit_time'] - df['start_time']
	df.drop(columns=['startup_latency', 'start_time', 'exit_time'], inplace=True)
	df.set_index('pid', inplace=True)
	return df


def analyze_data(df1, df2):

	cols = ['response_time', 'execution_time', 'turnaround_time']

	for col in cols:
		plt.figure()
		for df, label in zip([df1, df2], ['CFS', 'EEVDF']):
			data = np.sort(df[col].values)
			cdf = np.arange(1, len(data)+1) / len(data)
			plt.plot(data, cdf, label=label)
		plt.title(f'Cumulative Distribution Function - {col}')
		plt.xlabel(col)
		plt.ylabel('CDF')
		plt.legend()
		plt.grid(True)
		plt.tight_layout()
		plt.savefig(f"cfs_eevdf_{col}.png")
		plt.close()
		printr(f"Saved CDF plot for {col} as cfs_eevdf_latencies.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV timing data files. Calculate response, execution, turnaround and total time.')
	parser.add_argument('file1', help='Path to the first CSV file')
	parser.add_argument('file2', help='Path to the second CSV file')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	df1 = load_data(args.file1)
	df2 = load_data(args.file2)

	# Check if data was loaded successfully
	if df1 is None or df2 is None:
		printr("Failed to load one or both files. Exiting.")
		sys.exit(1)

	# Calculate additional timing metrics
	df1 = calculate_timing_metrics(df1)
	df2 = calculate_timing_metrics(df2)

	# Analyze the data
	analyze_data(df1, df2)



if __name__ == "__main__":
	main()
