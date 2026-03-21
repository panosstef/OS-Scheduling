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
	'font.size': 16,
	'axes.titlesize': 20,
	'axes.labelsize': 18,
	'xtick.labelsize': 16,
	'ytick.labelsize': 16,
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

# Function duration mappings (in milliseconds)
# dur_list = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 1347, 2175, 3512, 5673, 9172, 14835]
# fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
dur_list = [3, 3, 4, 4, 5, 7, 9, 14, 20, 31, 49, 77, 124, 198, 319, 515, 831, 1342, 2172, 3508, 5678, 9178, 14855]
fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]

# Create mapping from fib argument to duration
FIB_DURATION_MAP = {fib[i]: dur_list[i] for i in range(len(fib))}


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
		printr(f"Error loading {file_path}: {e}")
		return None, format_label(file_path)


def calculate_rte(df):
	"""
	Calculate Runtime Throughput Efficiency (RTE).
	RTE = Expected function duration / Actual execution duration
	"""
	rte_values = []
	invalid_count = 0

	for idx, row in df.iterrows():
		arg = int(row['arg'])
		# Duration in CSV is in seconds, convert to ms
		actual_duration_ms = row['duration'] * 1000

		# Look up expected duration for this fib argument
		if arg in FIB_DURATION_MAP:
			expected_duration_ms = FIB_DURATION_MAP[arg]
			rte = expected_duration_ms / actual_duration_ms
			rte_values.append(rte)
		else:
			invalid_count += 1

	if invalid_count > 0:
		print(f"  Warning: {invalid_count} rows had invalid fib arguments")

	rte_array = np.array(rte_values)
	# Cap the maximum value at 1.0, leave the minimum unbounded
	rte_array = np.clip(rte_array, a_min=None, a_max=1.0)
	return rte_array


def plot_rte_cdf(*datasets):
	"""Generate CDF plot for Runtime Throughput Efficiency."""
	plt.figure(figsize=(14, 9), dpi=300)

	# Store stats for comparison
	stats = {}
	load_numbers = set()
	for i, (df, label) in enumerate(datasets):
		rte_data = calculate_rte(df)
		if len(rte_data) == 0:
			printr(f"  No valid data for {label}")
			continue

		# Handle duplicate labels
		original_label = label
		idx = 1
		while label in stats:
			idx += 1
			label = f"{original_label} ({idx})"

		stats[label] = {'data': rte_data, 'color': None}
		# Extract load number from label (e.g., "EEVDF (50% load)" -> "50")
		import re
		match = re.search(r'(\d+)%', label)
		if match:
			load_numbers.add(match.group(1))

# Plot CDFs and store colors
	for i, label in enumerate(stats.keys()):
		# FIX: Sort the data before doing anything else
		data = np.sort(stats[label]['data'])

		p50 = np.percentile(data, 50)
		mean_val = np.mean(data)

		cdf = np.arange(1, len(data)+1) / len(data)
		lines = plt.plot(data, cdf, marker='o', markersize=1, alpha=0.7,
						label=f"{label} (Med={p50:.2f})")
		color = lines[0].get_color()
		stats[label]['color'] = color
		stats[label]['p50'] = p50
		stats[label]['mean'] = mean_val

		# Y offset for each dataset to avoid overlapping
		y_offset_median = 0.85 - i * 0.12

		# Plot median line
		plt.axvline(x=p50, color=color, linestyle=':', alpha=0.5)
		plt.text(p50, y_offset_median, f'Med: {p50:.2f}', color=color,
				ha='right', va='center', fontsize=11, bbox=dict(boxstyle='round,pad=0.3',
				facecolor='white', alpha=0.7))

	plt.title(f'CDF - Runtime Efficiency (RTE) - Load: {", ".join(sorted(load_numbers))}%', fontsize=24, pad=20, fontweight='bold')
	plt.xlabel('RTE (Expected Duration / Actual Duration)', fontsize=18)
	plt.ylabel('CDF', fontsize=18)
	plt.xscale('log')
	plt.grid(True, alpha=0.3)
	plt.legend(loc='upper left', fontsize=14, framealpha=0.95, edgecolor='black', title_fontsize=15)
	plt.tight_layout()
	plt.savefig("figures/rte_cdf.png")
	plt.close()
	printc("Saved RTE CDF plot as figures/rte_cdf.png")

	# Print statistics table
	print("\n" + "="*80)
	printc("RTE Statistics Summary")
	print("="*80)
	for label in stats.keys():
		print(f"\n{label}:")
		print(f"  Mean:     {stats[label]['mean']:.4f}")
		print(f"  Median:   {stats[label]['p50']:.4f}")
		print(f"  Samples:  {len(stats[label]['data'])}")


def main():
	parser = argparse.ArgumentParser(description='Generate RTE CDF plots from workload timing logs')
	parser.add_argument('patterns', nargs='*', type=str, default=None,
					   help='Glob pattern(s) to match CSV files (e.g., ../../log/per_proc_times/*100*)')
	parser.add_argument('--pattern', type=str, default=None,
					   help='Alternative flag for glob pattern (overrides positional args)')
	parser.add_argument('--scheduler', type=str, default=None,
					   help='Filter by scheduler (e.g., eevdf, cfs, fifo, schedext, schedext_user)')
	parser.add_argument('--load', type=str, default=None,
					   help='Filter by load percentage (e.g., 50, 80, 100)')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
					   help='Glob patterns to exclude (matched against filename, e.g. "*fifo*" "*100*")')

	args = parser.parse_args()

	# Determine which pattern(s) to use
	if args.pattern:
		# If --pattern flag is provided, use that
		patterns = [args.pattern]
	elif args.patterns:
		# If positional arguments are provided, use those
		patterns = args.patterns
	else:
		# Default pattern
		patterns = ['workload_times_*.csv']

	# Find CSV files
	csv_files = []
	for pattern in patterns:
		csv_files.extend(glob.glob(pattern))

	if not csv_files:
		printr(f"No files matching pattern '{args.pattern}' found")
		sys.exit(1)

	# Filter files if needed
	if args.scheduler:
		csv_files = [f for f in csv_files if args.scheduler in f]
	if args.load:
		csv_files = [f for f in csv_files if f'_{args.load}.csv' in f]

	if args.exclude:
		before = len(csv_files)
		csv_files = [f for f in csv_files
					 if not any(fnmatch.fnmatch(os.path.basename(f), exc) for exc in args.exclude)]
		printc(f"Excluded {before - len(csv_files)} file(s) via --exclude patterns.")

	if not csv_files:
		printr(f"No files matching filters found")
		sys.exit(1)

	# Sort files for consistent ordering
	csv_files = sorted(csv_files)

	printc(f"Found {len(csv_files)} matching files")

	# Load all data
	datasets = []
	for file_path in csv_files:
		printc(f"Loading {os.path.basename(file_path)}...", color=Fore.YELLOW)
		data, label = load_data(file_path)
		if data is not None:
			datasets.append((data, label))

	if not datasets:
		printr("No data loaded successfully")
		sys.exit(1)

	# Generate plots
	plot_rte_cdf(*datasets)


if __name__ == '__main__':
	main()
