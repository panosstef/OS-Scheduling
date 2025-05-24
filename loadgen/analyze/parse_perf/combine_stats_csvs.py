#!/usr/bin/env python3
import pandas as pd
import argparse
import sys
from colorama import Fore, Style

def main():
	parser = argparse.ArgumentParser(description="Merge two CSVs on the 'pid' column.")
	parser.add_argument('file1', help="Path to first CSV file")
	parser.add_argument('file2', help="Path to second CSV file")
	parser.add_argument('-o', '--output', required=True, help="Output CSV filename")

	args = parser.parse_args()

	print(f"{Fore.CYAN}	Combining CSVs: {args.file1} and {args.file2}{Fore.RESET}")

	try:
		df1 = pd.read_csv(args.file1)
		df2 = pd.read_csv(args.file2)
	except Exception as e:
		print(f"{Fore.RED}	Error reading CSV files: {e}{Fore.RESET}")
		sys.exit(1)

	# Standardize column names, merge, save to output
	df1.rename(columns={'Pid': 'pid'}, inplace=True)

	#Check all pids exist in both files
	pids1 = set(df1['pid'])
	pids2 = set(df2['pid'])

	if pids1 != pids2:
		missing_in_file2 = pids1 - pids2
		missing_in_file1 = pids2 - pids1
		if missing_in_file2:
			print(f"{Fore.RED}	Error: PIDs {missing_in_file2} found in {args.file1} but not in {args.file2}{Fore.RESET}")
		if missing_in_file1:
			print(f"{Fore.RED}	Error: PIDs {missing_in_file1} found in {args.file2} but not in {args.file1}{Fore.RESET}")

	merged_df = pd.merge(df1, df2, on='pid', how='outer')
	cols = list(merged_df.columns)
	if 'comm' in cols:
		cols.insert(1, cols.pop(cols.index('comm')))
		merged_df = merged_df[cols]
	merged_df.to_csv(args.output, index=False)
	print(f"{Fore.CYAN}	Merged CSV saved as '{args.output}'{Fore.RESET}")

if __name__ == "__main__":
	main()
