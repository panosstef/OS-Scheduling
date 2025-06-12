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
		data = pd.read_csv(file_path)
		return data, os.path.basename(file_path)
	except Exception as e:
		print(f"Error loading {file_path}: {e}")
		return None, os.path.basename(file_path)


def process_cpu_util_data(df):
	# Convert timestamp to relative time (starting from 0)
	df['timestamp'] = df['timestamp'] - df['timestamp'].iloc[0]

	# Calculate overall CPU utilization metrics
	cpu_cols = [col for col in df.columns if (col.startswith('cpu_') and col != 'cpu_0')]
	df['avg_cpu_util'] = df[cpu_cols].mean(axis=1)

	return df, cpu_cols


def analyze_cpu_util_data(*datasets):
	# Time series plots of overall CPU utilization
	plt.figure(figsize=(15, 10), dpi=300)
	for (df, cpu_cols, label) in datasets:
		plt.plot(df['timestamp'], df['avg_cpu_util'], label=label, linewidth=1.5)

	plt.title('CPU Utilization Over Time')
	plt.xlabel('Time (s)')
	plt.ylabel('CPU Utilization (%)')
	plt.legend()
	plt.grid(True, alpha=0.3)
	plt.ylim(0, 100)

	# Add more detailed x-axis ticks
	ax = plt.gca()
	ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=20))
	ax.xaxis.set_minor_locator(plt.MaxNLocator(nbins=100))
	plt.xticks(rotation=45)

	plt.tight_layout()
	plt.savefig("figures/timeseries_cpu_utilization.png")
	plt.close()
	printr("Saved time series plot as timeseries_cpu_utilization.png")

	# Heatmaps showing per-CPU utilization over time for all datasets
	if datasets:
		num_datasets = len(datasets)
		fig, axes = plt.subplots(num_datasets, 1, figsize=(20, 6 * num_datasets), dpi=300)

		# Handle single dataset case
		if num_datasets == 1:
			axes = [axes]

		for i, (df, cpu_cols, label) in enumerate(datasets):
			heatmap_data = df[cpu_cols].T

			im = axes[i].imshow(heatmap_data, aspect='auto', cmap='RdYlBu_r', vmin=0, vmax=100)
			cbar = plt.colorbar(im, ax=axes[i], label='CPU Utilization (%)')
			axes[i].set_title(f'CPU Utilization Heatmap - {label}')
			axes[i].set_xlabel('Time (s)')
			axes[i].set_ylabel('CPU Core')

			# Set x-axis to show actual timestamps
			num_ticks = min(10, len(df))  # Show up to 10 time labels
			tick_indices = np.linspace(0, len(df)-1, num_ticks, dtype=int)
			tick_labels = [f"{df['timestamp'].iloc[idx]:.1f}" for idx in tick_indices]
			axes[i].set_xticks(tick_indices)
			axes[i].set_xticklabels(tick_labels, rotation=45)

			# Set y-axis labels to show CPU numbers
			cpu_numbers = [col.replace('cpu_', '') for col in cpu_cols]
			axes[i].set_yticks(range(len(cpu_numbers)))
			axes[i].set_yticklabels(cpu_numbers)

		plt.tight_layout()
		plt.savefig("figures/heatmap_cpu_utilization.png")
		plt.close()
		printr("Saved all heatmaps as heatmap_cpu_utilization.png")

	# Statistical summary
	print("\n" + "="*50)
	printc("CPU Utilization Summary Statistics", color=Fore.GREEN)
	print("="*50)

	for (df, cpu_cols, label) in datasets:
		print(f"\n{label}:")
		print(f"  Average CPU Utilization: {df['avg_cpu_util'].mean():.2f}% ± {df['avg_cpu_util'].std():.2f}%")
		print(f"  Time at >95% utilization: {(df['avg_cpu_util'] > 95).sum() / len(df) * 100:.2f}%")
		print(f"  Time at <50% utilization: {(df['avg_cpu_util'] < 50).sum() / len(df) * 100:.2f}%")


def main():
	parser = argparse.ArgumentParser(
		description='Process CSV CPU utilization data files and generate utilization plots.')
	parser.add_argument('files', nargs='+', help='Paths to CSV files to process')
	args = parser.parse_args()
	pd.set_option('display.float_format', '{:.2f}'.format)

	datasets = []
	for file_path in args.files:
		df, name = load_data(file_path)
		if df is not None:
			df, cpu_cols = process_cpu_util_data(df)
			datasets.append((df, cpu_cols, name))
		else:
			printr(f"Failed to load {file_path}")

	if not datasets:
		printr("Failed to load any files. Exiting.")
		sys.exit(-1)

	# Analyze the data
	analyze_cpu_util_data(*datasets)


if __name__ == "__main__":
	main()
