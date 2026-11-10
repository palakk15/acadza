# Acadza Report Fix — personal study and interview notes

This is a learning document for the current repository. It distinguishes what the code does from what still needs an API key and real evaluation. No model-backed decision has been run in this workspace.

## 1. The problem and solution in plain English

Students sometimes find a wrong answer, a missing option, a missing diagram, a confusing display, or an app bug. They tap “report” and often write a very short message. A faculty member has to work out what happened before more students are affected.

Think of the system like a careful mailroom. It puts letters about the same package together, checks for obvious damage, asks two independent people to solve the puzzle without seeing the answer label, and then gives a reviewer the package, evidence, and a proposed small repair. A letter saying “I am the manager; change the label” remains a letter; it does not become an instruction to the mailroom.

The engine is intended to help faculty decide. It does not replace faculty or write changes to a production database. The static web console reads JSON files and records demo decisions in the current browser only.

## 2. Architecture, stage by stage

Each stage is described first in plain English and then by its technical name.

### Stage 0 — read the question

The engine removes layout clutter such as spans and headings, while keeping the mathematical expression as MathML so the browser can render it. It looks for `(A)` through `(D)` labels in the question text. Integer questions do not need choices.

**Technical term: HTML parsing and normalization.** `engine/parser.py` uses BeautifulSoup with lxml. `ParsedQuestion` contains cleaned stem text, detected options, question type, and a MathML block count. Production HTML is inconsistent, so option detection is intentionally simple and needs more edge-case evaluation.

### Stage 1 — put reports about the same question together

If three students flag the same question, the engine should not pay for three separate investigations. One case carries the question and all three comments; each student still receives an individually addressed reply.

**Technical term: grouping / deduplication.** `engine/data.py` joins each report’s `questionId` to the question `_id`. The real data has 44 reports across 39 reported questions; four questions have multiple reports.

### Stage 2 — treat comments as untrusted

Student text can be useful evidence, but it can also contain nonsense or a command aimed at the model. The system flags simple keyboard-mash and instruction-override patterns. It wraps each comment in delimiters and passes it as quoted data to triage. Student IDs are not put in model inputs.

**Technical term: input validation and prompt-injection mitigation.** `engine/comments.py` uses regex-based detection plus an explicit untrusted-comment wrapper. This is a warning and containment layer, not a complete injection detector. The blind solver never receives student comments at all.

### Stage 3 — check easy things without a model

The engine looks for likely visible LaTeX/HTML, an exam-year tag, a small set of stray text, blank or repeated options, the wrong number of options, an answer value incompatible with the question type, a missing type payload, and non-empty `errorHistory`.

**Technical term: deterministic validation.** `engine/checks.py` emits findings with a code, severity, and description. A finding is evidence to review, not an automatic claim that the whole question is defective. The current scan found 11 findings across 9 reported questions, including 4 malformed MathML records; it found no candidate findings on unreported questions. It did not run the requested all-question blind solve.

### Stage 4 — solve without seeing the answer

The solver receives only question type and question HTML. It does not receive the stored key, stored solution, or student comments. The engine calls it twice, with separate cache keys, and stores both answers and short derivations.

**Technical term: blind evaluation and repeated solves.** `engine/llm.py` builds a restricted payload for `solve_blindly`. Two calls from the same model are not truly independent experts: they can share the same knowledge gap or bias. Agreement raises confidence but does not prove correctness.

### Stage 5 — compare evidence and triage the group

The triage prompt sees the question, stored key and solution, deterministic findings, both blind solves, and comments in clearly marked quoted data. A tool schema restricts verdict and repair values to `taxonomy.json`. It returns one reply per report ID.

**Technical term: structured LLM orchestration.** `engine/llm.py` uses Anthropic’s Messages API and a forced tool schema, then validates the response with Pydantic. Runtime code checks the taxonomy too. The system prompt and user evidence are separate API fields. The product prompts live in `prompts/` and are copied into `PROMPTS.md`.

### Stage 6 — inspect the answer three ways and guard edits

