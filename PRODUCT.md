# Product note: protect the next student

When a question is broken, the student who loses most is the one studying alone under exam pressure: they may trust a wrong key, lose marks, or spend scarce revision time doubting correct work. A question can hurt many more students before a faculty member sees the report. The queue groups duplicate reports, raises confirmed answer-key issues and widely reported structural defects, and shows the original question, evidence, comments, and proposed change together so a reviewer can judge the source rather than a confident summary.

I would never let the system auto-author a missing diagram, invent a distractor, rewrite a question whose meaning is unclear, or change an answer key without independent support. Authored content and answer keys affect marks. The current guard policy makes answer-key edits faculty-only unless two blind solves and an explicit stored-solution answer agree, and still subjects them to the shared confidence and edit checks. A model can be confidently wrong, and two solves from one model can share the same blind spot.

**Week-one metric:** median time from report arrival to a faculty decision, segmented by answer-key and structural defects. Faster closure matters only if the harmful-auto-edit rate remains zero, so I would pair any speed improvement with manual audits of every auto-routed answer change.

**Beyond the brief:** use question exposure counts to estimate how many students may see a reported defect before it is fixed. That can make urgency reflect actual student impact, while keeping faculty review in control.

**Current limitation:** the engine and console are implemented, but this workspace had no Groq API key. No AI verdicts, confidence scores, student replies, or result file have been generated. The 0.95 auto threshold is a cautious initial setting and still needs calibration on adjudicated examples.
