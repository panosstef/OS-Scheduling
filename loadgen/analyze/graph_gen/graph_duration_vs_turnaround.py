#!/usr/bin/env python3
"""
Plot duration and turnaround time (exit_time - start_time) from per_proc_times CSVs
in the same plot as CDFs side-by-side for different loads or schedulers.

Usage:
    python graph_duration_vs_turnaround.py --data-dir <path/to/per_proc_times> [--scheduler SCHEDULER] [--load LOAD]

Examples:
    # Plot all schedulers for 80% load
    python graph_duration_vs_turnaround.py --data-dir ../../log/per_proc_times --load 80

    # Plot CFS across all loads
    python graph_duration_vs_turnaround.py --data-dir ../../log/per_proc_times --scheduler cfs

    # Plot all combinations
    python graph_duration_vs_turnaround.py --data-dir ../../log/per_proc_times
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import glob
import fnmatch
import os
import re
from pathlib import Path

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

# Fixed colour per scheduler so both panels share the same palette
SCHEDULER_COLORS = {
	'schedext_user': '#d62728',
	'schedext':      '#2ca02c',
	'cfs':           '#1f77b4',
	'eevdf':         '#ff7f0e',
	'fifo':          '#9467bd',
}


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_dataset(data_dir: str, scheduler: str, load: str):
	"""Load per_proc_times CSV for a scheduler and load."""
	filename = f"workload_times_{scheduler}_{load}.csv"
	path = os.path.join(data_dir, filename)
	if not os.path.exists(path):
		printr(f"File not found: {path}")
		return None
	try:
		df = pd.read_csv(path)
		return df
	except Exception as e:
		printr(f"Error loading {path}: {e}")
		return None


def compute_metrics(df):
	"""Compute duration and turnaround time (exit_time - start_time)."""
	df = df.copy()
	# duration already exists
	# turnaround time = exit_time - start_time
	if 'exit_time' in df.columns and 'start_time' in df.columns:
		df['turnaround_time'] = df['exit_time'] - df['start_time']
	return df


def filter_nonpositive(data, label: str):
	data = data[np.isfinite(data)]
	positive = data[data > 0]
	if len(data) != len(positive):
		printr(f"Filtered {len(data) - len(positive)} non-positive values for {label} (log scale).")
	return positive


def plot_panel(ax, data_dir: str, title: str, scheduler: str = None, load: str = None,
			  exclude: list = None, xscale: str = 'log'):
	"""
	Plot CDFs for duration and turnaround_time in the same axes.

	If scheduler is specified, plot that scheduler across loads.
	If load is specified, plot that load across schedulers.
	Otherwise, plot all combinations (will be one line per scheduler-load pair).
	"""
	exclude = exclude or []
	any_plotted = False

	# Set title
	ax.set_title(title)
	ax.set_xlabel('Time (s)')
	ax.set_ylabel('CDF')
	ax.set_xscale(xscale)

	# Collect all available scheduler-load combinations
	available_files = [f for f in os.listdir(data_dir) if f.startswith('workload_times_') and f.endswith('.csv')]

	if scheduler:
		# Filter by scheduler
		files_to_plot = [f for f in available_files if scheduler in f]
	elif load:
		# Filter by load
		files_to_plot = [f for f in available_files if f"_{load}.csv" in f]
	else:
		# Plot all
		files_to_plot = available_files

	# Apply exclude patterns
	if exclude:
		files_to_plot = [f for f in files_to_plot
						if not any(fnmatch.fnmatch(f, pat) for pat in exclude)]

	# Parse and plot each file
	for filename in sorted(files_to_plot):
		# Extract scheduler and load from filename
		match = re.search(r'workload_times_(.+?)_(\d+)\.csv', filename)
		if not match:
			continue
		sched, load_str = match.group(1), match.group(2)

		df = load_dataset(data_dir, sched, load_str)
		if df is None:
			continue

		df = compute_metrics(df)

		# Prepare label
		sched_label = SCHEDULER_NAMES.get(sched, sched)
		if scheduler:
			# Only scheduler specified, show load in legend
			label_prefix = f"{load_str}% load"
		elif load:
			# Only load specified, show scheduler in legend
			label_prefix = sched_label
		else:
			# Both, show both
			label_prefix = f"{sched_label} ({load_str}%)"

		color = SCHEDULER_COLORS.get(sched, None)

		# Plot duration
		if 'duration' in df.columns:
			data = np.sort(df['duration'].dropna().values)
			if xscale == 'log':
				data = filter_nonpositive(data, f"{label_prefix} - Duration")
			if len(data) > 0:
				cdf = np.arange(1, len(data) + 1) / len(data)
				ax.plot(data, cdf,
						label=f"{label_prefix} - Duration",
						color=color,
						alpha=0.85,
						linewidth=1.8,
						linestyle='-')
				any_plotted = True

		# Plot turnaround time
		if 'turnaround_time' in df.columns:
			data = np.sort(df['turnaround_time'].dropna().values)
			if xscale == 'log':
				data = filter_nonpositive(data, f"{label_prefix} - Turnaround")
			if len(data) > 0:
				cdf = np.arange(1, len(data) + 1) / len(data)
				ax.plot(data, cdf,
						label=f"{label_prefix} - Turnaround",
						color=color,
						alpha=0.85,
						linewidth=1.8,
						linestyle=':')
				any_plotted = True

	ax.legend(fontsize=14)
	ax.grid(True, alpha=0.3)
	return any_plotted


def main():
	parser = argparse.ArgumentParser(
		description='Plot duration and turnaround time (exit_time - start_time) from per_proc_times CSVs.')
	parser.add_argument('--data-dir', default='../../log/per_proc_times',
						help='Directory containing the per_proc_times CSV files '
							 '(default: ../../log/per_proc_times relative to this script)')
	parser.add_argument('--scheduler', default=None,
						help='Filter by scheduler (e.g., cfs, schedext, fifo). Shows all loads.')
	parser.add_argument('--load', default=None,
						help='Filter by load percentage (e.g., 80, 100). Shows all schedulers.')
	parser.add_argument('--output', default='figures/duration_vs_turnaround.png',
						help='Output figure path (default: figures/duration_vs_turnaround.png)')
	parser.add_argument('--xscale', choices=['linear', 'log', 'symlog'], default='log',
						help='X-axis scale (default: log). Use symlog to include zeros.')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (e.g., "*fifo*" "*100*")')
	args = parser.parse_args()

	data_dir = os.path.abspath(
		os.path.join(os.path.dirname(__file__), args.data_dir)
		if not os.path.isabs(args.data_dir) else args.data_dir
	)

	if not os.path.isdir(data_dir):
		printr(f"Data directory not found: {data_dir}")
		return

	# Determine plot layout
	if args.scheduler and args.load:
		# Single plot: specific scheduler and load
		fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
		title = f'{SCHEDULER_NAMES.get(args.scheduler, args.scheduler)} @ {args.load}% Load - ftrace vs simulator reported turnaround time'
		ok = plot_panel(ax, data_dir, title, scheduler=args.scheduler, load=args.load,
						exclude=args.exclude, xscale=args.xscale)
	elif args.scheduler:
		# Plot that scheduler across all loads
		fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
		title = f'{SCHEDULER_NAMES.get(args.scheduler, args.scheduler)} - All Loads - ftrace vs simulator reported turnaround time'
		ok = plot_panel(ax, data_dir, title, scheduler=args.scheduler, exclude=args.exclude,
						xscale=args.xscale)
	elif args.load:
		# Plot that load across all schedulers
		fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
		title = f'{args.load}% Load - ftrace vs simulator reported turnaround time'
		ok = plot_panel(ax, data_dir, title, load=args.load, exclude=args.exclude,
						xscale=args.xscale)
	else:
		# Plot all (may be busy)
		fig, ax = plt.subplots(figsize=(14, 10), dpi=300)
		title = 'ftrace vs simulator reported turnaround time - All Schedulers & Loads'
		ok = plot_panel(ax, data_dir, title, exclude=args.exclude, xscale=args.xscale)

	if not ok:
		printr(f"No data plotted. Check --data-dir and filter options.")
		return

	plt.tight_layout()
	os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
	plt.savefig(args.output, bbox_inches='tight')
	plt.close()
	printc(f"Saved figure to {args.output}")


if __name__ == '__main__':
	main()
