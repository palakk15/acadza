"""Run the parser and print a compact dataset summary."""

from pathlib import Path

from .data import format_summary, group_reports, load_dataset


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    questions, reports, _taxonomy = load_dataset(root / "data")
    cases = group_reports(questions, reports)
    print(format_summary(cases, reports))
    print("\nReported groups:")
    for question_id, case in sorted(cases.items()):
        if case["reports"]:
            print(
                f"{question_id}: {len(case['reports'])} report(s), "
                f"{case['parsed'].question_type}, "
                f"{len(case['parsed'].options)} options"
            )


if __name__ == "__main__":
    main()