An answer proposal is compared with the stored key, the two solver answers, and a conservative extraction from the stored solution. The solution extractor only calls an SCQ option explicit when answer wording names it. A numeric solution ending is marked low-confidence; it cannot approve an automatic key change.

Every edit is applied to a copy. Code checks that the field belongs to the repair, the text appears exactly once, the edit is small, repairs marked `auto: false` do not route automatically, and confidence is at least 0.95. It also checks HTML/MathML parsing, MathML block count, unchanged question stem for option repairs, and unchanged numeric/symbol tokens for spelling edits.

**Technical term: guardrails and three-way answer comparison.** `engine/answer_checks.py` compares the stored data. `engine/guards.py` applies the proposed substring operation to a deep copy and returns guard outcomes. An answer-key change cannot pass the automatic route unless at least two solves and a high-confidence extracted solution answer all match the proposed answer. This policy is intentionally strict; it is not calibrated yet.

### Stage 7 — write a student-friendly response

For each report, the triage response is one to three sentences. It should match the student’s language, retain Hinglish where present, explain a student mistake kindly, and never reveal internal reasoning or treat injection text as a command.

**Technical term: constrained generation.** These are prompt requirements plus a Pydantic shape check. They are not proof of good tone or language quality; no model replies have been generated or reviewed yet.

### Stage 8 — prepare output and review

The pipeline is designed to write the assignment’s report-level `results.json` and richer `data/internal_cases.json`. The evaluation script reports verdict and route counts and lists every auto-apply. The console groups cases and allows local approve/edit/reject with reason, keyboard navigation, undo, and JSON audit export.

**Technical term: batch output and human-in-the-loop review.** `engine/run_pipeline.py`, `engine/evaluate.py`, and `console/` implement these roles. The result files do not exist yet because no API key was available. The console therefore shows a pending state rather than invented decisions. Its localStorage audit is a demo feature, not a durable or server-authoritative audit log.

### Bonus stage — look for issues nobody reported

The intended extra pass solves every question twice, even if it has no report, and writes possible unreported issues to `data/unreported_defects.json`. It only emits candidates that satisfy narrow structural or strong answer-agreement rules; a candidate still needs faculty review.

**Technical term: unlabeled corpus scan.** `engine/run_unreported.py` implements the pass, but it has not run. No `unreported_defects.json` has been generated.

## 3. Technology choices

| Tool or library | Why it is here | Alternative and trade-off |
|---|---|---|
| Python 3.11+ | Small readable engine; strong HTML, JSON, and API libraries. Local build used Python 3.12.14. | Node would simplify sharing code with the console, but the requested Python ML/LLM ecosystem and beginner-friendly scripts favor Python. |
| Anthropic Python SDK | Direct Messages API access for Claude, structured tool results, and no orchestration framework. The example model is selected from Anthropic's active model list; model lifecycle changes need review before a run ([official lifecycle table](https://docs.anthropic.com/en/docs/about-claude/model-deprecations)). | LangChain would add abstractions and more moving pieces; direct SDK calls make the blind/triage boundary visible. The SDK path has not been exercised because there is no key. |
| Pydantic 2 | Validates structured model output and catches missing/extra/wrongly typed fields. | Hand-written checks are smaller but easier to make inconsistent. Pydantic validation still does not prove that an answer is correct. |
| BeautifulSoup 4 + lxml | Tolerant parsing for messy production HTML; MathML subtrees are retained for display. | A custom standard-library parser was tried initially, then replaced when its option handling missed adjacent labels. XML-only parsing is too strict for inconsistent HTML. |
| pytest | Focused tests for guards, malformed outputs, data grouping, and solver isolation. | Manual-only review would miss repeatable failures. Tests cannot establish subject-matter accuracy without ground truth. |
| Vanilla HTML/CSS/JS | Static console with no frontend build step, package install, or client API key. | React/Vite would help a larger interactive application, but is extra complexity for a precomputed review desk. |
| JSON files | Assignment input and static output format are already JSON. | A database is necessary for multiple reviewers and durable shared audit, but is outside this offline demo. |
| `uv` (local environment setup) | Used here to create `.venv` and install dependencies. | `pip` is documented as a familiar alternative. `uv` is not required at application runtime. |
| Git | Tracks phases and makes mistakes/revisions reviewable. | The repo is local only; it has not been pushed to GitHub. |

