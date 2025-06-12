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
	df['response_time'] = df['response_time'].astype(float) * 1e3 # Convert to milliseconds
	df.rename(columns={'migrations': 'load_balancing_migrations'}, inplace=True)
	df.drop(columns=['start_time', 'exit_time', 'arg'], inplace=True)
	df.set_index('pid', inplace=True)
	return df


def analyze_data(*datasets):
	cols = [('response_time', 'Response Time (ms)', 'log', 'linear'),
		 ('execution_time', 'Execution Time (s)', 'log', 'linear'),
		 ('turnaround_time', 'Turnaround Time (s)', 'log', 'linear'),
		 ('load_balancing_migrations', 'Migrations', 'linear', 'linear')]

	# Create subplots
	_, axes = plt.subplots(2, 2, figsize=(20, 12), dpi=300)

	for idx, (col, xlabel, xscale, yscale) in enumerate(cols):
		row, col_idx = divmod(idx, 2)
		ax = axes[row, col_idx]

		for (df, label) in datasets:
			data = np.sort(df[col].values)
			cdf = np.arange(1, len(data)+1) / len(data)
			ax.plot(data, cdf, label=label)

		ax.set_title(f'CDF - {col.replace("_", " ").title()}')
		ax.set_xlabel(xlabel)
		ax.set_xscale(xscale)
		ax.set_yscale(yscale)
		ax.set_ylabel('CDF')
		ax.legend()
		ax.grid(True, alpha=0.3)

	plt.tight_layout()
	plt.savefig("figures/per_proc_times.png")
	plt.close()
	printc("Saved combined timing CDF plots as per_proc_times.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV timing data files. Calculate response, execution, turnaround and total time.')
	parser.add_argument('files', nargs='+', help='Paths to CSV files to process')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	datasets = []
	for file_path in args.files:
		df, name = load_data(file_path)
		if df is not None:
			df = calculate_timing_metrics(df)
			datasets.append((df, name))
		else:
			printr(f"Failed to load {file_path}")

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(-1)

	# Analyze the data
	analyze_data(*datasets)



if __name__ == "__main__":
	main()
