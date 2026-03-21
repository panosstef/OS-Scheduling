#!/usr/bin/env python3
"""
graph_response_exec_times.py
Generates a 2x2 figure showing CDF of Response Time and Execution Time
split by load level (50% top row, 80% bottom row).

Usage:
    ./graph_response_exec_times.py ../../log/per_proc_times/*50* ../../log/per_proc_times/*80*
    ./graph_response_exec_times.py ../../log/per_proc_times/*.csv
"""

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
    'font.size': 20,
    'axes.titlesize': 22,
    'axes.labelsize': 20,
    'xtick.labelsize': 18,
    'ytick.labelsize': 18,
    'legend.fontsize': 16,
    'legend.title_fontsize': 17,
})

SCHEDULER_NAMES = {
    'schedext_user': 'sched_ext (Userspace)',
    'schedext': 'sched_ext',
    'cfs': 'CFS',
    'eevdf': 'EEVDF',
    'fifo': 'FIFO',
}


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
    df['execution_time'] = df['exit_time'] - df['start_time'] - df['response_time']
    df['response_time'] = df['response_time'].astype(float) * 1e3  # Convert to milliseconds
    if 'migrations' in df.columns:
        df.rename(columns={'migrations': 'load_balancing_migrations'}, inplace=True)
    df.set_index('pid', inplace=True)
    return df


def extract_load_pct(label):
    """Return the integer load percentage from a label like 'CFS (80% load)', or None."""
    m = re.search(r'\((\d+)%', label)
    return int(m.group(1)) if m else None


def short_label(label):
    """Strip the load group from the label for a cleaner legend entry."""
    return re.sub(r'\s*\(\d+%.*?\)', '', label).strip()


def plot_cdf_on_ax(ax, datasets, col, xlabel, xscale='log'):
    """Plot CDF lines for `col` from each (df, label) in datasets onto ax."""
    for i, (df, label) in enumerate(datasets):
        if col not in df.columns:
            printr(f"  Column '{col}' not found in dataset '{label}', skipping.")
            continue
        data = np.sort(df[col].dropna().values)
        if len(data) == 0:
            continue
        p99 = np.percentile(data, 99)
        cdf = np.arange(1, len(data) + 1) / len(data)
        lbl = short_label(label)
        lines = ax.plot(data, cdf, marker='o', markersize=1.5, alpha=0.75,
                        label=f"{lbl} (P99={p99:.2f})")
        color = lines[0].get_color()
        ax.axvline(x=p99, color=color, linestyle='--', alpha=0.4)
        ax.text(p99, 0.05 + i * 0.18, f'{p99:.2f}',
                color=color, rotation=90, ha='right', va='bottom', fontsize=10)

    ax.set_xlabel(xlabel)
    ax.set_xscale(xscale)
    ax.set_ylabel('CDF')
    ax.legend(loc='lower right')
    ax.grid(True, alpha=0.3)


def _load_label(load_pct):
    return f"{load_pct}% Load"


