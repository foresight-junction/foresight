import sys
from pathlib import Path

# export_replay.py (frontend/tools) is the reference the recorder must match.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
