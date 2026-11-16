import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("curl") is None,
    reason="installer/updater tests need bash and curl",
)

EXPECTED_SCRIPTS = [
    "tickets.py",
    "logs.py",
    "progress.py",
    "storage.py",
    "update.py",
    "migrate.py",
    "coder.py",
    "coder_prompt.md",
]


def _managed_scripts(script_name):
    text = (ROOT / script_name).read_text()
    match = re.search(r'^MANAGED_SCRIPTS="([^"]*)"', text, re.MULTILINE)
    assert match, f"{script_name} does not declare MANAGED_SCRIPTS"
    return match.group(1).split()


def test_install_and_update_manage_same_scripts():
    assert _managed_scripts("install.sh") == _managed_scripts("update.sh")


def test_managed_scripts_cover_skill_file_manifest():
    assert _managed_scripts("install.sh") == EXPECTED_SCRIPTS


def test_installer_downloads_scripts():
    text = (ROOT / "install.sh").read_text()
    assert 'log "Installing scripts/..."' in text
    assert 'mkdir -p scripts' in text
    assert 'for script in $MANAGED_SCRIPTS' in text
    assert 'scripts/$script missing' in text


def test_installer_ships_security_md_without_overwriting():
    text = (ROOT / "install.sh").read_text()
    assert 'log "Installing SECURITY.md..."' in text
    assert '[ -f "SECURITY.md" ]' in text
    assert '$REPO_RAW/SECURITY.md' in text


def test_updater_restores_missing_security_md():
    text = (ROOT / "update.sh").read_text()
    assert 'log "Checking SECURITY.md..."' in text
    assert '[ -f "SECURITY.md" ]' in text
    assert '$REPO_RAW/SECURITY.md' in text


def test_command_template_has_no_machine_specific_paths():
    text = (ROOT / "commands" / "devcadence.md").read_text()
    for forbidden in ("/Users/", "/home/", "devdock"):
        assert forbidden not in text, f"template leaks {forbidden!r}"


def test_command_template_uses_generic_project_root():
    text = (ROOT / "commands" / "devcadence.md").read_text()
    assert "git top-level directory" in text


def _seed_install(tmp_path, config_lines):
    (tmp_path / ".opencode" / "skills" / "devcadence").mkdir(parents=True)
    (tmp_path / ".opencode" / "skills" / "devcadence" / "SKILL.md").write_text("stub\n")
    command = tmp_path / ".opencode" / "commands" / "devcadence.md"
    command.parent.mkdir(parents=True)
    command.write_text(
        'skill({ name: "devcadence" })\n\n# Project Config\n\n```markdown\n'
        + "\n".join(config_lines)
        + "\n```\n"
    )
    return command


def _run_update(tmp_path):
    script = tmp_path / "run-update.sh"
    script.write_text(
        (ROOT / "update.sh")
        .read_text()
        .replace("https://raw.githubusercontent.com/amLiux/devcadence/main", ROOT.as_uri())
    )
    return subprocess.run(
        ["bash", str(script)], cwd=tmp_path, capture_output=True, text=True
    )


def test_update_warns_on_legacy_devdock_config(tmp_path):
    command = _seed_install(
        tmp_path,
        ["# - Log dir: ~/docs/devdock/", "# - Progress: ~/docs/devdock/progress.json", "# - Ticket format: dd-01"],
    )

    result = _run_update(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Legacy config detected" in result.stdout
    assert "~/docs/devdock/" in result.stdout
    assert "/devcadence setup" in result.stdout
    # preserved, never auto-rewritten
    assert "docs/devdock" in command.read_text()


def test_update_does_not_warn_on_project_config(tmp_path):
    command = _seed_install(
        tmp_path,
        ["# - Log dir: ~/docs/my-project/", "# - Progress: ~/docs/my-project/progress.json", "# - Ticket format: MP-01"],
    )

    result = _run_update(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Legacy config detected" not in result.stdout
    assert "~/docs/my-project/" in command.read_text()
