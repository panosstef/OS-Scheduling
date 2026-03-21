#!/usr/bin/env python3
"""
Plot Context Switches and Avg Burst Runtime CDFs in a 2x2 grid
(rows = 80% / 100% load, columns = metric) for all schedulers.
No titles. Square subplots.

Usage:
    python graph_switches_burst.py [--data-dir DIR] [--output FILE] [--exclude PATTERN ...]
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import fnmatch
import os

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
	'schedext':      'sched_ext',
	'cfs':           'CFS',
	'eevdf':         'EEVDF',
	'fifo':          'FIFO',
}

SCHEDULER_COLORS = {
	'schedext_user': '#1f77b4',
	'schedext':      '#ff7f0e',
	'cfs':           '#2ca02c',
	'eevdf':         '#d62728',
	'fifo':          '#9467bd',
}

LOADS = ['80', '100']

METRICS = [
	('Switches',    'Context Switches',   'Count',        'log', 'linear'),
	('avg_run_ms',  'Avg Burst Runtime',  'Runtime (ms)', 'log', 'linear'),
]


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_dataset(data_dir: str, scheduler: str, load: str):
	filename = f"{scheduler}_{load}_stats.csv"
	path = os.path.join(data_dir, filename)
	if not os.path.exists(path):
		printr(f"File not found: {path}")
		return None
	try:
		return pd.read_csv(path, usecols=lambda c: c not in ['Max_delay_start_s', 'Max_delay_end_s'])
	except Exception as e:
		printr(f"Error loading {path}: {e}")
		return None


def plot_panel(ax, data_dir: str, load: str, col: str, xlabel: str,
               xscale: str, yscale: str, exclude: list):
	"""Plot one CDF panel for a given load and metric column."""
	any_plotted = False
	for sched, label in SCHEDULER_NAMES.items():
		filename = f"{sched}_{load}_stats.csv"
		if any(fnmatch.fnmatch(filename, pat) for pat in exclude):
			printc(f"Excluded: {filename}")
			continue
		df = load_dataset(data_dir, sched, load)
		if df is None or col not in df.columns:
			continue
		data = np.sort(df[col].dropna().values)
		if len(data) == 0:
			continue
		cdf = np.arange(1, len(data) + 1) / len(data)
		ax.plot(data, cdf,
				label=f"{label} ({load}% load)",
				color=SCHEDULER_COLORS.get(sched),
				alpha=0.85,
				linewidth=1.8)
		any_plotted = True

	ax.set_xlabel(xlabel)
	ax.set_ylabel('CDF')
	ax.set_xscale(xscale)
	ax.set_yscale(yscale)
	ax.legend()
	ax.grid(True, alpha=0.3)
	ax.set_aspect('auto')
	return any_plotted


def main():
	parser = argparse.ArgumentParser(
		description='Plot Context Switches and Avg Burst Runtime CDFs for 80% and 100% load.')
	parser.add_argument('--data-dir', default='../../log/per_proc_stats',
						help='Directory containing the per_proc_stats CSV files')
	parser.add_argument('--output', default='figures/switches_burst.png',
						help='Output figure path (default: figures/switches_burst.png)')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (matched against filename, e.g. "*fifo*")')
	args = parser.parse_args()

	data_dir = os.path.abspath(
		os.path.join(os.path.dirname(__file__), args.data_dir)
		if not os.path.isabs(args.data_dir) else args.data_dir
	)

	# 2 rows (loads) x 2 cols (metrics), square subplots
	fig, axes = plt.subplots(2, 2, figsize=(12, 12), dpi=300)

	panel_labels = [['(a)', '(b)'], ['(c)', '(d)']]

	for row, load in enumerate(LOADS):
		for col_idx, (col, title, xlabel, xscale, yscale) in enumerate(METRICS):
			ax = axes[row][col_idx]
			ok = plot_panel(ax, data_dir, load, col, xlabel, xscale, yscale, args.exclude)
			if not ok:
				printr(f"No data plotted for {load}% load, {col}.")

			# Panel letter label (top-left corner)
			ax.text(0.02, 0.98, panel_labels[row][col_idx],
					transform=ax.transAxes, fontsize=14, fontweight='bold',
					va='top', ha='left')

			# Load annotation (top-right corner)
			ax.text(0.98, 0.98, f'{load}% load',
					transform=ax.transAxes, fontsize=12,
					va='top', ha='right',
					bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7, ec='grey'))

			# CDF y-label only on left panels
			if col_idx == 0:
				ax.set_ylabel('CDF')

			# Column header only on top row
			if row == 0:
				ax.set_title(title)

	plt.tight_layout()

	out_path = args.output
	os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
	plt.savefig(out_path, bbox_inches='tight')
	plt.close()
	printc(f"Saved figure to {out_path}")


if __name__ == '__main__':
	main()