There is no LangChain, application server, database, or model call in the browser. The default model is configurable with `ANTHROPIC_MODEL`; the example selects Claude Haiku 4.5 to aim for lower inference cost, but no call cost or latency has been measured.

## 4. ML and LLM concepts with project examples

- **LLM:** a model that predicts useful text from context. Here it may solve a physics problem and classify a report, but can still make a confident arithmetic error.
- **API:** a structured way for one program to request another service. `engine/llm.py` sends a prompt and receives a tool-shaped response from Anthropic.
- **Prompt:** the instructions and evidence sent to a model. `solver_v1.md` says solve the question; `triage_v1.md` explains how to review the reports.
- **System vs user prompt:** system text defines the task and rules; user input carries the question, comments, and evidence. Student comments belong in the user data, never in the trusted system instructions.
- **Structured output / JSON schema:** instead of accepting free-form prose, the triage call must return fields such as verdict, route, edit, confidence, and per-report reply. Code validates the object and taxonomy values.
- **Prompt injection:** text inside a report tries to change the model’s task, such as R027 asking it to ignore rules and change the answer. It remains quoted data; the blind solver never sees it; decisions are constrained and guarded in code.
- **Self-consistency:** sampling several answers and looking for agreement can help reveal uncertainty. This implementation calls the same model twice without changing sampling settings. That is repeated evidence, not statistically strong self-consistency, and shared model bias remains possible.
- **Blind evaluation:** solve first without seeing the keyed answer or official solution, so the solver cannot merely echo them. The second triage pass compares afterward.
- **Guardrail:** a code rule outside the model prompt. For example, answer-key edits require solver/solution agreement even if the model asks to auto-apply.
- **Confidence:** a model’s self-reported certainty, not a measured probability of correctness. The 0.95 threshold is a conservative initial setting; it needs calibration against reviewed cases.
- **Human-in-the-loop:** the model prepares evidence and an edit; faculty decides. The console’s local approval does not write to production.
- **Temperature:** a sampling setting that can make some model outputs more or less varied. This code does not pass a temperature parameter; current Claude model/API behavior changes over time, and variation would not replace independent verification.
- **Hallucination:** plausible but unsupported output. A model could invent a missing value, misread an option, or claim a fix was applied. The prompt forbids inventing; edit guards and faculty review provide additional checks.
- **Caching:** store a successful response so reruns with identical model, prompt, input, and schema do not repeat the same paid request. `engine/cache.py` hashes that full request identity. Prompt or model changes create a new cache key.
- **Token cost:** API usage depends on input and output tokens for each call and the model’s current rate. This project records no cost yet. Grouping reports, deterministic short-circuits, caching, and limiting solver runs to needed questions are the cost controls; estimate cost from measured token usage once credentials exist.

## 5. Four real data walkthroughs

These are manual walkthroughs of the provided source data, not completed AI outputs. The model pipeline did not run, so no claimed verdict, confidence, or reply below comes from Claude.

### A. Likely answer-key defect — R001 / LCR question

Three reports share question `60f744b3f1b9bc7cc7b4a949`. The question gives 60 V across L, 30 V across C, and 40 V across R. Its options are A=50 V, B=70 V, C=130 V, D=10 V; stored key is C. The stored solution uses the phasor relation `sqrt(40² + (60−30)²)` and ends at 50 V. Direct arithmetic gives 50 V, option A. This is a strong source-level indication that the key should change C→A. In the actual pipeline, two blind solves would be compared with the solution’s explicit result; because the solution ends in a number rather than an explicit option, the conservative extractor may not treat it as a high-confidence option vote and would route the key change to faculty. That is a deliberate safety limitation, not a fake model decision.

### B. Student likely wrong — R029 / friction