def plot_figure(datasets_50, datasets_80, load_50, load_80, output_path):
    """
    Plot response time and execution time CDFs.
    - Both load levels present  → 2x2 grid (top=load_50, bottom=load_80)
    - Only one load level       → 2x1 stack (response time top, execution time bottom)
    """
    has_50 = bool(datasets_50)
    has_80 = bool(datasets_80)
    both = has_50 and has_80

    if both:
        fig, axes = plt.subplots(2, 2, figsize=(20, 12), dpi=300)
        fig.suptitle('Response Time & Execution Time CDF by Load Level', fontsize=22, y=1.01)

        # ── Top row: load_50 ────────────────────────────────────────────────
        axes[0, 0].set_title(f'Response Time — {_load_label(load_50)}')
        plot_cdf_on_ax(axes[0, 0], datasets_50, 'response_time',
                       'Response Time (ms)', xscale='log')

        axes[0, 1].set_title(f'Execution Time — {_load_label(load_50)}')
        plot_cdf_on_ax(axes[0, 1], datasets_50, 'execution_time',
                       'Execution Time (s)', xscale='log')

        # ── Bottom row: load_80 ─────────────────────────────────────────────
        axes[1, 0].set_title(f'Response Time — {_load_label(load_80)}')
        plot_cdf_on_ax(axes[1, 0], datasets_80, 'response_time',
                       'Response Time (ms)', xscale='log')

        axes[1, 1].set_title(f'Execution Time — {_load_label(load_80)}')
        plot_cdf_on_ax(axes[1, 1], datasets_80, 'execution_time',
                       'Execution Time (s)', xscale='log')

        layout_desc = "2x2"

    else:
        # Single load level → 2x1 (stacked)
        datasets = datasets_50 if has_50 else datasets_80
        load_pct = load_50 if has_50 else load_80

        fig, axes = plt.subplots(2, 1, figsize=(12, 14), dpi=300)

        axes[0].set_title(f'Response Time — {_load_label(load_pct)}')
        plot_cdf_on_ax(axes[0], datasets, 'response_time',
                       'Response Time (ms)', xscale='log')

        axes[1].set_title(f'Execution Time — {_load_label(load_pct)}')
        plot_cdf_on_ax(axes[1], datasets, 'execution_time',
                       'Execution Time (s)', xscale='log')

        layout_desc = "2x1"

    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight')
    plt.close()
    printc(f"Saved {layout_desc} figure to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Generate a 2x2 figure with Response Time and Execution Time CDFs '
            'for 50%% (top row) and 80%% (bottom row) load levels.'
        )
    )
    parser.add_argument('files', nargs='+',
                        help='Paths or glob patterns to CSV files (per_proc_times logs)')
    parser.add_argument('--exclude', nargs='+', default=[], metavar='PATTERN',
                        help='Glob patterns to exclude (e.g. "*fifo*")')
    parser.add_argument('--load-50', type=int, default=None, metavar='N',
                        help='Load percentage to treat as first group (auto-detected if omitted)')
    parser.add_argument('--load-80', type=int, default=None, metavar='N',
                        help='Load percentage to treat as second group (auto-detected if omitted)')
    parser.add_argument('--output', default='figures/response_exec_times_2x2.png',
                        help='Output file path (default: figures/response_exec_times_2x2.png)')
    args = parser.parse_args()

    pd.set_option('display.float_format', '{:.10f}'.format)

    # ── Resolve files ────────────────────────────────────────────────────────
    files = []
    for pattern in args.files:
        matched = glob.glob(pattern, recursive=True)
        if matched:
            files.extend(sorted(matched))
        else:
            printr(f"No files matched pattern: {pattern}")

    if args.exclude:
        before = len(files)
        def _is_excluded(path):
            name = os.path.basename(path)
            for exc in args.exclude:
                # If the pattern has no glob chars, treat it as a substring match
                if not any(c in exc for c in ('*', '?', '[', ']')):
                    if exc in name:
                        return True
                elif fnmatch.fnmatch(name, exc):
                    return True
            return False
        files = [f for f in files if not _is_excluded(f)]
        printc(f"Excluded {before - len(files)} file(s) via --exclude patterns.")

    # ── Load & process ───────────────────────────────────────────────────────
    all_datasets = []
    for file_path in files:
        df, label = load_data(file_path)
        if df is not None:
            df = calculate_timing_metrics(df)
            all_datasets.append((df, label))
        else:
            printr(f"Failed to load {file_path}")

    if not all_datasets:
        printr("No data loaded. Exiting.")
        sys.exit(1)

    # ── Auto-detect load levels if not specified ────────────────────────────
    unique_loads = sorted(set(
        extract_load_pct(lbl) for _, lbl in all_datasets
        if extract_load_pct(lbl) is not None
    ))
    printc(f"Detected load levels: {unique_loads}")

    load_50 = args.load_50 if args.load_50 is not None else (unique_loads[0] if unique_loads else None)
    load_80 = args.load_80 if args.load_80 is not None else (unique_loads[1] if len(unique_loads) > 1 else None)

    # ── Split by load level ──────────────────────────────────────────────────
    datasets_50 = [(df, lbl) for df, lbl in all_datasets
                   if extract_load_pct(lbl) == load_50]
    datasets_80 = [(df, lbl) for df, lbl in all_datasets
                   if load_80 is not None and extract_load_pct(lbl) == load_80]

    if not datasets_50 and load_50 is not None:
        printr(f"No datasets found for {load_50}% load. "
               f"Check filenames or use --load-50 to override.")
    if not datasets_80 and load_80 is not None:
        printr(f"No datasets found for {load_80}% load. "
               f"Check filenames or use --load-80 to override.")

    if not datasets_50 and not datasets_80:
        printr("Nothing to plot. Exiting.")
        sys.exit(1)

    args.load_50 = load_50
    args.load_80 = load_80 if load_80 is not None else load_50

    printc(f"Group 1 ({args.load_50}% load): {[lbl for _, lbl in datasets_50]}")
    printc(f"Group 2 ({args.load_80}% load): {[lbl for _, lbl in datasets_80]}")

    # ── Ensure output directory exists ───────────────────────────────────────
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # ── Plot ─────────────────────────────────────────────────────────────────
    plot_figure(datasets_50, datasets_80, args.load_50, args.load_80, args.output)


if __name__ == "__main__":
    main()
