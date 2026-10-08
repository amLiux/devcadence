import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from migrate import decrypt, encrypt, pack_project, unpack_project


def test_pack_and_unpack_roundtrip(tmp_path):
    """Pack a fake project, encrypt, decrypt, unpack, verify contents."""
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    logs_dir = project_dir / "logs"
    logs_dir.mkdir()

    progress = {"project": "demo", "currentPhase": 1}
    (project_dir / "progress.json").write_text(json.dumps(progress))
    (logs_dir / "2026-10-06-huddle.json").write_text(json.dumps({"id": "2026-10-06-huddle"}))

    archive = pack_project(project_dir)
    encrypted, key = encrypt(archive)

    decrypted = decrypt(encrypted, key)
    assert decrypted == archive

    target = tmp_path / "imported"
    unpack_project(decrypted, target)

    assert (target / "progress.json").exists()
    assert json.loads((target / "progress.json").read_text()) == progress
    assert (target / "logs" / "2026-10-06-huddle.json").exists()


def test_unpack_rejects_path_traversal(tmp_path):
    """Malicious archive members that escape target dir should raise."""
    import io
    import tarfile

    target = tmp_path / "target"
    target.mkdir()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"evil"
        info = tarfile.TarInfo(name="../evil.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))

    with pytest.raises(ValueError):
        unpack_project(buf.getvalue(), target)
