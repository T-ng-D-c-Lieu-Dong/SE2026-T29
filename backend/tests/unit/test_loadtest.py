import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LOADTEST_DIR = REPO_ROOT / "loadtest"


def test_loadtest_directory_structure():
    assert LOADTEST_DIR.is_dir(), "loadtest directory must exist"
    readme_path = LOADTEST_DIR / "README.md"
    slots_path = LOADTEST_DIR / "slots.js"
    booking_path = LOADTEST_DIR / "booking.js"

    assert readme_path.is_file(), "loadtest/README.md must exist"
    assert slots_path.is_file(), "loadtest/slots.js must exist"
    assert booking_path.is_file(), "loadtest/booking.js must exist"


def test_loadtest_slots_script_contents():
    slots_content = (LOADTEST_DIR / "slots.js").read_text(encoding="utf-8")

    assert "/api/slots" in slots_content, "Script must query /api/slots endpoint"
    assert "BASE_URL" in slots_content, "Script must support BASE_URL environment variable"
    assert "TARGET_DATE" in slots_content, "Script must support TARGET_DATE environment variable"
    assert "p(95)<500" in slots_content, "Threshold must enforce p(95) < 500ms per E15"
    assert "rate<0.01" in slots_content, "Threshold must enforce error rate < 1%"
    assert "slotsDuration" in slots_content, "Script must record slotsDuration metric"
    assert "slotsSuccessRate" in slots_content, "Script must record slotsSuccessRate metric"
    assert "status is 200" in slots_content, "Script must check for status 200"


def test_loadtest_booking_entrypoint_contents():
    booking_content = (LOADTEST_DIR / "booking.js").read_text(encoding="utf-8")

    assert "queryAvailableSlots" in booking_content, "booking.js must integrate slots scenario"
    assert "slots.js" in booking_content, "booking.js must import from slots.js"


def test_loadtest_readme_documentation():
    readme_content = (LOADTEST_DIR / "README.md").read_text(encoding="utf-8")

    assert "E15" in readme_content, "README must mention E15 SLO requirement"
    assert "BASE_URL" in readme_content, "README must document BASE_URL variable"
    assert "slots.js" in readme_content, "README must document slots.js scenario"
    assert "booking.js" in readme_content, "README must document booking.js entrypoint"
    assert "k6 run" in readme_content, "README must document k6 execution command"


def test_loadtest_javascript_syntax():
    node_executable = shutil.which("node")
    if node_executable is None:
        return

    for filename in ("slots.js", "booking.js"):
        file_path = LOADTEST_DIR / filename
        result = subprocess.run(
            [node_executable, "--check", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Syntax error in {filename}: {result.stderr}"


def test_booking_scenario_behaviour():
    node_executable = shutil.which("node")
    if node_executable is None:
        pytest.skip("Node.js is required for k6 scenario behaviour tests")
    result = subprocess.run(
        [
            node_executable,
            "--experimental-vm-modules",
            "--test",
            str(LOADTEST_DIR / "tests" / "booking.test.mjs"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
