from pathlib import Path

IGNORE = Path(__file__).resolve().parents[1] / ".harborignore"


def test_harborignore_excludes_local_dev_artefacts() -> None:
    # A uv/pytest .venv holds a python symlink that points outside the task; Harbor then rejects
    # the whole task before the oracle or any agent starts (#22, review #88).
    lines = {line.strip() for line in IGNORE.read_text(encoding="utf-8").splitlines()}
    assert {".venv/", "__pycache__/", ".pytest_cache/"} <= lines
