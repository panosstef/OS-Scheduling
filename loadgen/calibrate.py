#!/usr/bin/python3
import time
from datetime import date
import subprocess
import os
import socket

def get_reps(arg):
    if arg <= 34: return 300  # Captures jitter for short-lived tasks
    if arg <= 39: return 30   # Reliable mean for medium tasks
    if arg <= 42: return 5    # Minimal noise for long tasks
    return 2                 # Ground truth for very long tasks

# The function to launch the C++ fibonacci function
def launch_command_cpp(arg):
    command = [
        "/shared/loadgen/payload/launch_function.out",
        str(arg)
    ]
    subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )


dur_list = []
fib = []


# Measure the runtime of the C++ fibonacci function
def loop(arg, repeat):
    start = time.perf_counter()
    for i in range(repeat):
        launch_command_cpp(arg)
    end = time.perf_counter()
    # get milliseconds
    print("Runtime for arg {} is {} ms".format(arg, (end - start) * 1000 / repeat))
    dur_list.append(round((end - start) * 1000 / repeat))
    fib.append(arg)
    with open(f"./log/calibrate_{socket.gethostname()}_{date.today()}.txt", "a") as f:
        f.write(
            "Runtime for arg {} is {} ms\n".format(arg, (end - start) * 1000 / repeat)
        )


if __name__ == "__main__":
    if not os.path.exists("./log"):
        os.makedirs("./log")

    for i in range(24, 47):
        loop(i, get_reps(i))


    with open(f"./log/calibrate_list_{socket.gethostname()}_{date.today()}.txt", "w") as f:
        f.write("dur_list = {}\n".format(dur_list))
        f.write("fib = {}\n".format(fib))