import secrets
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TASK = ROOT / "task"
BUILD = ROOT / "build"

SEPARATE_VERIFIER = '[verifier]\nenvironment_mode = "separate"\nenv = { REWARD_SOURCE = "evidence" }\n'
NO_NETWORK_ENV = '[environment]\nnetwork_mode = "no-network"\n'


def write_token() -> None:
    token = secrets.token_hex(32)
    (TASK / "environment" / "sidecar" / "verifier.env").write_text(
        f"VERIFIER_TOKEN={token}\n", newline="\n"
    )
    (TASK / "tests" / "verifier_token").write_text(token + "\n", newline="\n")


def variant(name: str, toml_replacements: dict[str, str], tamper: bool = False) -> Path:
    dest = BUILD / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(TASK, dest)
    toml_path = dest / "task.toml"
    text = toml_path.read_text()
    for old, new in toml_replacements.items():
        assert old in text, old
        text = text.replace(old, new, 1)
    text = text.replace('name = "unfindable/s0-mcp-sidecar"', f'name = "unfindable/{name}"', 1)
    toml_path.write_text(text, newline="\n")
    if tamper:
        sol = dest / "solution"
        shutil.rmtree(sol)
        sol.mkdir()
        for f in ("solve.sh", "fake_sidecar.py"):
            shutil.copy(ROOT / "tamper" / f, sol / f)
    return dest


def main() -> None:
    write_token()
    BUILD.mkdir(exist_ok=True)
    built = [
        variant("s0-separate", {"[verifier]\n": SEPARATE_VERIFIER}),
        variant("s0-tamper-shared", {}, tamper=True),
        variant("s0-tamper-separate", {"[verifier]\n": SEPARATE_VERIFIER}, tamper=True),
        variant("s0-no-network", {"[environment]\n": NO_NETWORK_ENV}),
    ]
    print("token regenerated; variants:")
    for path in built:
        print(" ", path.relative_to(ROOT))


main()
