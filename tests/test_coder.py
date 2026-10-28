import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from coder import (
    call_ollama,
    find_template,
    get_coder_config,
    load_spec,
    render_prompt,
)


def _example_spec():
    return {
        "ticketId": "DC-30",
        "task": "Add hello function",
        "acceptance": ["Function returns 'hello'"],
        "files": ["src/greet.py"],
        "context": {"src/greet.py": "# existing"},
        "constraints": ["Use only stdlib"],
        "output_format": "unified-diff",
        "coder": {
            "endpoint": "http://localhost:11434",
            "model": "qwen2.5-coder:7b",
            "temperature": 0.1,
        },
    }


def test_load_spec(tmp_path):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_example_spec()))
    loaded = load_spec(spec_path)
    assert loaded["ticketId"] == "DC-30"


def test_find_template_uses_shipped_default():
    text = find_template(None)
    assert "$task" in text
    assert "$output_format" in text


def test_find_template_uses_project_override(tmp_path):
    override = tmp_path / ".devcadence" / "prompts" / "coder.md"
    override.parent.mkdir(parents=True)
    override.write_text("OVERRIDE $task")
    text = find_template(str(tmp_path))
    assert text == "OVERRIDE $task"


def test_render_prompt_replaces_placeholders():
    prompt = render_prompt(find_template(None), _example_spec())
    assert "Add hello function" in prompt
    assert "Function returns 'hello'" in prompt
    assert "src/greet.py" in prompt
    assert "Use only stdlib" in prompt
    assert "unified-diff" in prompt


def test_get_coder_config_reads_spec():
    spec = _example_spec()
    endpoint, model, temperature, timeout = get_coder_config(spec)
    assert endpoint == "http://localhost:11434"
    assert model == "qwen2.5-coder:7b"
    assert temperature == 0.1


def test_get_coder_config_fallback_to_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENDPOINT", "http://other:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "other-model")
    spec = {"task": "x"}
    endpoint, model, temperature, timeout = get_coder_config(spec)
    assert endpoint == "http://other:11434"
    assert model == "other-model"


def _fake_urlopen(body_dict):
    """Return a fake urlopen context manager that yields a mock response."""

    def urlopen(req, timeout=None):
        response = MagicMock()
        response.read.return_value = json.dumps(body_dict).encode("utf-8")
        response.__enter__ = MagicMock(return_value=response)
        response.__exit__ = MagicMock(return_value=False)
        return response

    return urlopen


def test_call_ollama_returns_response(monkeypatch):
    monkeypatch.setattr(
        "coder.urllib.request.urlopen",
        _fake_urlopen({"response": "generated diff"}),
    )
    result = call_ollama("http://localhost:11434", "qwen2.5-coder:7b", "prompt", 0.1, 30)
    assert result["response"] == "generated diff"


def test_call_ollama_raises_on_connection_error(monkeypatch):
    import urllib.error

    def broken_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("coder.urllib.request.urlopen", broken_urlopen)
    try:
        call_ollama("http://localhost:11434", "qwen2.5-coder:7b", "prompt", 0.1, 30)
    except RuntimeError as e:
        assert "Cannot reach Ollama" in str(e)
    else:
        raise AssertionError("Expected RuntimeError")


def test_cli_dry_run(capsys, tmp_path):
    import coder as coder_module

    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_example_spec()))
    sys.argv = ["coder", "--spec", str(spec_path), "--dry-run"]
    try:
        coder_module.main()
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "Add hello function" in captured.out
    assert "unified-diff" in captured.out


def test_cli_json_success(monkeypatch, capsys, tmp_path):
    import coder as coder_module

    monkeypatch.setattr(
        "coder.urllib.request.urlopen",
        _fake_urlopen({"response": "@@ -0,0 +1 @@\n+hello"}),
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_example_spec()))
    sys.argv = ["coder", "--spec", str(spec_path), "--json"]
    try:
        coder_module.main()
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["ok"] is True
    assert "@@" in result["response"]


def test_cli_json_failure(monkeypatch, capsys, tmp_path):
    import coder as coder_module

    def broken_urlopen(req, timeout=None):
        import urllib.error
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("coder.urllib.request.urlopen", broken_urlopen)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_example_spec()))
    sys.argv = ["coder", "--spec", str(spec_path), "--json"]
    try:
        coder_module.main()
    except SystemExit as e:
        assert e.code == 1
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["ok"] is False
    assert "Cannot reach Ollama" in result["error"]


def test_cli_writes_output(monkeypatch, tmp_path):
    import coder as coder_module

    monkeypatch.setattr(
        "coder.urllib.request.urlopen",
        _fake_urlopen({"response": "generated"}),
    )
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_example_spec()))
    out_path = tmp_path / "out.diff"
    sys.argv = ["coder", "--spec", str(spec_path), "--output", str(out_path)]
    try:
        coder_module.main()
    except SystemExit as e:
        assert e.code == 0
    assert out_path.read_text() == "generated"
