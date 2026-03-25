from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devtools.evalbench.runner import load_cases, run_suite


def test_evalbench_loads_router_cases() -> None:
    cases = load_cases("router")
    assert cases
    assert cases[0]["id"].startswith("router_")


def test_evalbench_router_suite_runs() -> None:
    report = run_suite("router")
    assert report["suite"] == "router"
    assert report["total"] >= 1
    assert report["passed"] >= 1
