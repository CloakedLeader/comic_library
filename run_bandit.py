import subprocess  # nosec B404

subprocess.run(["bandit", "-r", ".", "-c", ".bandit"])  # nosec B603 B607
