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


def analyze_latency_data(*datasets):
	cols = [('Wait_time_ms', 'Wait Time', 'Wait Time (ms)', 'log', 'linear'),
		 ('Sched_delay_ms', 'Scheduling Delay', 'Scheduling Delay (ms)', 'linear', 'logit'),
		 ('Run_time_ms', 'Burst CPU Run Time', 'Run Time (ms)', 'log', 'linear')]

	# Create subplots for all CDFs
	fig, axes = plt.subplots(1, 3, figsize=(35, 15), dpi=300)

	for i, (col, name, xlabel, xscale, yscale) in enumerate(cols):
		ax = axes[i]
		for (df, label) in datasets:
			if col in df.columns and len(df) > 0:
				data = np.sort(df[col].values)
				cdf = np.arange(1, len(data)+1) / len(data)
				ax.plot(data, cdf, label=f"{label} (n={len(data)})", alpha=0.7)

		ax.set_title(f'CDF - {name}')
		ax.set_xlabel(xlabel)
		ax.set_ylabel('CDF')
		ax.legend()
		ax.grid(True)
		ax.set_xscale(xscale)
		ax.set_yscale(yscale)

	plt.tight_layout()
	plt.savefig("figures/sched_latencies_statistics.png")
	plt.close()
	printc("Saved combined CDF plot as sched_latencies_statistics.png")

	# Time series plot of scheduling delays
	# Make timeseries start from 0 all of them
	plt.figure(figsize=(15, 8), dpi=300)
	for (df, label) in datasets:
		df['Time'] = df['Time'].apply(lambda x: round(x, 3))
		df['Time'] = df['Time'] - df['Time'].min()  # Normalize time to start from 0

		avg_sched_delay = df['Sched_delay_ms'].mean()
		scatter = plt.scatter(df['Time'], df['Sched_delay_ms'],
				   label=label, alpha=0.6, s=4)
		plt.axhline(y=avg_sched_delay, linestyle='--', alpha=0.8, color = scatter.get_facecolor()[0],
				   label=f'{label} avg ({avg_sched_delay:.2f} ms)')

	plt.title('Scheduling Delays Over Time')
	plt.xlabel('Time (s)')
	plt.ylabel('Scheduling Delay (ms)')
	plt.yscale('log')
	plt.legend(loc='upper right', fontsize='small')
	plt.grid(True, alpha=0.3)
	plt.tight_layout()
	plt.savefig("figures/timeseries_scheduling_delays.png")
	plt.close()
	printc("Saved time series plot as timeseries_scheduling_delays.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV scheduling latency data files and generate distribution plots.')
	parser.add_argument('files', nargs='+', help='Paths to CSV files to process')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	datasets = []
	for file_path in args.files:
		df, name = load_data(file_path)
		if df is not None:
			datasets.append((df, name))
		else:
			printr(f"Failed to load {file_path}")

	# Check if any data was loaded successfully
	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(1)

	analyze_latency_data(*datasets)


if __name__ == "__main__":
	main()
