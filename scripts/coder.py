#!/usr/bin/env python3
"""DevCadence local coder — generate code/diff from a spec using a local LLM."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from string import Template

DEFAULT_ENDPOINT = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT = 120

# Embedded fallback template. The default shipped template lives next to this
# script as coder_prompt.md and can be overridden per project at
# .devcadence/prompts/coder.md.
DEFAULT_TEMPLATE = """\
You are a local code generator. You receive a strict, self-contained spec.
Do not improvise. Do not explain. Only emit the requested output.

Task:
$task

Acceptance criteria:
$acceptance

Files to modify or create:
$files

Relevant existing context:
$context

Constraints you must follow:
$constraints

Output format:
$output_format

Rules:
- Follow every constraint.
- If output_format is "unified-diff", emit a valid unified diff that can be applied with `patch -p1`.
- If output_format is "full-files", emit complete file contents in fenced code blocks with the file path on the same line (e.g. ```python path/to/file.py).
- Do not include markdown explanations, summaries, or chat text outside the diff or code blocks.
"""


def load_spec(path):
    with open(path) as f:
        return json.load(f)


def find_template(project_root):
    """Return override template if present, else the shipped default."""
    if project_root:
        override = Path(project_root) / ".devcadence" / "prompts" / "coder.md"
        if override.exists():
            return override.read_text()

    shipped = Path(__file__).with_name("coder_prompt.md")
    if shipped.exists():
        return shipped.read_text()

    return DEFAULT_TEMPLATE


def render_list(items, bullet="-"):
    if not items:
        return "(none)"
    return "\n".join(f"{bullet} {item}" for item in items)


def render_context(context):
    if not context:
        return "(none provided)"
    parts = []
    for path, content in context.items():
        parts.append(f"--- {path} ---")
        parts.append(content if content else "(empty)")
    return "\n".join(parts)


def render_prompt(template_text, spec):
    coder_cfg = spec.get("coder", {})
    params = {
        "task": spec.get("task", "").strip() or "(no task)",
        "acceptance": render_list(spec.get("acceptance", [])),
        "files": render_list(spec.get("files", [])),
        "context": render_context(spec.get("context", {})),
        "constraints": render_list(spec.get("constraints", [])),
        "output_format": spec.get("output_format", "unified-diff"),
    }
    return Template(template_text).safe_substitute(params)


def get_coder_config(spec):
    """Merge coder config from spec, env, and defaults."""
    cfg = spec.get("coder", {})
    endpoint = cfg.get("endpoint") or os.environ.get("OLLAMA_ENDPOINT") or DEFAULT_ENDPOINT
    model = cfg.get("model") or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL
    temperature = cfg.get("temperature", 0.1)
    timeout = cfg.get("timeout") or int(os.environ.get("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT))
    return endpoint, model, temperature, timeout


def call_ollama(endpoint, model, prompt, temperature, timeout):
    url = endpoint.rstrip("/") + "/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "options": {"temperature": temperature},
        "stream": False,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ollama HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Ollama at {url}: {e.reason}") from e


def main():
    parser = argparse.ArgumentParser(
        description="Generate code/diff from a spec using a local LLM (e.g. Ollama)."
    )
    parser.add_argument("--spec", required=True, help="Path to the JSON spec file")
    parser.add_argument("--project-root", help="Project root for prompt override lookup")
    parser.add_argument("--output", "-o", help="File to write generated output")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="Print the rendered prompt and exit")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout in seconds")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"Spec not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    spec = load_spec(spec_path)
    template_text = find_template(args.project_root)
    prompt = render_prompt(template_text, spec)

    if args.dry_run:
        print(prompt)
        sys.exit(0)

    endpoint, model, temperature, _ = get_coder_config(spec)
    timeout = args.timeout

    try:
        result = call_ollama(endpoint, model, prompt, temperature, timeout)
    except RuntimeError as e:
        if args.json:
            print(json.dumps({"ok": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    generated = result.get("response", "")

    if args.output:
        Path(args.output).write_text(generated)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "model": model,
                    "endpoint": endpoint,
                    "response": generated,
                },
                indent=2,
            )
        )
    else:
        print(generated)
        if args.output:
            print(f"\nSaved to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
