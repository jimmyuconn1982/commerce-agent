from __future__ import annotations

"""Replay runner for local router and retrieval evaluation."""

from dataclasses import asdict, dataclass
import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from commerce_agent.agent import CommerceAgent
from commerce_agent.repository import PostgresSearchRepository

CASE_DIR = Path(__file__).resolve().parent / "cases"


@dataclass(slots=True)
class CaseResult:
    """One replay case result."""

    suite: str
    case_id: str
    passed: bool
    expected_intent: str | None
    actual_intent: str | None
    expected_top_product_id: int | None
    actual_top_product_id: int | None
    detail: dict[str, Any]


def load_cases(suite: str) -> list[dict[str, Any]]:
    """Load one suite of JSONL cases."""
    path = CASE_DIR / f"{suite}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_suite(suite: str) -> dict[str, Any]:
    """Run one suite and return a JSON-serializable report."""
    results = [run_case(suite, case) for case in load_cases(suite)]
    passed = sum(1 for item in results if item.passed)
    return {
        "suite": suite,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": [asdict(item) for item in results],
    }


def run_case(suite: str, case: dict[str, Any]) -> CaseResult:
    """Run one replay case against the local pipeline."""
    if suite == "router":
        agent = CommerceAgent()
        actual = agent.route_intent(case.get("prompt", ""), has_image=bool(case.get("has_image")))
        passed = actual.intent == case.get("expected_intent")
        return CaseResult(
            suite=suite,
            case_id=case["id"],
            passed=passed,
            expected_intent=case.get("expected_intent"),
            actual_intent=actual.intent,
            expected_top_product_id=None,
            actual_top_product_id=None,
            detail={"rationale": actual.rationale},
        )

    agent = CommerceAgent(search_repository=PostgresSearchRepository())
    temp_path: Path | None = None
    previous_mock = os.getenv("COMMERCE_AGENT_MOCK_VISION_RESPONSE")
    previous_flag = os.getenv("COMMERCE_AGENT_MOCK_VISION")

    try:
        if case.get("image_mock_response"):
            os.environ["COMMERCE_AGENT_MOCK_VISION"] = "1"
            os.environ["COMMERCE_AGENT_MOCK_VISION_RESPONSE"] = case["image_mock_response"]
            with NamedTemporaryFile(suffix=".png", delete=False) as handle:
                handle.write(b"fake")
                temp_path = Path(handle.name)

        result = agent.run_pipeline(
            prompt=case.get("prompt", ""),
            image_path=temp_path,
            limit=5,
        )
        actual_top_product_id = result.matches[0].id if result.matches else None
        passed = (
            result.intent == case.get("expected_intent")
            and actual_top_product_id == case.get("expected_top_product_id")
        )
        return CaseResult(
            suite=suite,
            case_id=case["id"],
            passed=passed,
            expected_intent=case.get("expected_intent"),
            actual_intent=result.intent,
            expected_top_product_id=case.get("expected_top_product_id"),
            actual_top_product_id=actual_top_product_id,
            detail={
                "response": result.content,
                "steps": [step.tool_name for step in result.trace.react.steps],
            },
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if previous_flag is None:
            os.environ.pop("COMMERCE_AGENT_MOCK_VISION", None)
        else:
            os.environ["COMMERCE_AGENT_MOCK_VISION"] = previous_flag
        if previous_mock is None:
            os.environ.pop("COMMERCE_AGENT_MOCK_VISION_RESPONSE", None)
        else:
            os.environ["COMMERCE_AGENT_MOCK_VISION_RESPONSE"] = previous_mock


def main() -> None:
    """CLI entrypoint for local replay and evaluation."""
    parser = argparse.ArgumentParser(description="Run local replay and evaluation suites")
    parser.add_argument("--suite", choices=["router", "text", "image", "multimodal", "e2e", "all"], default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    suite_names = ["router", "text", "image", "multimodal", "e2e"] if args.suite == "all" else [args.suite]
    report = {"suites": [run_suite(name) for name in suite_names]}

    output = json.dumps(report, indent=2)
    print(output)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
