import importlib.util
import json
from pathlib import Path

import pytest

VERIFY_PATH = Path(__file__).resolve().parents[3] / "tests" / "verify.py"
spec = importlib.util.spec_from_file_location("ed72_verify", VERIFY_PATH)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def good_report() -> dict:
    o, t, w, b = 0.8, 0.5, 0.6, 1.0
    score = 60 * o + 20 * t + o * (10 * w + 10 * b)
    return {"reward": score / 100, "score": score, "O": o, "T": t, "W": w, "B": b}


def run(tmp_path: Path, content: str | None) -> tuple[int, Path, Path]:
    report = tmp_path / "report.json"
    if content is not None:
        report.write_text(content, encoding="utf-8")
    reward, full = tmp_path / "logs" / "reward.txt", tmp_path / "logs" / "score_full.json"
    return verify.run(report, reward, full), reward, full


def test_valid_report_writes_reward_and_full_object(tmp_path: Path) -> None:
    report = good_report()
    code, reward, full = run(tmp_path, json.dumps(report))
    assert code == 0
    assert float(reward.read_text()) == pytest.approx(report["reward"], abs=1e-6)
    assert json.loads(full.read_text()) == report
    assert not (tmp_path / "logs" / "reward.json").exists()


@pytest.mark.parametrize("bad", [1.5, -0.1])
def test_out_of_range_reward_scores_zero(tmp_path: Path, bad: float) -> None:
    report = good_report() | {"reward": bad}
    code, reward, full = run(tmp_path, json.dumps(report))
    assert code == 1
    assert float(reward.read_text()) == 0
    assert not full.exists()


def test_nan_reward_scores_zero(tmp_path: Path) -> None:
    code, reward, _ = run(tmp_path, json.dumps(good_report() | {"reward": float("nan")}))
    assert code == 1
    assert float(reward.read_text()) == 0


def test_forged_reward_inconsistent_with_score_scores_zero(tmp_path: Path) -> None:
    code, reward, _ = run(tmp_path, json.dumps(good_report() | {"reward": 1.0}))
    assert code == 1
    assert float(reward.read_text()) == 0


def test_score_inconsistent_with_components_scores_zero(tmp_path: Path) -> None:
    code, reward, _ = run(tmp_path, json.dumps(good_report() | {"O": 0.1}))
    assert code == 1
    assert float(reward.read_text()) == 0


def test_missing_file_scores_zero(tmp_path: Path) -> None:
    code, reward, _ = run(tmp_path, None)
    assert code == 1
    assert float(reward.read_text()) == 0


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"reward": 0.5}'])
def test_garbage_or_truncated_json_scores_zero(tmp_path: Path, content: str) -> None:
    code, reward, _ = run(tmp_path, content)
    assert code == 1
    assert float(reward.read_text()) == 0
