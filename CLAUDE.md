# Project Rules (CLAUDE.md)

These rules apply to **every** AI-assistant action in this repository.

## Rule 1 — Forward-only AI usage logging
For **every** discrete step the assistant performs (scaffolding, writing a script, running an experiment, fixing a bug, making a design decision, etc.), append a new entry to [ai_usage/step_logs.md](ai_usage/step_logs.md).

- **Append only.** Never edit or delete prior entries retroactively, even to fix typos or reframe a decision. If a previous step turned out wrong, add a new entry that supersedes it.
- **One entry per step.** Do not batch multiple unrelated steps into one entry.
- **Write the entry in the same turn** that produced the step — not later, not "I'll log this at the end."

## Entry format
```
## Step <N> — <short title> — <YYYY-MM-DD>
- **Goal:** what we set out to do
- **Action:** what the assistant did (scripts touched, commands run, decisions made)
- **Prompt / model:** which model + a one-line description of the prompt or instruction
- **Outcome:** result, files produced, anything that broke
- **Notes:** follow-ups, risks, things deferred
```

## Rule 2 — Scope discipline
Implement only what the current step asks for. Defer extras to a follow-up step (and log them).

## Rule 3 — Reproducibility
New dependencies → `requirements.txt`. New env vars → `.env.example`. New pipeline outputs → documented in `README.md`.

## Rule 4 — Project conventions
- **No `config.yaml`.** Runtime settings come from `.env`; small fixed constants live in `src/` modules.
- `.env` is **never** committed; `.env.example` is. Both are listed in `.gitignore` rules accordingly.
- All prompts live under `prompts/`. Do not inline prompts inside Python files.
- **Do not call LLM annotations "gold labels"** — they are silver / reference annotations.
- **Do not claim outlet-block effects are causal**, and **do not equate subjectivity with bias**, in code comments, docs, or report text.

## Rule 5 — External model facts must be verified
Before writing client code against an external model (OpenAI, HF, etc.), confirm the model ID, supported endpoints, modalities, context window, and output limits against the **official docs**, and record the verification in `ai_usage/step_logs.md`.

## Rule 6 — VLM image handling
Never send image **URLs** to the VLM. Always download, optionally resize/compress, base64-encode, and send the image inline. Keep `image_url` as dataset metadata only — never inside the prompt.
