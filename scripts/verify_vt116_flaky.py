"""Bounded repeat/order/timezone checks; not a proof that tests can never flake."""

import os
import subprocess
import sys


def pytest_collection_modifyitems(items):
    if os.getenv("VT116_REVERSE_ORDER") == "1":
        items.reverse()


if __name__ == "__main__":
    targets = [
        "backend/tests/unit/test_soft_delete_restore.py",
        "backend/tests/integration/test_soft_delete_restore_api.py",
        "backend/tests/integration/test_vt116_security_transitions.py",
    ]
    for zone, reverse in [("UTC", "0"), ("Pacific/Honolulu", "1"), ("Asia/Ho_Chi_Minh", "0")]:
        environment = dict(
            os.environ,
            TZ=zone,
            VT116_REVERSE_ORDER=reverse,
            PYTHONHASHSEED="1",
            PYTHONPATH=".:backend",
        )
        command = [
            sys.executable,
            "-m",
            "pytest",
            *targets,
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "scripts.verify_vt116_flaky",
        ]
        print(f"RUN timezone={zone} reverse_order={reverse}; command={command}", flush=True)
        subprocess.run(command, env=environment, check=True)
    print(
        "PASS: three isolated runs; reversed order and varied process timezone; "
        "fixed service clocks"
    )
