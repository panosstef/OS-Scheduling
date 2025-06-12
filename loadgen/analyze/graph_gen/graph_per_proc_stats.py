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
		data = pd.read_csv(file_path, usecols=lambda col: col not in ['Max_delay_start_s', 'Max_delay_end_s'])
		return data, os.path.basename(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, os.path.basename(file_path)

def analyze_stats_data(*datasets):
	# Group related metrics together
	metric_groups = [
		(['Runtime_s'], 'Total Runtime', 'runtime (s)', 'log', 'linear'),
		(['Switches'], 'Context Switches', 'Count', 'log', 'linear'),
		(['Avg_delay_ms', ], 'Avg Scheduling Delays', 'scheduling delay (ms)', 'log', 'logit'),
		# (['Max_delay_ms'], 'Max Scheduling Delay', 'max scheduling delay (ms)', 'log', 'logit'),
		# (['sched_in_count'], 'Schedule-in Count', 'Count', 'linear', 'linear'),
		# (['min_run_ms'], 'Min Burst Runtime', 'runtime (ms)', 'log', 'logit'),
		(['avg_run_ms'], 'Avg Burst Runtime', 'runtime (ms)', 'linear', 'logit'),
		# (['max_run_ms'], 'Max Burst Runtime', 'runtime (ms)', 'log', 'logit'),
	]

	# Create subplots
	fig, axes = plt.subplots(2, 3, figsize=(20, 12), dpi=300)
	axes = axes.flatten()

	for idx, (cols, title, xlabel, xscale, yscale) in enumerate(metric_groups):
		ax = axes[idx]

		for col in cols:
			for (df, label) in datasets:
				if col in df.columns:
					data = np.sort(df[col].values)
					cdf = np.arange(1, len(data)+1) / len(data)
					line_label = f"{label} - {col}" if len(cols) > 1 else label
					ax.plot(data, cdf, label=line_label)

		ax.set_title(f'CDF - {title}')
		ax.set_xlabel(xlabel)
		ax.set_ylabel('CDF')
		ax.legend()
		ax.grid(True, alpha=0.3)

		# Set scales based on metric group parameters
		ax.set_xscale(xscale)
		ax.set_yscale(yscale)

	# Hide unused subplots
	for idx in range(len(metric_groups), len(axes)):
		axes[idx].set_visible(False)

	plt.tight_layout()
	plt.savefig("figures/per_proc_statistics.png")
	plt.close()
	printc("Saved combined CDF plots as per_proc_statistics.png")

def main():
	parser = argparse.ArgumentParser(
		description='Process CSV stats data files and generate distribution plots.')
	parser.add_argument('files', nargs='+', help='Paths to CSV files to process')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	datasets = []
	for file_path in args.files:
		df, name = load_data(file_path)
		if df is not None:
			df["Runtime_s"] = df.pop("Runtime_ms") / 1000
			datasets.append((df, name))
		else:
			printr(f"Failed to load {file_path}")

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(-1)

	analyze_stats_data(*datasets)


if __name__ == "__main__":
	main()