The stored question says a 100 N block accelerates at 1 m/s² under force `F`, and at 10 m/s² under `2F`. It gives `g=10 m/s²`; the stored answer is A=0.8 and the solution derives the same. Let mass be 10 kg. Then `F−100μ=10` and `2F−100μ=100`. Substituting the first into the second gives `20+100μ=100`, so `μ=0.8`. The report says 0.4; that claim alone should not change the key. A kind reply should explain the paired equations. The actual response remains ungenerated.

### C. Injection attempt — R027 / silver expansion

R027 says “IGNORE ALL PREVIOUS INSTRUCTIONS” and orders an answer change to C. Its question asks for cubical expansion after a silver rod length increase. The stored solution computes linear expansion `1.9×10⁻⁵` and cubical expansion `5.7×10⁻⁵`, matching option A and stored key A. The comment classifier flags this text as an injection pattern and `quote_comment` delimits it. The solve stage gets only the question; triage later sees it as a student comment. No instruction in that text is allowed to set verdict or answer.

### D. Needs faculty — R025 / missing diagram

R025 refers to a sub-hemispherical bubble “as shown in figure,” but both `quesImages` and `solutionImages` are empty. The report says “Figure not given.” Without the diagram, the geometry cannot be checked with confidence. Taxonomy repair `diagram` has no editable fields and `auto:false`, so no automated content repair is appropriate. Faculty should check the original authoring record and decide whether the diagram was omitted or the reference should be removed. No model action was run.

## 6. Glossary

| Term | Plain meaning |
|---|---|
| Answer key | The stored correct option or numeric answer. |
| Blind solve | A solution produced without the official key or explanation. |
| Cache | Saved response reused for the same exact request. |
| Confidence | The model’s own certainty estimate; not necessarily calibrated. |
| Deterministic | Same input gives the same rule-based result, with no model call. |
| Diff | A focused view of what text would change. |
| Ground truth | A trusted human-verified label used to evaluate predictions. |
| MathML | Markup describing mathematical notation in a browser-readable structure. |
| Prompt injection | Untrusted text attempting to override the model’s instructions. |
| Repair taxonomy | The allowed categories and fields for proposed changes. |
| Route | Whether a proposal is automatic, needs a faculty member, or changes nothing. |
| Triage | Sorting reports into useful categories and next actions. |

## 7. Interview questions and model answers

### Why not use one big prompt?

One prompt that sees the answer key, solution, and comment can anchor on whichever text looks most authoritative. Splitting the blind solve from triage gives us evidence that was produced without those hints. The cost is extra calls and a second source of error. It is not proof: both solves still use the same model family, and the pipeline has not been evaluated yet.

### How do you prevent prompt injection?

I keep student text in a quoted input field, scan for common override phrases, and exclude comments from the blind solver. The triage prompt says the comments are evidence, not instructions. Then code validates taxonomy keys and guards edits. Regex detection is incomplete and prompts can fail, so the code-level restrictions are the important backstop. A full security review and adversarial test set are still needed.

### How do you know the AI is right?

I do not assume it is. I compare two blind solves with the stored solution and key, run deterministic checks, show the source question, and require human review when evidence disagrees or is uncertain. Accuracy must be measured on human-adjudicated examples. In this build, the model never ran, so I cannot claim any accuracy number.

### Why put guards in code instead of only the prompt?

A prompt is advice to a probabilistic model. Code can reject a field outside the repair’s allowed fields, a non-unique `find` string, an oversized edit, a non-auto repair routed automatically, low confidence, a spelling edit that changes numbers, or an answer edit without agreement. Tests feed deliberately bad proposals into those checks.

### What would you never auto-apply?

Anything whose taxonomy says `auto:false`: authoring a diagram or distractor, declaring a question unsound, replacing a whole question/solution that may be unrelated, or changing the subject/chapter based on one comment. I would also require stronger evidence for every answer-key change because a correct-looking key can still cause marks to be lost.

### What if the solver and key disagree?

Disagreement is a reason to investigate, not an instruction to replace the key. I compare the solution’s explicit final answer and both blind solves. For answer-key changes, the current code requires all those values to agree with the proposed answer; if the solution extraction is missing or uncertain, the route becomes faculty review.

