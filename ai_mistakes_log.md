# AI mistakes log

## Parser initially missed adjacent option labels

- **What happened:** The first parser version required an option label to be preceded by whitespace or punctuation. In the production HTML, choices can be concatenated (`50 V(B)`), so it reported 26 questions with no options.
- **How it was caught:** I ran the parser on the supplied data and checked the summary against the visible A–D options in the question records.
- **Correction:** Removed the preceding-character constraint and reran the parser. It now finds four choices on 32 records; one three-choice record and ten zero-choice records remain for later deterministic checks (including integer questions).
