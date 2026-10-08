#!/usr/bin/env python3
"""DevCadence migration assistant — export, serve, and import project logs."""

import argparse
import base64
import io
import json
import os
import secrets
import socket
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

from cryptography.fernet import Fernet

try:
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.responses import StreamingResponse
except ImportError:
    uvicorn = None
    FastAPI = None
    Header = None
    HTTPException = None
    StreamingResponse = None

DEFAULT_DOCS_DIR = Path.home() / "docs"
LOG_DIR_ENV = "DEVCADENCE_LOG_DIR"
PROGRESS_ENV = "PROGRESS_JSON"
TRANSFER_TTL_SECONDS = 600  # 10 minutes
APP_NAME = "DevCadence Migration"

# In-memory store for active transfers.
_transfers = {}


def find_project_dirs():
    """Discover DevCadence project directories under ~/docs/."""
    dirs = []
    if not DEFAULT_DOCS_DIR.exists():
        return dirs
    for project_dir in sorted(DEFAULT_DOCS_DIR.iterdir()):
        if project_dir.is_dir():
            progress = project_dir / "progress.json"
            if progress.exists():
                dirs.append((project_dir.name, project_dir))
    return dirs


def load_progress(path):
    with open(path) as f:
        return json.load(f)


def pack_project(project_dir: Path) -> bytes:
    """Create a tar.gz archive containing progress.json and logs/."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        progress = project_dir / "progress.json"
        if progress.exists():
            tar.add(progress, arcname="progress.json")
        logs = project_dir / "logs"
        if logs.exists():
            for log_file in sorted(logs.glob("*.json")):
                tar.add(log_file, arcname=f"logs/{log_file.name}")
    return buf.getvalue()


def unpack_project(archive_bytes: bytes, target_dir: Path):
    """Extract tar.gz archive into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO(archive_bytes)
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        def is_within_directory(directory, target):
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
            prefix = os.path.commonprefix([abs_directory, abs_target])
            return prefix == abs_directory

        for member in tar.getmembers():
            member_path = os.path.join(target_dir, member.name)
            if not is_within_directory(target_dir, member_path):
                raise ValueError(f"Archive member escapes target dir: {member.name}")
        tar.extractall(path=target_dir)


def encrypt(data: bytes) -> tuple[bytes, str]:
    key = Fernet.generate_key()
    f = Fernet(key)
    return f.encrypt(data), key.decode()


def decrypt(encrypted: bytes, key: str) -> bytes:
    f = Fernet(key.encode())
    return f.decrypt(encrypted)


def encode_transfer(endpoint: str, code: str, token: str, key: str) -> str:
    payload = json.dumps({"e": endpoint, "c": code, "t": token, "k": key})
    return "dcm-" + base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_transfer(transfer_code: str) -> dict:
    if not transfer_code.startswith("dcm-"):
        raise ValueError("Invalid transfer code: must start with dcm-")
    b64 = transfer_code[4:] + "=" * (-len(transfer_code[4:]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(b64).decode())
    return payload


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def build_app() -> "FastAPI":
    app = FastAPI(title=APP_NAME)

    @app.get("/health")
    def health():
        return {"status": "ok", "transfers": len(_transfers)}

    @app.get("/download/{code}")
    def download(code: str, authorization: str = Header(None)):
        transfer = _transfers.get(code)
        if not transfer:
            raise HTTPException(status_code=404, detail="Transfer not found or expired")
        expected = f"Bearer {transfer['token']}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid token")
        data = transfer["data"]
        del _transfers[code]
        return StreamingResponse(io.BytesIO(data), media_type="application/octet-stream")

    return app


def cmd_discover(args):
    dirs = find_project_dirs()
    if not dirs:
        print("No DevCadence projects found under ~/docs/.")
        return
    print(f"\n{'Project':20} Path")
    print("-" * 60)
    for name, path in dirs:
        print(f"  {name:20} {path}")
    print()


def cmd_export(args):
    project_dir = Path(args.project)
    if not project_dir.exists():
        dirs = dict(find_project_dirs())
        if args.project in dirs:
            project_dir = dirs[args.project]
        else:
            print(f"Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)

    archive = pack_project(project_dir)
    encrypted, key = encrypt(archive)

    if args.serve:
        if uvicorn is None:
            print("Serve mode requires fastapi and uvicorn. Install: pip install devcadence[migrate]", file=sys.stderr)
            sys.exit(1)

        code = secrets.token_urlsafe(8)
        token = secrets.token_urlsafe(16)
        _transfers[code] = {
            "token": token,
            "data": encrypted,
            "created_at": time.time(),
        }

        port = args.port or find_free_port()
        host = args.host or get_local_ip()
        endpoint = f"http://{host}:{port}"
        transfer_code = encode_transfer(endpoint, code, token, key)

        print(f"\nServing migration for: {project_dir.name}")
        print(f"Endpoint: {endpoint}")
        print(f"Transfer code: {transfer_code}")
        print(f"Expires in {TRANSFER_TTL_SECONDS} seconds or after first download.\n")

        app = build_app()
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        out_path = args.output or project_dir.parent / f"{project_dir.name}-{time.strftime('%Y%m%d')}.dcm"
        with open(out_path, "wb") as f:
            f.write(encrypted)
        print(f"\nExported encrypted archive to: {out_path}")
        print(f"Decryption key (save this): {key}\n")


def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def cmd_import(args):
    if args.file:
        if not args.key:
            print("--key required when importing from --file", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "rb") as f:
            encrypted = f.read()
        archive = decrypt(encrypted, args.key)
    else:
        if not args.code:
            print("Transfer code or --file required", file=sys.stderr)
            sys.exit(1)
        payload = decode_transfer(args.code)
        endpoint = payload["e"]
        code = payload["c"]
        token = payload["t"]
        key = payload["k"]

        url = f"{endpoint}/download/{code}"
        try:
            encrypted = http_get(url, headers={"Authorization": f"Bearer {token}"})
        except urllib.error.HTTPError as e:
            print(f"Download failed: {e.code} {e.reason}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Download failed: {e}", file=sys.stderr)
            sys.exit(1)

        archive = decrypt(encrypted, key)

    target = Path(args.target)
    target.mkdir(parents=True, exist_ok=True)
    unpack_project(archive, target)

    progress_path = target / "progress.json"
    if progress_path.exists():
        data = load_progress(progress_path)
        print(f"\nImported project: {data.get('project', 'unknown')}")
    print(f"Files extracted to: {target.resolve()}\n")


def main():
    parser = argparse.ArgumentParser(description="DevCadence migration assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("discover", help="List discoverable DevCadence projects")

    p_export = subparsers.add_parser("export", help="Export project to encrypted archive")
    p_export.add_argument("project", help="Project name or path")
    p_export.add_argument("--serve", action="store_true", help="Serve archive via temporary API")
    p_export.add_argument("--host", help="Bind host for serve mode")
    p_export.add_argument("--port", type=int, help="Bind port for serve mode")
    p_export.add_argument("-o", "--output", help="Output file for archive mode")

    p_import = subparsers.add_parser("import", help="Import project from transfer code or local archive")
    p_import.add_argument("target", help="Target directory for import")
    p_import.add_argument("code", nargs="?", help="Transfer code from export --serve")
    p_import.add_argument("--file", help="Import from a local encrypted archive file")
    p_import.add_argument("--key", help="Decryption key for local archive import")

    args = parser.parse_args()

    if args.command == "discover":
        cmd_discover(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "import":
        cmd_import(args)


if __name__ == "__main__":
    main()