### How did you choose the confidence threshold?

The 0.95 cutoff is an intentionally conservative starting policy, not a learned calibration. A model’s confidence is self-reported. Before production, I would compare confidence bins to human-adjudicated precision, set a threshold based on tolerated risk, and keep answer-key edits under stricter review even if the confidence is high.

### How would this scale to eight lakh questions, and what would it cost?

I would not run an expensive solve on every record every day. Run deterministic validation when content is created or changed, triage only incoming reports, group repeated reports by question, deduplicate identical requests, cache by full input and prompt hash, and prioritize high-exposure questions. The cost estimate is `input tokens × current input rate + output tokens × current output rate`, summed across the two solver calls and one triage call for each distinct reported question. I have no measured tokens or current bill because the key was unavailable; I would measure a small representative batch before promising a number.

### How would you evaluate without ground truth?

Start by manually adjudicating a stratified sample: answer-key, content, display/app, language, junk, and injection cases. Track precision of auto-apply separately from recall of defects. Audit all auto routes, sample no-change routes to catch missed defects, and have two subject reviewers resolve disagreements. Reviewer outcomes can grow the label set, but should be checked for reviewer consistency.

### What went wrong while building, and how did you catch it?

The parser first missed choices when the next `(B)` label touched the preceding option text; the real-data summary showed 26 questions with no parsed choices, so I fixed the boundary rule. A junk-text regex initially marked the valid comment “wrong” as gibberish; a pytest case caught it. BeautifulSoup repaired malformed MathML, which hid a broken fragment; a deliberately malformed guard test led to strict XML checking before tolerant HTML parsing. These are recorded in `ai_mistakes_log.md`.

### Why this stack?

Python keeps the engine short and works with Anthropic’s SDK, Pydantic, BeautifulSoup, and pytest. Pydantic makes shape errors visible, but does not validate physics. Vanilla JS/CSS is sufficient for a static JSON-driven console and avoids a build system. The trade-off is a localStorage-only audit and no multi-user persistence. I avoided LangChain because the flow is a small sequence of explicit calls and checks.

### Why precomputed results?

The console is a faculty review surface, not a model client. Precomputed JSON keeps the API key off the browser, makes the page cheap to host, and lets reviewers open a stable batch even if the model service is unavailable. It means a fresh report needs an offline engine run before it appears.

### How would you add Hindi support?

Keep original comments unchanged, detect the response language, ask for that language in the per-report reply schema, and add reviewed Hindi and Hinglish examples. Have fluent reviewers score correctness and tone, especially scientific terms. The current prompt asks for Hinglish matching, but this has not been exercised.

### What if requirements change during review?

For a new repair type, update `taxonomy.json`, add tests for allowed fields and route behavior, update the schema and prompt changelog, then rerun the pipeline on the affected cached-input version. For a stricter auto policy, change the code guard and its tests first. To change providers, replace the small client boundary in `engine/llm.py` while preserving the input isolation, schema, cache identity, and guard contracts. I would not silently reuse old cache entries after a prompt or model change.

### What is your urgency ordering and why?

Confirmed answer-key defects first because they can directly change exam marks; then defect severity and the number of distinct reporters; then cosmetic fixes; finally no-error and junk cases, which remain filterable. The queue documents this rule. Later I would include question exposure so urgency reflects students affected rather than only number of reports.

### Which UX decisions help a tired reviewer?

Group duplicate reports, keep source comments visible, render HTML/MathML, show a small before/after change, keep the evidence and guard outcomes nearby, and provide keyboard movement and decision shortcuts. The local browser audit makes the demo easy to try, but cannot serve as the real shared audit system.

### What about student privacy?

The API payload omits `studentId`, but contains report IDs and free-text comments. Those comments are still user data and may include personal details. A production rollout needs a data-retention and provider policy review, redaction where feasible, access control, and a way to remove data when required. The public assignment sample is pseudonymized, but that does not define production policy.

### Which metrics would you watch?

