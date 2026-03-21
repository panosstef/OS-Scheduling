#!/usr/bin/env python3
"""
Plot CDF of load balancing migrations from per_proc_times CSVs.

Usage:
    python graph_load_balancing_migrations.py <files_or_globs> [--exclude PATTERN ...] [--output PATH]

Examples:
    # All per_proc_times files
    python graph_load_balancing_migrations.py ../../log/per_proc_times/workload_times_*.csv

    # Only 80% load, exclude FIFO
    python graph_load_balancing_migrations.py ../../log/per_proc_times/*_80.csv --exclude "*fifo*"
"""
import argparse
import fnmatch
import glob
import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from colorama import Fore, Style

plt.rcParams.update({
	'font.size': 14,
	'axes.titlesize': 16,
	'axes.labelsize': 14,
	'xtick.labelsize': 12,
	'ytick.labelsize': 12,
	'legend.fontsize': 14,
	'legend.title_fontsize': 15,
})

SCHEDULER_NAMES = {
	'schedext_user': 'sched_ext (Userspace)',
	'schedext': 'sched_ext',
	'cfs': 'CFS',
	'eevdf': 'EEVDF',
	'fifo': 'FIFO',
}


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def format_label(file_path: str) -> str:
	name = os.path.splitext(os.path.basename(file_path))[0]
	match = re.search(r'workload_times_(schedext_user|schedext|cfs|eevdf|fifo)_(\d+)', name)
	if match:
		sched, load = match.group(1), match.group(2)
		return f"{SCHEDULER_NAMES.get(sched, sched)} ({load}% load)"
	return name


def load_dataset(file_path: str):
	try:
		return pd.read_csv(file_path)
	except Exception as e:
		printr(f"Error loading {file_path}: {e}")
		return None


def filter_nonpositive(data, label: str):
	data = data[np.isfinite(data)]
	positive = data[data > 0]
	if len(data) != len(positive):
		printr(f"Filtered {len(data) - len(positive)} non-positive values for {label} (log scale).")
	return positive


def plot_migrations(datasets, output_path: str, xscale: str):
	plt.figure(figsize=(12, 8), dpi=300)
	any_plotted = False

	for idx, (df, label) in enumerate(datasets):
		if 'migrations' not in df.columns:
			continue
		data = np.sort(df['migrations'].dropna().values)
		if xscale == 'log':
			data = filter_nonpositive(data, label)
		if len(data) == 0:
			continue
		cdf = np.arange(1, len(data) + 1) / len(data)
		p99 = np.percentile(data, 99)
		lines = plt.plot(data, cdf, marker='o', markersize=1, alpha=0.7,
						label=f"{label} (P99={p99:.2f})")
		plt.axvline(x=p99, color=lines[0].get_color(), linestyle='--', alpha=0.5)
		plt.text(p99, 0.5, f"{p99:.2f}",
				 color=lines[0].get_color(), rotation=90, ha='center', va='center',
				 fontsize=10, fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))
		any_plotted = True

	if not any_plotted:
		printr("No data plotted. Check your input files.")
		return False

	plt.title('CDF - Load Balancing Migrations')
	plt.xlabel('Migrations')
	plt.ylabel('CDF')
	if xscale == 'symlog':
		plt.xscale('symlog', linthresh=1)
	else:
		plt.xscale(xscale)
	plt.yscale('linear')
	plt.grid(True, alpha=0.3)
	plt.legend()
	plt.tight_layout()
	os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
	plt.savefig(output_path, bbox_inches='tight')
	plt.close()
	printc(f"Saved figure to {output_path}")
	return True


def main():
	parser = argparse.ArgumentParser(
		description='Plot CDF of load balancing migrations from per_proc_times CSVs.')
	parser.add_argument('files', nargs='+', help='Paths or glob patterns to per_proc_times CSV files')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (matched against filename, e.g. "*fifo*" "*100*")')
	parser.add_argument('--output', default='figures/load_balancing_migrations.png',
						help='Output figure path (default: figures/load_balancing_migrations.png)')
	parser.add_argument('--xscale', choices=['linear', 'log', 'symlog'], default='linear',
						help='X-axis scale (default: linear). Use symlog to include zeros.')
	args = parser.parse_args()

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

	if not files:
		printr("No files to process. Exiting.")
		sys.exit(1)

	datasets = []
	for file_path in files:
		df = load_dataset(file_path)
		if df is None:
			continue
		datasets.append((df, format_label(file_path)))

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(1)

	ok = plot_migrations(datasets, args.output, args.xscale)
	if not ok:
		sys.exit(1)


if __name__ == '__main__':
	main()
