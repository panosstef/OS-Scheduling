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
		data = pd.read_csv(file_path, usecols=lambda col: col not in ['Max_delay_start_s', 'Max_delay_end_s'])
		return data, format_label(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, format_label(file_path)

def analyze_stats_data(*datasets):
	# Group related metrics together
	metric_groups = [
		(['Runtime_s'], 'Total Runtime', 'runtime (s)', 'log', 'linear'),
		(['Switches'], 'Context Switches', 'Count', 'log', 'linear'),
		(['Avg_delay_ms', ], 'Avg Scheduling Delays', 'scheduling delay (ms)', 'log', 'linear'),
		# (['Max_delay_ms'], 'Max Scheduling Delay', 'max scheduling delay (ms)', 'log', 'logit'),
		# (['sched_in_count'], 'Schedule-in Count', 'Count', 'linear', 'linear'),
		# (['min_run_ms'], 'Min Burst Runtime', 'runtime (ms)', 'log', 'logit'),
		(['avg_run_ms'], 'Avg Burst Runtime', 'runtime (ms)', 'log', 'linear'),
		# (['max_run_ms'], 'Max Burst Runtime', 'runtime (ms)', 'log', 'logit'),
	]

	# Create subplots
	fig, axes = plt.subplots(2, 3, figsize=(20, 12), dpi=300)
	axes = axes.flatten()

	for idx, (cols, title, xlabel, xscale, yscale) in enumerate(metric_groups):
		ax = axes[idx]

		for col in cols:
			for i, (df, label) in enumerate(datasets):
				if col in df.columns:
					data = np.sort(df[col].values)
					cdf = np.arange(1, len(data)+1) / len(data)

					# Calculate p99 for display
					p99 = np.percentile(data, 99)

					# Add p99 to label for Avg_delay_ms specifically
					if col == 'Avg_delay_ms':
						line_label = f"{label} (P99={p99:.2f} ms)" if len(cols) == 1 else f"{label} - {col} (P99={p99:.2f})"
					else:
						line_label = f"{label} - {col}" if len(cols) > 1 else label

					lines = ax.plot(data, cdf, label=line_label)

					# Add p99 vertical line and text annotation for Avg_delay_ms
					if col == 'Avg_delay_ms':
						ax.axvline(x=p99, color=lines[0].get_color(), linestyle='--', alpha=0.5)
						ax.text(p99, 0.05 + i * 0.15, f'{p99:.2f}', color=lines[0].get_color(),
							   rotation=90, ha='right', va='bottom', fontsize=10)

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
