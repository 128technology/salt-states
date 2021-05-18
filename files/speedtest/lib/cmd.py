import subprocess

def run_command(command):
    return subprocess.run(command.split(), stdout=subprocess.PIPE)
