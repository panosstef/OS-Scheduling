#!/usr/bin/env python3
"""
Plot Avg Scheduling Delay CDFs side-by-side for 80% and 100% CPU utilisation loads.
Usage:
    python graph_avg_delay_comparison.py --data-dir <path/to/per_proc_stats>
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

LOADS = ['80', '100']


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
		df = pd.read_csv(path, usecols=lambda c: c not in ['Max_delay_start_s', 'Max_delay_end_s'])
		return df
	except Exception as e:
		printr(f"Error loading {path}: {e}")
		return None


def plot_panel(ax, data_dir: str, load: str, exclude: list = None):
	"""Plot the Avg_delay_ms CDF for every scheduler into *ax*."""
	exclude = exclude or []
	any_plotted = False
	for sched, label in SCHEDULER_NAMES.items():
		filename = f"{sched}_{load}_stats.csv"
		if any(fnmatch.fnmatch(filename, pat) for pat in exclude):
			printc(f"Excluded: {filename}")
			continue
		df = load_dataset(data_dir, sched, load)
		if df is None or 'Avg_delay_ms' not in df.columns:
			continue
		data = np.sort(df['Avg_delay_ms'].dropna().values)
		if len(data) == 0:
			continue
		cdf = np.arange(1, len(data) + 1) / len(data)
		color = SCHEDULER_COLORS.get(sched)
		p99 = np.percentile(data, 99)
		ax.plot(data, cdf,
				label=f"{label} (p99={p99:.2f} ms)",
				color=color,
				alpha=0.85,
				linewidth=1.8)

		ax.axvline(p99, color=color, linestyle='--', linewidth=1.2, alpha=0.7)
		ax.text(p99, 0.5, f"{p99:.2f}", color=color, rotation=90, ha='center', va='center',
				fontsize=10, fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8, ec=color))
		any_plotted = True

	ax.set_title(f'Per Task Avg Scheduling Delay - {load}% Load', pad=5)
	ax.set_xlabel('Avg Scheduling Delay (ms)')
	ax.set_ylabel('CDF')
	ax.set_xscale('log')
	ax.set_yscale('linear')
	ax.legend()
	ax.grid(True, alpha=0.3)
	return any_plotted


def main():
	parser = argparse.ArgumentParser(description='Compare Avg Scheduling Delay CDFs for 80% vs 100% load.')
	parser.add_argument('--data-dir', default='../../log/per_proc_stats',
						help='Directory containing the per_proc_stats CSV files '
							 '(default: ../../log/per_proc_stats relative to this script)')
	parser.add_argument('--output', default='figures/avg_delay_comparison.png',
						help='Output figure path (default: figures/avg_delay_comparison.png)')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (matched against filename, e.g. "*fifo*" "*100*")')
	args = parser.parse_args()

	data_dir = os.path.abspath(
		os.path.join(os.path.dirname(__file__), args.data_dir)
		if not os.path.isabs(args.data_dir) else args.data_dir
	)

	# Split output path to handle multiple files (one per load)
	out_path = args.output
	os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
	base, ext = os.path.splitext(out_path)

	for load in LOADS:
		fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
		ok = plot_panel(ax, data_dir, load, exclude=args.exclude)
		if not ok:
			printr(f"No data plotted for {load}% load.")
			plt.close(fig)
			continue

		plt.tight_layout()
		current_out = f"{base}_{load}{ext}"
		plt.savefig(current_out, bbox_inches='tight')
		plt.close(fig)
		printc(f"Saved figure to {current_out}")


if __name__ == '__main__':
	main()
