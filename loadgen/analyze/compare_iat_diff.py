#!/usr/bin/env python3
"""
Enhanced script to compare IAT_diff files with outlier analysis and multiple visualizations
"""

import numpy as np
import matplotlib.pyplot as plt
import argparse
import os
import re
from pathlib import Path


def parse_iat_diff_file(filepath):
	"""
	Parse an IAT_diff file and extract the difference values

	Args:
		filepath: Path to the IAT_diff file

	Returns:
		numpy array of difference values
	"""
	differences = []

	with open(filepath, 'r') as f:
		for line in f:
			line = line.strip()
			if line and not line.startswith('#'):
				# Extract the numerical value using regex
				# Format: "24: 6.151199340820312e-05 (should be 0)"
				match = re.match(r'\d+:\s+([\d\.\-e]+)', line)
				if match:
					value = float(match.group(1))
					differences.append(value)

	return np.array(differences)


def calculate_cdf(data):
	"""
	Calculate CDF for given data

	Args:
		data: numpy array of values

	Returns:
		sorted_data, cdf_values
	"""
	sorted_data = np.sort(data)
	n = len(data)
	cdf_values = np.arange(1, n + 1) / n
	return sorted_data, cdf_values


def plot_cdf_comparison(files_data, output_dir="./", show_plot=True, save_plot=True):
	"""
	Create simple CDF comparison plot
	"""

	# Create a single figure
	fig, ax = plt.subplots(1, 1, figsize=(10, 6))

	colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']

	# CDF plot with log scale
	for i, (filename, data) in enumerate(files_data.items()):
		abs_data = np.abs(data)
		sorted_data, cdf_values = calculate_cdf(abs_data)
		clean_name = filename.replace('_iat_test_IAT_diff.txt', '').upper()
		ax.plot(sorted_data, cdf_values, label=clean_name, color=colors[i % len(colors)], linewidth=2)

	ax.set_xlabel('IAT Difference (% + absolute for zero-IAT cases)')
	ax.set_ylabel('Cumulative Probability')
	ax.set_title('CDF of IAT Differences')
	ax.grid(True, alpha=0.3)
	ax.legend()
	ax.set_xscale('log')

	plt.tight_layout()

	if save_plot:
		output_path = os.path.join(output_dir, 'iat_diff_cdf_comparison.png')
		plt.savefig(output_path, dpi=300, bbox_inches='tight')
		print(f"CDF plot saved to: {output_path}")

	if show_plot:
		plt.show()

	return fig


def print_detailed_statistics(files_data):
	"""
	Print detailed statistical summary for each file
	"""
	print("\n" + "="*80)
	print("DETAILED STATISTICAL SUMMARY")
	print("="*80)

	for filename, data in files_data.items():
		clean_name = filename.replace('_iat_test_IAT_diff.txt', '').upper()
		abs_data = np.abs(data)

		print(f"\n{clean_name}:")
		print(f"  Total samples: {len(data):,}")
		print(f"  ")
		print(f"  RAW DATA STATISTICS:")
		print(f"    Mean absolute diff: {np.mean(abs_data):.6f} (% + absolute for zero-IAT cases)")
		print(f"    Median absolute diff: {np.median(abs_data):.6f} (% + absolute for zero-IAT cases)")
		print(f"    Std absolute diff: {np.std(abs_data):.6f} (% + absolute for zero-IAT cases)")
		print(f"    Min: {np.min(abs_data):.6f} (% + absolute for zero-IAT cases)")
		print(f"    Max: {np.max(abs_data):.6f} (% + absolute for zero-IAT cases)")
		print(f"  ")
		print(f"  PERCENTILES (raw data):")
		for p in [50, 75, 90, 95, 99, 99.9, 99.99]:
			print(f"    {p:5.1f}%: {np.percentile(abs_data, p):.6f} (% + absolute for zero-IAT cases)")


def main():
	parser = argparse.ArgumentParser(description='Enhanced IAT_diff comparison with outlier analysis')
	parser.add_argument('files', nargs='*', help='IAT_diff files to compare')
	parser.add_argument('--output-dir', '-o', default='./', help='Output directory for plots')
	parser.add_argument('--no-show', action='store_true', help='Don\'t display the plot')
	parser.add_argument('--no-save', action='store_true', help='Don\'t save the plot')
	parser.add_argument('--stats-only', action='store_true', help='Only print statistics')

	args = parser.parse_args()

	# If no files provided, search for IAT_diff files
	if not args.files:
		current_dir = Path('.')
		iat_files = list(current_dir.glob('*_iat_test_IAT_diff.txt'))
		if not iat_files:
			print("No IAT_diff files found.")
			return
		args.files = [str(f) for f in iat_files]

	# Parse files
	files_data = {}
	for filepath in args.files:
		if os.path.exists(filepath):
			try:
				data = parse_iat_diff_file(filepath)
				filename = os.path.basename(filepath)
				files_data[filename] = data
				print(f"Loaded {len(data):,} data points from {filename}")
			except Exception as e:
				print(f"Error parsing {filepath}: {e}")
		else:
			print(f"File not found: {filepath}")

	if not files_data:
		print("No valid data files found.")
		return

	# Print detailed statistics
	print_detailed_statistics(files_data)

	# Generate plots if requested
	if not args.stats_only:
		plot_cdf_comparison(
			files_data,
			output_dir=args.output_dir,
			show_plot=not args.no_show,
			save_plot=not args.no_save
		)


if __name__ == "__main__":
	main()
