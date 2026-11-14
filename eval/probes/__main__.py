import argparse
import json
from pathlib import Path

from .invalid_actions import invalid_actions
from .replay import replay
from .runner import play, ward


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a public-tool exploit probe inside main")
    parser.add_argument("probe", choices=("invalid-actions", "replay"))
    parser.add_argument("--script", type=Path)
    options = parser.parse_args()
    if options.probe == "replay" and options.script is None:
        parser.error("replay requires --script")
    policy = invalid_actions
    if options.probe == "replay":
        policy = replay(json.loads(options.script.read_text(encoding="utf-8")))
    print(json.dumps(play(ward, policy)))


if __name__ == "__main__":
    main()
