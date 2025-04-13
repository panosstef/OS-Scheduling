import uuid
import subprocess
import time

# ANSI color codes
GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RESET = "\033[0m"

IMAGE_NAME = "python:3.9-slim"

def run_container(container_type, script, _ = None):
    container_name = f"{container_type}-test-{uuid.uuid4().hex[:8]}"
    cmd = f"docker run --rm --name {container_name} {IMAGE_NAME} {script}"
    start = time.time()
    result = subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    end = time.time()

    stderr_on_fail(result.returncode, container_name)
    return end - start


def stderr_on_fail(result, container_name):
    if result != 0:
        error_message = result.stderr.decode()
        print(f"{RED}Container {container_name} failed:\n{error_message}{RESET}")
        raise RuntimeError(
            f"Execution failed for container {container_name}: {error_message}")

def initialize():
    print(f"{CYAN}Initializing python:3.9-slim docker image...{RESET}")
    result = subprocess.run("docker image pull python:3.9-slim", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"{RED}Failed to pull docker image {IMAGE_NAME}\nError: {result.stderr.decode()}{RESET}")
        exit(-1)
