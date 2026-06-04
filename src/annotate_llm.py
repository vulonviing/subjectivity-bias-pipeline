"""Step: annotate_llm — LLM sentence annotation via OpenAI Batch API.

Model: gpt-5.4-mini (snapshot pin: gpt-5.4-mini-2026-03-17, verified 2026-06-01)
    - Context window: 400,000 tokens; max output: 128,000 tokens.
    - Endpoint: /v1/chat/completions (Batch API, Structured Outputs).
    - %50 cost discount vs synchronous API.

Workflow (three subcommands):
    submit  -- build JSONL, upload to OpenAI Files, create batch, save state
    status  -- poll batch status, show request counts
    fetch   -- download completed output, join with input, write llm_annotations.jsonl

Prompt and response schema are DEFERRED to a later step. `submit` will fail
with a clear error until prompts/llm_sentence_annotation.txt and
prompts/llm_response_schema.json are finalized.

Only cleaned sentence text is sent to the model. Outlet name, URL, title,
and image metadata are preserved in the output for analysis but never
included in the model input.

LLM labels are SILVER / REFERENCE annotations — never "gold".
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_INPUT = "data/processed/proxy_predictions.jsonl"
DEFAULT_OUTPUT = "data/processed/llm_annotations.jsonl"
DEFAULT_STATE = "data/processed/llm_batch_state.json"
DEFAULT_PROMPT_PATH = "prompts/llm_sentence_annotation.txt"
DEFAULT_SCHEMA_PATH = "prompts/llm_response_schema.json"
BATCH_ENDPOINT = "/v1/chat/completions"
COMPLETION_WINDOW = "24h"
_PLACEHOLDER_MARKERS = ("PLACEHOLDER", "deferred")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


def _load_env_model() -> tuple[str, str]:
    """Return (resolved_model_id, display_string) from env with fallbacks."""
    snapshot = os.getenv("OPENAI_MODEL_SNAPSHOT", "").strip()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip()
    resolved = snapshot if snapshot else model
    return resolved, resolved


def _require_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        sys.exit("OPENAI_API_KEY is not set. Add it to .env or set the environment variable.")
    return key


def _load_prompt(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Prompt file not found: {path}")
    content = p.read_text(encoding="utf-8").strip()
    if not content:
        sys.exit(f"Prompt file is empty: {path}")
    for marker in _PLACEHOLDER_MARKERS:
        if marker.lower() in content.lower():
            sys.exit(
                f"Prompt is still a placeholder — design {path} before running submit. "
                f"(Found marker: '{marker}')"
            )
    return content


def _load_schema(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Response schema file not found: {path}")
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"Response schema file is not valid JSON: {path} — {e}")
    comment = obj.get("_comment", "")
    for marker in _PLACEHOLDER_MARKERS:
        if marker.lower() in comment.lower():
            sys.exit(
                f"Response schema is still a placeholder — design {path} before running submit. "
                f"(Found marker: '{marker}' in _comment)"
            )
    return obj


def _iter_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _load_state(state_path: str) -> dict:
    p = Path(state_path)
    if not p.exists():
        sys.exit(
            f"State file not found: {state_path}\n"
            "Run `python src/annotate_llm.py submit` first to create a batch."
        )
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------

def cmd_submit(args: argparse.Namespace) -> None:
    load_dotenv()

    if args.model:
        resolved_model = model_display = args.model.strip()
    else:
        resolved_model, model_display = _load_env_model()

    if not args.dry_run:
        _require_api_key()

    log.info("Model: %s", model_display)
    if args.dry_run:
        log.info("DRY RUN mode — no API calls will be made.")

    prompt_text = _load_prompt(args.prompt)
    schema_obj = _load_schema(args.schema)

    # Prompt split convention: if file contains "--- user ---", split on it.
    # Whole text is treated as user message otherwise.
    # Format is finalized in the prompt design step.
    if "--- user ---" in prompt_text:
        parts = prompt_text.split("--- user ---", 1)
        system_text: str | None = parts[0].replace("--- system ---", "").strip() or None
        user_template = parts[1].strip()
    else:
        system_text = None
        user_template = prompt_text

    if "{sentence}" not in user_template:
        sys.exit(
            "User prompt template must contain the {sentence} placeholder. "
            f"Check {args.prompt}."
        )

    log.info("Loading input from %s", args.input)
    rows = list(_iter_jsonl(args.input))
    log.info("  %d rows loaded", len(rows))

    batch_lines: list[dict] = []
    skipped = 0
    for row in rows:
        text = row.get("text", "").strip()
        if not text:
            log.warning("Empty text for sentence_id=%s — skipping", row.get("sentence_id"))
            skipped += 1
            continue
        messages: list[dict] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        try:
            user_content = user_template.format(sentence=text)
        except KeyError as e:
            sys.exit(
                f"User template has unknown placeholder {e}. "
                f"Only {{sentence}} is supported. Check {args.prompt}."
            )
        messages.append({"role": "user", "content": user_content})
        batch_lines.append({
            "custom_id": row["sentence_id"],
            "method": "POST",
            "url": BATCH_ENDPOINT,
            "body": {
                "model": resolved_model,
                "messages": messages,
                "response_format": {"type": "json_schema", "json_schema": schema_obj},
                "temperature": 0,
                "max_completion_tokens": 256,
                "seed": 42,
            },
        })

    n = len(batch_lines)
    log.info("Batch input: %d requests (skipped %d empty)", n, skipped)

    batch_input_path = Path(args.input).parent / "llm_batch_input.jsonl"
    with open(batch_input_path, "w", encoding="utf-8") as f:
        for line in batch_lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    log.info("Batch JSONL written: %s (%d lines)", batch_input_path, n)

    if args.dry_run:
        log.info("DRY RUN — first 3 batch lines:")
        for line in batch_lines[:3]:
            print(json.dumps(line, ensure_ascii=False, indent=2))
        log.info("DRY RUN complete. No files uploaded, no batch created.")
        return

    state_p = Path(args.state)
    if state_p.exists():
        existing = json.loads(state_p.read_text(encoding="utf-8"))
        if existing.get("batch_id"):
            sys.exit(
                f"State file already exists with batch_id={existing['batch_id']}. "
                f"Delete {args.state} to re-submit."
            )

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    log.info("Uploading batch input file to OpenAI Files...")
    with open(batch_input_path, "rb") as f:
        upload = client.files.create(file=f, purpose="batch")
    input_file_id = upload.id
    log.info("  Uploaded: file_id=%s", input_file_id)

    log.info("Creating batch (endpoint=%s, window=%s)...", BATCH_ENDPOINT, COMPLETION_WINDOW)
    batch = client.batches.create(
        input_file_id=input_file_id,
        endpoint=BATCH_ENDPOINT,
        completion_window=COMPLETION_WINDOW,
        metadata={"step": "annotate_llm", "n": str(n), "model": model_display},
    )
    log.info("  Batch created: batch_id=%s  status=%s", batch.id, batch.status)

    state = {
        "batch_id": batch.id,
        "input_file_id": input_file_id,
        "model": resolved_model,
        "endpoint": BATCH_ENDPOINT,
        "n_requests": n,
        "input_path": args.input,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    state_p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("State saved: %s", args.state)
    log.info("Next: `python src/annotate_llm.py status` to poll, then `fetch` when completed.")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    load_dotenv()
    state = _load_state(args.state)
    api_key = _require_api_key()
    client = OpenAI(api_key=api_key)
    batch_id = state["batch_id"]

    batch = client.batches.retrieve(batch_id)
    counts = batch.request_counts

    log.info("Batch ID     : %s", batch_id)
    log.info("Status       : %s", batch.status)
    log.info("Model        : %s", state.get("model"))
    log.info("Submitted at : %s", state.get("submitted_at"))
    log.info("Requests     : total=%s  completed=%s  failed=%s",
             counts.total, counts.completed, counts.failed)
    if batch.output_file_id:
        log.info("Output file  : %s", batch.output_file_id)
    if batch.error_file_id:
        log.warning("Error file   : %s", batch.error_file_id)

    if batch.status == "completed":
        log.info("=> Ready to fetch. Run `python src/annotate_llm.py fetch`.")
    elif batch.status in ("failed", "expired", "cancelled"):
        sys.exit(f"Batch ended with terminal status: {batch.status}")
    else:
        log.info("=> Batch still in progress (%s). Check again later.", batch.status)


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

def cmd_fetch(args: argparse.Namespace) -> None:
    load_dotenv()
    state = _load_state(args.state)
    api_key = _require_api_key()
    client = OpenAI(api_key=api_key)
    batch_id = state["batch_id"]
    resolved_model = state.get("model", DEFAULT_MODEL)

    batch = client.batches.retrieve(batch_id)
    if batch.status != "completed":
        sys.exit(
            f"Batch status is '{batch.status}', not 'completed'. "
            "Wait for completion before fetching."
        )

    output_file_id = batch.output_file_id
    if not output_file_id:
        sys.exit("Batch is completed but output_file_id is missing.")

    log.info("Loading original rows from %s", state["input_path"])
    original: dict[str, dict] = {}
    for row in _iter_jsonl(state["input_path"]):
        original[row["sentence_id"]] = row
    log.info("  %d original rows indexed", len(original))

    log.info("Downloading output file %s...", output_file_id)
    file_response = client.files.content(output_file_id)
    raw_lines = file_response.text.splitlines()
    log.info("  %d output lines received", len(raw_lines))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    err_path = out_path.parent / "llm_annotations.errors.jsonl"

    succeeded = failed = 0
    total_prompt_tokens = total_completion_tokens = 0

    with open(out_path, "w", encoding="utf-8") as out_f, \
         open(err_path, "w", encoding="utf-8") as err_f:

        for raw in raw_lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Could not parse output line (skipping): %s", raw[:80])
                failed += 1
                continue

            custom_id = item.get("custom_id")
            error = item.get("error")

            if error:
                log.warning("Request error for %s: %s", custom_id, error)
                err_f.write(
                    json.dumps({"custom_id": custom_id, "error": error}, ensure_ascii=False) + "\n"
                )
                failed += 1
                continue

            try:
                resp_body = item["response"]["body"]
                finish_reason = resp_body["choices"][0]["finish_reason"]
                content_str = resp_body["choices"][0]["message"]["content"]
                annotation = json.loads(content_str)
                usage = resp_body.get("usage", {})
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                log.warning("Parse failure for %s: %s", custom_id, e)
                err_f.write(
                    json.dumps(
                        {"custom_id": custom_id, "parse_error": str(e), "raw": raw[:500]},
                        ensure_ascii=False,
                    ) + "\n"
                )
                failed += 1
                continue

            out_row = dict(original.get(custom_id, {}))
            out_row.update({
                "llm_label": annotation.get("llm_label"),
                "llm_rationale": annotation.get("llm_rationale"),
                "llm_confidence": annotation.get("llm_confidence"),
                "llm_model": resolved_model,
                "llm_finish_reason": finish_reason,
            })
            if args.keep_raw:
                out_row["llm_raw_response"] = raw
            out_f.write(json.dumps(out_row, ensure_ascii=False) + "\n")
            succeeded += 1

    if failed == 0:
        err_path.unlink(missing_ok=True)

    # Rough cost estimate (gpt-5.4-mini batch pricing approximate).
    # Input: $0.15/1M → batch $0.075; Output: $0.60/1M → batch $0.30.
    cost_est = (
        (total_prompt_tokens / 1_000_000 * 0.075)
        + (total_completion_tokens / 1_000_000 * 0.30)
    )

    log.info("=== Fetch complete ===")
    log.info("  Succeeded      : %d", succeeded)
    log.info("  Failed         : %d", failed)
    log.info("  Prompt tokens  : %d", total_prompt_tokens)
    log.info("  Completion tok : %d", total_completion_tokens)
    log.info("  Cost estimate  : $%.4f (batch discount applied, rates approximate)", cost_est)
    if failed:
        log.warning("  Error report   : %s", err_path)
    log.info("Output: %s", out_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="LLM sentence annotation via OpenAI Batch API (submit / status / fetch)"
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("submit", help="Upload batch JSONL and create batch job")
    s.add_argument("--input", default=DEFAULT_INPUT)
    s.add_argument("--prompt", default=DEFAULT_PROMPT_PATH)
    s.add_argument("--schema", default=DEFAULT_SCHEMA_PATH)
    s.add_argument("--state", default=DEFAULT_STATE)
    s.add_argument("--model", default=None, help="Override model (default: OPENAI_MODEL_SNAPSHOT from .env)")
    s.add_argument("--dry-run", action="store_true",
                   help="Build JSONL and preview first 3 requests without calling the API")

    st = sub.add_parser("status", help="Poll and display batch status")
    st.add_argument("--state", default=DEFAULT_STATE)

    f = sub.add_parser("fetch", help="Download completed batch and write llm_annotations.jsonl")
    f.add_argument("--state", default=DEFAULT_STATE)
    f.add_argument("--output", default=DEFAULT_OUTPUT)
    f.add_argument("--keep-raw", action="store_true",
                   help="Include raw API response per row (for debugging)")

    return p


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "submit":
        cmd_submit(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "fetch":
        cmd_fetch(args)


if __name__ == "__main__":
    main()
