"""Guards for the environment template: tracked files must never carry a usable secret key."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_example_secret_key_is_only_a_placeholder():
    value = next(line.split("=", 1)[1].strip() for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
                 if line.startswith("SECRET_KEY="))
    assert value.startswith("REPLACE_ME") and "DO_NOT_USE" in value


def test_local_env_file_is_ignored_by_git():
    assert subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode == 0
    tracked = subprocess.run(["git", "ls-files", ".env"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    assert tracked == ""
