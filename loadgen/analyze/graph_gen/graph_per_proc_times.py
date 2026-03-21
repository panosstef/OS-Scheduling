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

		for i, (df, label) in enumerate(datasets):
			data = np.sort(df[col].values)
			if len(data) == 0:
				continue
			p99 = np.percentile(data, 99)
			cdf = np.arange(1, len(data)+1) / len(data)
			color = get_color(label)
			lines = ax.plot(data, cdf, marker='o', markersize=2, alpha=0.7, label=f"{label} (P99={p99:.2f})", color=color)
			ax.axvline(x=p99, color=lines[0].get_color(), linestyle='--', alpha=0.5)
			ax.text(p99, 0.05 + i * 0.20, f'{p99:.2f}', color=lines[0].get_color(), rotation=90, ha='right', va='bottom')

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


def plot_turnaround_times(datasets, draw_median=True):
	plt.figure(figsize=(12, 8), dpi=300)

	col = 'duration'
	xlabel = 'Turnaround Time (s)'

	# Store stats for comparison
	stats = {}
	for i, (df, label) in enumerate(datasets):
		if col not in df.columns:
			continue
		data = np.sort(df[col].values)
		if len(data) == 0:
			continue

		# Handle duplicate labels
		original_label = label
		idx = 1
		while label in stats:
			idx += 1
			label = f"{original_label} ({idx})"

		stats[label] = {'data': data, 'color': None}

	# Plot CDFs and store colors
	for i, label in enumerate(stats.keys()):
		data = stats[label]['data']
		p99 = np.percentile(data, 99)
		median = np.percentile(data, 50)
		cdf = np.arange(1, len(data)+1) / len(data)

		label_text = f"{label} (P99={p99:.2f}s"
		if draw_median:
			label_text += f", Med={median:.2f}s"
		label_text += ")"

		color = get_color(label)
		lines = plt.plot(data, cdf, marker='o', markersize=1, alpha=0.7,
						label=label_text, color=color)
		color = lines[0].get_color()
		stats[label]['color'] = color
		stats[label]['p99'] = p99
		stats[label]['median'] = median

		# Y offset for each dataset to avoid overlapping
		y_offset_p99 = 0.95 - i * 0.15
		y_offset_median = 0.90 - i * 0.15

		# Plot P99 line
		plt.axvline(x=p99, color=color, linestyle='--', alpha=0.5)
		plt.text(p99, y_offset_p99, 'P99:', color=color, ha='right', va='center', fontsize=11)
		plt.text(p99, y_offset_p99, f' {p99:.2f}', color=color, ha='left', va='center', fontsize=15)

		if draw_median:
			# Plot median line
			plt.axvline(x=median, color=color, linestyle=':', alpha=0.5)
			plt.text(median, y_offset_median, 'Med:', color=color, ha='right', va='center', fontsize=11)
			plt.text(median, y_offset_median, f' {median:.2f}', color=color, ha='left', va='center', fontsize=15)

	# Calculate and display comparison percentages
	if draw_median:
		sched_ext_stats = None
		comparison_text = [] # Ensure comparison_text is initialized or this block only runs if draw_median
		for label, stat in stats.items():
			if 'sched_ext' in label.lower():
				sched_ext_stats = stat
				break

		if sched_ext_stats:
			sched_ext_data = sched_ext_stats['data']
			for label, stat in stats.items():
				if 'sched_ext' not in label.lower():
					other_data = stat['data']
					# Calculate percentage of sched_ext < median of other
					pct_less_than_median = np.sum(sched_ext_data < stat['median']) / len(sched_ext_data) * 100
					comparison_text.append(f"{label}:\n  {pct_less_than_median:.1f}% of sched_ext < median")
		if comparison_text:
			textstr = '\n'.join(comparison_text)
			plt.text(0.02, 0.98, textstr, transform=plt.gca().transAxes, fontsize=12,
					verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

	plt.title('CDF - Turnaround Time')
	plt.xlabel(xlabel)
	plt.ylabel('CDF')
	plt.xscale('log')
	plt.yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0])
	plt.grid(True, alpha=0.3)
	plt.legend(loc='lower right', fontsize=12)

	plt.tight_layout()
	plt.savefig("figures/per_proc_turnaround_times.png")
	plt.close()
	printc("Saved turnaround time CDF plot as per_proc_turnaround_times.png")


