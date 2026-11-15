import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

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
