#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import glob
import fnmatch
import sys
import os
import re

from colorama import Fore, Style

plt.rcParams.update({
	'font.size': 14,
	'axes.titlesize': 16,
	'axes.labelsize': 14,
	'xtick.labelsize': 12,
	'ytick.labelsize': 12,
	'legend.fontsize': 12,
	'legend.title_fontsize': 13,
})


SCHEDULER_NAMES = {
	'schedext_user': 'sched_ext (Userspace)',
	'schedext': 'sched_ext',
	'cfs': 'CFS',
	'eevdf': 'EEVDF',
	'fifo': 'FIFO',
}

SCHEDULER_COLORS = {
	'schedext_user': '#d62728',
	'schedext':      '#2ca02c',
	'cfs':           '#1f77b4',
	'eevdf':         '#ff7f0e',
	'fifo':          '#9467bd',
}

def get_color(label):
	label_lower = label.lower()
	if 'sched_ext (userspace)' in label_lower:
		return SCHEDULER_COLORS['schedext_user']
	elif 'sched_ext' in label_lower:
		return SCHEDULER_COLORS['schedext']
	elif 'cfs' in label_lower:
		return SCHEDULER_COLORS['cfs']
	elif 'eevdf' in label_lower:
		return SCHEDULER_COLORS['eevdf']
	elif 'fifo' in label_lower:
		return SCHEDULER_COLORS['fifo']
	return None


def format_label(file_path):
	"""Convert a raw filename into a thesis-quality label."""
	name = os.path.splitext(os.path.basename(file_path))[0]
	match = re.search(r'(schedext_user|schedext|cfs|eevdf|fifo)_(\d+)', name)
	if match:
		sched, load = match.group(1), match.group(2)
		return f"{SCHEDULER_NAMES.get(sched, sched)} ({load}% load)"
	return name


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_data(file_path):
	try:
		data = pd.read_csv(file_path)
		return data, format_label(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, format_label(file_path)


def analyze_latency_data(*datasets):
	cols = [('Wait_time_ms', 'Wait Time', 'Wait Time (ms)', 'log', 'linear'),
		 ('Sched_delay_ms', 'Scheduling Delay', 'Scheduling Delay (ms)', 'log', 'linear'),
		 ('Run_time_ms', 'Run Time', 'Run Time (ms)', 'log', 'linear')]

	# Create subplots for all CDFs
	fig, axes = plt.subplots(1, 3, figsize=(20, 6), dpi=300)

	for i, (col, name, xlabel, xscale, yscale) in enumerate(cols):
		ax = axes[i]
		for (df, label) in datasets:
			if col in df.columns and len(df) > 0:
				data = np.sort(df[col].values)
				cdf = np.arange(1, len(data)+1) / len(data)
				color = get_color(label)
				ax.plot(data, cdf, label=f"{label} (n={len(data)})", alpha=0.7, color=color)

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
		color = get_color(label)
		scatter = plt.scatter(df['Time'], df['Sched_delay_ms'],
				   label=label, alpha=0.6, s=4, color=color)
		plt.axhline(y=avg_sched_delay, linestyle='--', alpha=0.8, color = color,
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
	parser.add_argument('files', nargs='+', help='Paths or glob patterns to CSV files to process')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (matched against filename, e.g. "*fifo*" "*100*")')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.10f}'.format)

	files = []
	for pattern in args.files:
		matched = glob.glob(pattern, recursive=True)
		if matched:
			files.extend(sorted(matched))
		else:
			printr(f"No files matched pattern: {pattern}")

	if args.exclude:
		before = len(files)
		files = [f for f in files
				 if not any(fnmatch.fnmatch(os.path.basename(f), exc) for exc in args.exclude)]
		printc(f"Excluded {before - len(files)} file(s) via --exclude patterns.")

	datasets = []
	for file_path in files:
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
