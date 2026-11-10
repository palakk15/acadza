"""Summarize the committed model output and list each auto-apply for review."""

import json
from collections import Counter
from pathlib import Path


def main() -> None:
    path = Path(__file__).resolve().parents[1] / "results.json"
    if not path.exists():
        print("results.json does not exist. Run the real LLM pipeline after setting GROQ_API_KEY.")
        return
    results = json.loads(path.read_text(encoding="utf-8"))
    print(f"Reports in results.json: {len(results)}")
    print("Verdicts:", dict(sorted(Counter(row["verdict"] for row in results).items())))
    print("Routes:", dict(sorted(Counter(row["route"] for row in results).items())))
    automatic = [row for row in results if row["route"] == "auto_apply"]
    print(f"\nAuto-apply proposals for hand review: {len(automatic)}")
    for row in automatic:
        print(f"{row['reportId']} / {row['questionId']} · {row['verdict']} · {row.get('repair')} · {row.get('edit')}")


if __name__ == "__main__":
    main()
