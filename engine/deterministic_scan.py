"""Print deterministic findings across all source questions without an LLM."""

from pathlib import Path

from .checks import deterministic_checks
from .data import group_reports, load_dataset


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    questions, reports, _ = load_dataset(root / "data")
    cases = group_reports(questions, reports)
    findings_by_code: dict[str, int] = {}
    unreported: list[tuple[str, str, str]] = []
    total = 0
    for question_id, case in cases.items():
        findings = deterministic_checks(case["question"], case["parsed"])
        total += len(findings)
        for finding in findings:
            findings_by_code[finding.code] = findings_by_code.get(finding.code, 0) + 1
            if not case["reports"]:
                unreported.append((question_id, finding.code, finding.detail))
    print(f"Scanned {len(questions)} questions; deterministic findings: {total}.")
    print("Finding counts:", ", ".join(f"{key}={count}" for key, count in sorted(findings_by_code.items())) or "none")
    print(f"Reported questions with findings: {sum(bool(case['reports']) and bool(deterministic_checks(case['question'], case['parsed'])) for case in cases.values())}")
    print(f"Unreported questions with candidate findings: {len(unreported)}")
    for question_id, code, detail in unreported:
        print(f"{question_id} [{code}] {detail}")


if __name__ == "__main__":
    main()
