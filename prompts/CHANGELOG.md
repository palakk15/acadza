# Prompt changelog

## v1 — initial implementation

- Added `solver_v1.md` for a blind question solve without the stored answer, solution, or reports.
- Added `triage_v1.md` for grouped report analysis with taxonomy choices and per-student replies.
- These are the first product prompt versions. There is no earlier prompt to preserve.
- The v1 prompts have been run through Groq on all 44 supplied reports. No wording revision has been made yet; the available evaluation summarizes verdict and route counts but does not score against ground truth.
- One tool call returned malformed/truncated JSON. The client now retries that specific failure with a larger bounded completion budget; this was a client reliability fix, not a prompt revision.
