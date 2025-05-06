#!/usr/bin/python3
import time
from datetime import date
import subprocess
import os
import socket

# The function to launch the C++ fibonacci function
def launch_command_cpp(arg):
    command = (
        f"./payload/launch_function.out {arg}"
    )
    print(command)
    subprocess.run(command, shell=True)


dur_list = []
fib = []


# Measure the runtime of the C++ fibonacci function
def loop(arg, repeat):
    start = time.time()
    for i in range(repeat):
        launch_command_cpp(arg)
    end = time.time()
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

    for i in range(3, 41):
        loop(i, 100)

    for i in range(40, 47):
        loop(i, 20)

    with open(f"./log/calibrate_list_{socket.gethostname()}_{date.today()}.txt", "w") as f:
        f.write("dur_list = {}\n".format(dur_list))
        f.write("fib = {}\n".format(fib))
