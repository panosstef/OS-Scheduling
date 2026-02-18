#!/usr/bin/env python3
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt

dur_df_list = []
days = [
    "01", "02", "03", "04", "05", "06", "07",
    "08", "09", "10", "11", "12", "13", "14",
]

__file = os.path.dirname(os.path.realpath(__file__))

# ---------------------------------------------------------
# 1. Load Two-Week Azure CDF
# ---------------------------------------------------------
for i in days:
    dur_filename = f"{__file}/trace/function_durations_percentiles.anon.d{i}.csv"
    dur_df = pd.read_csv(dur_filename)
    dur_df_list.append(dur_df)

duration_df = pd.concat(dur_df_list, axis=0, ignore_index=True).iloc[:, [3, 4]]
duration_df = duration_df[duration_df["Average"] > 0]
duration_df = duration_df.groupby("Average").sum().reset_index()

x_2weeks = list(duration_df["Average"] / 1000)
y_2weeks = list(duration_df["Count"])
p_2weeks = y_2weeks / np.sum(y_2weeks)
cdf_2weeks = np.cumsum(p_2weeks)


# ---------------------------------------------------------
# 2. Load First 2 Minutes Azure CDF (Day 01)
# ---------------------------------------------------------
durations_day01 = f"{__file}/trace/function_durations_percentiles.anon.d01.csv"
invoke_day01 = f"{__file}/trace/invocations_per_function_md.anon.d01.csv"

duration_01 = pd.read_csv(durations_day01).iloc[:, [2, 3]]
invoke_01 = pd.read_csv(invoke_day01).drop(columns=["HashOwner", "HashApp", "Trigger"])

df_day1 = pd.merge(duration_01, invoke_01, how="inner", on=["HashFunction"])
df_day1 = df_day1[df_day1["Average"] > 0]

# Vectorized processing for the first 2 minutes (columns 1 and 2 after Average)
df_2min = df_day1.iloc[:, [1, 2, 3]].copy()
df_2min.columns = ['Average', 'Min1', 'Min2']
df_2min_grouped = df_2min.groupby("Average").sum()
df_2min_grouped["Count"] = df_2min_grouped["Min1"] + df_2min_grouped["Min2"]
df_2min_grouped = df_2min_grouped[df_2min_grouped["Count"] > 0].reset_index()

x_2min = list(df_2min_grouped["Average"] / 1000)
y_2min = list(df_2min_grouped["Count"])
p_2min = y_2min / np.sum(y_2min)
cdf_2min = np.cumsum(p_2min)


# ---------------------------------------------------------
# 3. Load Generated Workload CDF
# ---------------------------------------------------------
dur_list = [7, 8, 9, 10, 12, 14, 17, 21, 27, 39, 56, 85, 131, 205, 325, 520, 838, 1347, 2175, 3512, 5673, 9172, 14835]
fib = [24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
arg_to_duration = dict(zip(fib, dur_list))

workload_file = f"{__file}/workload_dur.txt"
if not os.path.exists(workload_file):
    raise FileNotFoundError(f"No workload file found at: {workload_file}")

workload_df = pd.read_csv(workload_file, sep=r"\s+", header=None, names=["iat", "arg"])
workload_counts = workload_df["arg"].value_counts().sort_index()

workload_duration_counts = []
for arg, count in workload_counts.items():
    if arg in arg_to_duration:
        workload_duration_counts.append((arg_to_duration[arg], count))

workload_duration_counts.sort(key=lambda x: x[0])
x_wl = [duration for duration, _ in workload_duration_counts]
y_wl = [count for _, count in workload_duration_counts]
p_wl = y_wl / np.sum(y_wl)
cdf_wl = np.cumsum(p_wl)
x_divided_wl = [value / 1000 for value in x_wl]


# ---------------------------------------------------------
# 4. Plot Combined CDFs
# ---------------------------------------------------------
fig, ax1 = plt.subplots(figsize=(12, 6))

ax1.step(
    x_2weeks, cdf_2weeks, color="lightcoral", where="pre", linewidth=3, label="Azure 2-week data"
)
ax1.step(
    x_2min, cdf_2min, color="mediumseagreen", where="pre", linewidth=3, label="Azure first 2 minutes"
)
ax1.step(
    x_divided_wl, cdf_wl, color="cornflowerblue", where="pre", linewidth=3, label="Sampled data"
)

plt.xticks(size=20)
plt.yticks(size=20)
plt.grid()
plt.xscale("log")
ax1.set_xlabel("Average Duration (s)", size=23)
ax1.set_ylabel("Cumulative prob", size=23)
plt.legend(fontsize=20)
plt.tight_layout()
plt.savefig(f"{__file}/azure_sample_comparison.png", dpi=300)