def plot_turnaround_times_side_by_side(datasets, draw_median=True):
	"""Group datasets by load level and plot each group as a separate subplot."""
	# Group by load percentage extracted from the label, e.g. "CFS (80% load)" -> "80%"
	groups = {}
	for (df, label) in datasets:
		match = re.search(r'\((\d+)%', label)
		group_key = f"{match.group(1)}% load" if match else 'Other'
		groups.setdefault(group_key, []).append((df, label))

	group_keys = sorted(groups, key=lambda k: int(re.search(r'\d+', k).group()) if re.search(r'\d+', k) else 0)
	n = len(group_keys)

	if n == 0:
		printr("No groups found for side-by-side plot.")
		return

	fig, axes = plt.subplots(n, 1, figsize=(12, 8 * n), dpi=300, sharex=True)
	if n == 1:
		axes = [axes]

	col = 'duration'

	for ax, key in zip(axes, group_keys):
		# Store stats for this group
		stats = {}
		for i, (df, label) in enumerate(groups[key]):
			if col not in df.columns:
				continue
			data = np.sort(df[col].values)
			if len(data) == 0:
				continue

			# Handle duplicate labels
			original_label = label
			idx = 1
			while label in stats:
				idx += 1
				label = f"{original_label} ({idx})"

			stats[label] = {'data': data, 'color': None}

		# Plot CDFs and collect stats
		for i, label in enumerate(stats.keys()):
			data = stats[label]['data']
			p99 = np.percentile(data, 99)
			median = np.percentile(data, 50)
			cdf = np.arange(1, len(data)+1) / len(data)
			# Strip the load group from the label to avoid redundancy in the legend
			short_label = re.sub(r'\s*\(\d+%.*?\)', '', label).strip()

			label_text = f"{short_label} (P99={p99:.2f}s"
			if draw_median:
				label_text += f", Med={median:.2f}s"
			label_text += ")"

			color = get_color(label)
			lines = ax.plot(data, cdf, marker='o', markersize=1, alpha=0.7,
							label=label_text, color=color)
			color = lines[0].get_color()
			stats[label]['color'] = color
			stats[label]['p99'] = p99
			stats[label]['median'] = median

			# Plot lines for P99 and median
			# Y offset for each dataset to avoid overlapping
			y_offset_p99 = 0.95 - i * 0.15
			y_offset_median = 0.90 - i * 0.15

			ax.axvline(x=p99, color=color, linestyle='--', alpha=0.5)
			ax.text(p99, y_offset_p99, 'P99:', color=color, ha='right', va='center', fontsize=11)
			ax.text(p99, y_offset_p99, f' {p99:.2f}', color=color, ha='left', va='center', fontsize=15)

			if draw_median:
				ax.axvline(x=median, color=color, linestyle=':', alpha=0.5)
				ax.text(median, y_offset_median, 'Med:', color=color, ha='right', va='center', fontsize=11)
				ax.text(median, y_offset_median, f' {median:.2f}', color=color, ha='left', va='center', fontsize=15)

		# Calculate and display comparison percentages
		if draw_median:
			sched_ext_stats = None
			comparison_text = []
			for label, stat in stats.items():
				if 'sched_ext' in label.lower():
					sched_ext_stats = stat
					break

			if sched_ext_stats:
				sched_ext_data = sched_ext_stats['data']
				for label, stat in stats.items():
					if 'sched_ext' not in label.lower():
						other_data = stat['data']
						pct_less_than_median = np.sum(sched_ext_data < stat['median']) / len(sched_ext_data) * 100
						short_name = re.sub(r'\s*\(\d+%.*?\)', '', label).strip()
						comparison_text.append(f"{short_name}:\n  {pct_less_than_median:.1f}% of sched_ext < median")
			# Add comparison text box
			if comparison_text:
				textstr = '\n'.join(comparison_text)
				ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=11,
						verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

		ax.set_title(f'Turnaround Time CDF — {key}')
		ax.set_xlabel('Turnaround Time (s)')
		ax.set_xscale('log')
		ax.set_ylabel('CDF')
		ax.legend(loc='lower right', fontsize=11)
		ax.grid(True, alpha=0.3)

	plt.tight_layout()
	plt.savefig("figures/per_proc_turnaround_times_side_by_side.png")
	plt.close()
	printc("Saved side-by-side plot as per_proc_turnaround_times_side_by_side.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV timing data files. Calculate response, execution, turnaround and total time.')
	parser.add_argument('files', nargs='+', help='Paths or glob patterns to CSV files to process')
	parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
						help='Glob patterns to exclude (matched against filename, e.g. "*fifo*" "*100*")')
	parser.add_argument('--side-by-side', action='store_true',
						help='Plot turnaround times grouped by load level in side-by-side subplots')
	parser.add_argument('--no-median', action='store_true',
						help='Hide median values and their comparison')
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
			df = calculate_timing_metrics(df)
			datasets.append((df, name))
		else:
			printr(f"Failed to load {file_path}")

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(-1)

	# Analyze the data
	analyze_data(*datasets)
	if args.side_by_side:
		plot_turnaround_times_side_by_side(datasets, draw_median=not args.no_median)
	else:
		plot_turnaround_times(datasets, draw_median=not args.no_median)



if __name__ == "__main__":
	main()
