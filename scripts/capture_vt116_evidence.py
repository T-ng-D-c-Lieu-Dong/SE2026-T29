"""Capture a command's actual output with provenance; never edit generated logs."""

import importlib.metadata
import os
import platform
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main():
    destination = Path(sys.argv[1])
    command = sys.argv[2:]
    destination.parent.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--short"], text=True)
    with destination.open("w") as output:
        output.write(f"UTC: {datetime.now(UTC).isoformat()}\nTested commit: {sha}\n")
        output.write(f"Working tree before run:\n{dirty or '(clean)'}\n")
        output.write(f"Python: {platform.python_version()}\nOS: {platform.platform()}\n")
        for package in ("pytest", "asyncpg", "coverage", "sqlalchemy", "httpx"):
            try:
                output.write(f"{package}: {importlib.metadata.version(package)}\n")
            except importlib.metadata.PackageNotFoundError:
                pass
        output.write(f"Command: {shlex.join(command)}\n")
        output.write("Database: isolated vt116_final_test on 127.0.0.1:55433\n")
        for key in ("COVERAGE_CORE", "PYTHONHASHSEED", "TZ"):
            if key in os.environ:
                output.write(f"{key}={os.environ[key]}\n")
        output.flush()
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=False)
        output.write(f"\nExit code: {result.returncode}\n")
    print(destination)
    print(destination.read_text()[-2200:])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
