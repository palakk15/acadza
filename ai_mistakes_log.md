# AI mistakes log

## Parser initially missed adjacent option labels

- **What happened:** The first parser version required an option label to be preceded by whitespace or punctuation. In the production HTML, choices can be concatenated (`50 V(B)`), so it reported 26 questions with no options.
- **How it was caught:** I ran the parser on the supplied data and checked the summary against the visible A–D options in the question records.
- **Correction:** Removed the preceding-character constraint and reran the parser. It now finds four choices on 32 records; one three-choice record and ten zero-choice records remain for later deterministic checks (including integer questions).

## First safety test run exposed two guard-classifier bugs

- **What happened:** The initial junk-comment rule labelled the valid report `wrong` as gibberish, and the forgiving HTML parser repaired a deliberately broken MathML fragment before the guard could reject it.
- **How it was caught:** The first pytest run returned 2 failures out of 15, including explicit adversarial cases for valid short feedback and malformed MathML.
- **Correction:** Restricted gibberish detection to clearly keyboard-mashed text and made MathML validation parse the original XML fragments strictly before the forgiving HTML parser runs. Rerun the suite after these fixes.
