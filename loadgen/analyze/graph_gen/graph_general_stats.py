#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import sys
import os
import re

from colorama import Fore, Style


def printc(*args, color=Fore.CYAN, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def printr(*args, color=Fore.RED, **kwargs):
	print(f"{color}{' '.join(map(str, args))}{Style.RESET_ALL}", **kwargs)


def load_data(file_path):
	try:
		with open(file_path, 'r') as f:
			content = f.read()
		return content, os.path.basename(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, os.path.basename(file_path)


def parse_general_stats(content):
	"""Parse the general stats text file and extract metrics."""
	lines = content.strip().split('\n')

	stats = {}

	# Extract total runtime
	runtime_match = re.search(r'(\d+\.\d+)\s+s$', lines[0])
	if runtime_match:
		stats['total_runtime'] = float(runtime_match.group(1))

	# Get workload size - fix the variable name bug
	if len(lines) > 1 and lines[1].startswith("total_workload_size:"):
		stats['total_workload_size'] = int(lines[1].split(":")[1].strip())

	# Parse idle stats
	cpu_idle_data = {}
	in_idle_section = False

	for line in lines:
		if 'Idle stats:' in line:
			in_idle_section = True
			continue

		if in_idle_section and 'CPU' in line:
			# Parse CPU idle line: "    CPU  0 idle for   3863.895  msec  (  0.73%)"
			cpu_match = re.search(r'CPU\s+(\d+)\s+idle\s+for\s+(\d+\.\d+)\s+msec\s+\(\s*(\d+\.\d+)%\)', line)
			if cpu_match:
				cpu_num = int(cpu_match.group(1))
				idle_time_ms = float(cpu_match.group(2))
				idle_percent = float(cpu_match.group(3))
				if(cpu_num != 0):  # Skip CPU 0 if it's not relevant
					cpu_idle_data[cpu_num] = {
						'idle_time_ms': idle_time_ms,
						'idle_percent': idle_percent,
					}
		elif in_idle_section and line.strip() == '':
			in_idle_section = False
			continue

		# Parse additional metrics
		if 'Total number of context switches:' in line:
			switches_match = re.search(r'Total number of context switches:\s+(\d+)', line)
			if switches_match:
				stats['total_context_switches'] = int(switches_match.group(1))


	stats['cpu_idle_data'] = cpu_idle_data

	# Calculate aggregate metrics
	if cpu_idle_data:
		idle_times = [data['idle_time_ms'] for data in cpu_idle_data.values()]
		idle_percents = [data['idle_percent'] for data in cpu_idle_data.values()]

		stats['avg_idle_time_ms'] = np.mean(idle_times)
		stats['total_idle_time_ms'] = np.sum(idle_times)
		stats['avg_idle_percent'] = np.mean(idle_percents)
		stats['num_cpus'] = len(cpu_idle_data)

	return stats


def analyze_general_stats_data(*datasets, show_individual_cpu=False):
	"""Analyze and visualize general stats data."""

	# Extract data for plotting
	labels = []
	total_runtimes = []
	num_cpus_list = []
	context_switches = []
	total_idle_times = []
	workload_sizes = []

	for (stats, label) in datasets:
		labels.append(label)
		total_runtimes.append(stats.get('total_runtime', 0))
		num_cpus_list.append(stats.get('num_cpus', 0))
		context_switches.append(stats.get('total_context_switches', 0))
		total_idle_times.append(stats.get('total_idle_time_ms', 0))
		workload_sizes.append(stats.get('total_workload_size', 0))

	# Main plot with 3 metrics as subplots (2x2 but only use 3)
	fig, axes = plt.subplots(2, 2, figsize=(15, 15), dpi=300)

	# Total runtime
	colors = ['skyblue', 'lightcoral', 'lightgreen', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan'][:len(labels)]
	bars = axes[0,0].bar(labels, total_runtimes, color=colors, label=labels)
	axes[0,0].set_title('Total Runtime')
	axes[0,0].set_ylabel('Runtime (s)')
	axes[0,0].grid(True, alpha=0.3)
	axes[0,0].tick_params(axis='x', rotation=45)
	axes[0,0].legend(loc='best')
	for bar, runtime in zip(bars, total_runtimes):
		axes[0,0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_runtimes)*0.01,
					   f'{runtime:.2f}s', ha='center', va='bottom')

	# Context switches
	bars = axes[0,1].bar(labels, context_switches, color=colors, label=labels)
	axes[0,1].set_title('Total Context Switches')
	axes[0,1].set_ylabel('Number of Context Switches')
	axes[0,1].grid(True, alpha=0.3)
	axes[0,1].tick_params(axis='x', rotation=45)
	axes[0,1].legend(loc='best')
	for bar, switches in zip(bars, context_switches):
		axes[0,1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(context_switches)*0.01,
					   f'{switches}', ha='center', va='bottom')

	# Total CPU idle time
	bars = axes[1,0].bar(labels, total_idle_times, color=colors)
	axes[1,0].set_title('Total CPU Idle Time')
	axes[1,0].set_ylabel('Idle Time (ms)')
	axes[1,0].grid(True, alpha=0.3)
	axes[1,0].tick_params(axis='x', rotation=45)
	for bar, idle_time in zip(bars, total_idle_times):
		axes[1,0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(total_idle_times)*0.01,
					   f'{idle_time:.0f} ms', ha='center', va='bottom')

	# Hide the fourth subplot
	axes[1,1].set_visible(False)

	# Add workload size as text annotation (should be same for all datasets)
	if workload_sizes and workload_sizes[0] > 0:
		fig.suptitle(f'General Statistics (Total Workload Size: {workload_sizes[0]} functions)', fontsize=16, y=0.98)

	plt.tight_layout()
	plt.subplots_adjust(top=0.94)
	plt.savefig("figures/general_stats.png", bbox_inches='tight')
	plt.close()
	printc("Saved general stats plot as general_stats.png")

	# Create separate individual CPU idle times plot if requested
	if show_individual_cpu:
		fig_cpu, ax_cpu = plt.subplots(figsize=(20, 8), dpi=300)

		all_cpu_nums = set()
		for i, (stats, label) in enumerate(datasets):
			cpu_idle_data = stats.get('cpu_idle_data', {})
			if cpu_idle_data:
				cpu_nums = sorted(cpu_idle_data.keys())
				all_cpu_nums.update(cpu_nums)
				idle_times = [cpu_idle_data[cpu]['idle_time_ms'] for cpu in cpu_nums]

				bar_width = 0.8 / len(datasets)  # Adjust bar width based on number of datasets
				x_offset = i * bar_width - (len(datasets) - 1) * bar_width / 2
				x_positions = [cpu + x_offset for cpu in cpu_nums]

				ax_cpu.bar(x_positions, idle_times, width=bar_width, label=label, color=colors[i])

		ax_cpu.set_title('Individual CPU Idle Times')
		ax_cpu.set_xlabel('CPU Number')
		ax_cpu.set_ylabel('Idle Time (ms)')
		ax_cpu.legend()
		ax_cpu.grid(True, alpha=0.3)

		# Set x-axis ticks to show CPU numbers
		if all_cpu_nums:
			ax_cpu.set_xticks(sorted(all_cpu_nums))
			ax_cpu.set_xticklabels([f'{cpu}' for cpu in sorted(all_cpu_nums)])

		# Add workload size as text annotation
		if workload_sizes and workload_sizes[0] > 0:
			fig_cpu.suptitle(f'Individual CPU Idle Times (Total Workload Size: {workload_sizes[0]} functions)', fontsize=14)

		plt.tight_layout()
		plt.savefig("figures/individual_cpu_idle.png", bbox_inches='tight')
		plt.close()
		printc("Saved individual CPU idle times plot as individual_cpu_idle.png")


def main():
	parser = argparse.ArgumentParser(
		description='Process general stats text files and generate comparison plots.')
	parser.add_argument('files', nargs='+', help='Paths to text files to process')
	parser.add_argument('--indiv_cpu', action='store_true',
						help='Generate separate individual CPU idle times plot')
	args = parser.parse_args()

	datasets = []
	for file_path in args.files:
		content, name = load_data(file_path)
		if content is not None:
			stats = parse_general_stats(content)
			datasets.append((stats, name))
		else:
			printr(f"Failed to load {file_path}")

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(-1)

	analyze_general_stats_data(*datasets, show_individual_cpu=args.indiv_cpu)


if __name__ == "__main__":
	main()
