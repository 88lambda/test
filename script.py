#!/usr/bin/env python3

import sys
import subprocess
import os

def run_command(command):
    try:
        result = subprocess.run(command, text=True, check=True, capture_output=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error executing {' '.join(command)}", file=sys.stderr)
        print(e.stderr.strip(), file=sys.stderr)
        sys.exit(e.returncode)

def create_new_version(app_name, version):
    print(f"Creating new version of {app_name}")
    command = ["./univention-appcenter-control", "new-version", app_name, version]
    run_command(command)

def upload_files(app_name, files):
    for file in files:
        if os.path.isfile(file):  
            print(f"Uploading {file}")
            command = ["./univention-appcenter-control", "upload", version, file]
            run_command(command)
        else:
            print(f"Skipping file {file} (file doesn't exist)", file=sys.stderr)

def main():
    if len(sys.argv) < 4:
        sys.exit(1)

    app_name = sys.argv[1]
    version = sys.argv[2]
    files = sys.argv[3].split(',')

    create_new_version(app_name, version)

    upload_files(version, files)

if __name__ == "__main__":
    main()
