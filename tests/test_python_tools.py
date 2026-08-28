import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_self_test():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "self_test.py")],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SELF_TEST_OK" in result.stdout