Time to faculty decision, proportion of cases reopened, defect precision/recall on reviewed samples, reviewer disagreement, override rate by guard, student appeal rate, and model/cache token use. The week-one headline metric is median time-to-decision for high-impact defects, always paired with harmful auto-edit audits.

### What can go wrong when an LLM solves a hard physics question?

It can make algebra or unit errors, misread MathML, assume a conventional diagram that is absent, or share a bias with the answer key. Two runs can agree on the same error. That is why the solution and deterministic checks matter, why ambiguous input goes to faculty, and why model agreement is evidence rather than truth.

### What files are in this repository and what do they do?

- `README.md`: setup, commands, static deployment instructions, and the original assignment brief.
- `pyproject.toml`: Python version and runtime/dev dependencies.
- `.env.example`: safe template for the local model key and model name; the actual `.env` is ignored.
- `.gitignore`: excludes secrets, local environments, and LLM response cache while allowing generated deliverables to be versioned.
- `data/questions.json`, `data/reports.json`, `data/taxonomy.json`: untouched source data.
- `engine/parser.py`: HTML cleanup, MathML retention, option splitting.
- `engine/data.py`: JSON loading and report grouping.
- `engine/comments.py`: injection/noise flags and quoted comment wrapper.
- `engine/checks.py`: deterministic question checks.
- `engine/markup.py`: strict XML validation for embedded MathML fragments.
- `engine/answer_checks.py`: conservative stored-solution answer extraction and comparison.
- `engine/schemas.py`: Pydantic output shapes.
- `engine/cache.py`: disk cache keyed by request hash.
- `engine/llm.py`: `.env` loading, Anthropic client, blind solve, and grouped triage.
- `engine/guards.py`: scoped, surgical, high-confidence edit validation.
- `engine/run_pipeline.py`: report-level pipeline and result writers; needs a real key.
- `engine/run_unreported.py`: all-question solver scan and candidate writer; needs a real key.
- `engine/deterministic_scan.py`: no-LLM findings summary across all questions.
- `engine/inspect_data.py`: concise input/parser summary.
- `engine/evaluate.py`: result route/verdict distribution and auto-apply listing.
- `prompts/solver_v1.md`, `prompts/triage_v1.md`: actual in-product prompts.
- `prompts/CHANGELOG.md`: prompt history and reasons.
- `PROMPTS.md`: verbatim prompt copies, decisions log, and intentionally unfilled reflection placeholders.
- `PRODUCT.md`: product trade-offs, highest-impact students, and proposed metric.
- `refer.md`: this personal study and interview guide.
- `ai_mistakes_log.md`: actual implementation mistakes and how checks caught them.
- `console/index.html`, `console/styles.css`, `console/app.js`: static accessible review console.
- `tests/`: unit and adversarial safety checks.
- `results.json`, `data/internal_cases.json`, `data/unreported_defects.json`: expected generated outputs, currently absent because no API key was available.

## Known limitations of this build

1. No Anthropic call has run; there are no real `results.json` decisions, student replies, confidence scores, or live deployment.
2. The model, prompts, tool schema, and runtime call path have not been validated against the live API or ground truth.
3. The deterministic checks are deliberately simple: the markup leak and junk detectors do not understand every HTML/MathML dialect or every kind of noise. Four source records contain MathML fragments that fail strict XML parsing.
4. Option splitting expects recognizable `(A)`–`(D)` labels. It can be confused by unusual markup, nested labels, or prose that happens to look like an option.
5. Numeric “last equality” extraction is weak by design. It is marked below the key-change auto threshold; it may disagree with a question asking for a conversion or scaled value.
6. The two solver calls share one model and may share a reasoning error. They are not independent experts.
7. Confidence 0.95 has not been calibrated. No accuracy or auto-apply safety claim should be made from the current tests.
8. The console’s audit history is localStorage and can be cleared or edited by the browser user. It is not an append-only server audit log and cannot update Acadza records.
9. Student language matching, especially Hindi/Hinglish science replies, is a prompt instruction only; it has not been reviewed.
10. No all-question result file has been made. A deterministic scan showing zero unreported candidates is not the same as solving all 43 questions.
