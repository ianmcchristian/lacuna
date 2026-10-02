"""Deploy the API to a Hugging Face Docker Space.

Usage: uv run python scripts/deploy_space.py
Env:   HF_TOKEN (write), LACUNA_DATABASE_URL, optional SPACE_ID and CORS_ORIGINS.

Uploads only what the Dockerfile needs, sets the runtime secrets, then waits
until /ready reports the model loaded and the database reachable.
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import httpx
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SPACE_ID = os.environ.get("SPACE_ID", "ianmcchristian/lacuna")
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", '["https://ianmcchristian.github.io", "http://localhost:5173"]'
)
FILES = [
    "Dockerfile",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "LICENSE",
    "alembic.ini",
    "scripts/download_weights.py",
]
DIRS = ["lacuna", "migrations"]

# Space settings live in the README front matter
SPACE_README = """---
title: Lacuna
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 8080
pinned: false
license: agpl-3.0
short_description: Finds empty shelf space in retail shelf photos
---

API for [Lacuna](https://github.com/ianmcchristian/lacuna). Deployed from GitHub
Actions; edit the code there, not here. Docs at `/docs`.
"""


def space_url(space_id: str) -> str:
    owner, name = space_id.split("/")
    return f"https://{owner}-{name}.hf.space".lower()


def stage(target: Path) -> None:
    for name in FILES:
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target / name)
    for name in DIRS:
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__"))
    (target / "README.md").write_text(SPACE_README)


def wait_ready(url: str, timeout_s: int = 1200) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{url}/ready", timeout=15)
            last = f"{resp.status_code} {resp.text[:200]}"
            if resp.status_code == 200:
                body: dict[str, object] = resp.json()
                return body
        except httpx.HTTPError as err:
            last = repr(err)
        time.sleep(15)
    raise SystemExit(f"space never got ready, last response: {last}")


def main() -> None:
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(SPACE_ID, repo_type="space", space_sdk="docker", exist_ok=True)
    api.add_space_secret(SPACE_ID, "LACUNA_DATABASE_URL", os.environ["LACUNA_DATABASE_URL"])
    api.add_space_variable(SPACE_ID, "LACUNA_CORS_ORIGINS", json.dumps(json.loads(CORS_ORIGINS)))

    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp))
        commit = api.upload_folder(
            repo_id=SPACE_ID,
            repo_type="space",
            folder_path=tmp,
            commit_message=f"Deploy {os.environ.get('GITHUB_SHA', 'local')[:7]}",
            delete_patterns=[f"{name}/**" for name in DIRS],  # drop files removed from src
        )
    print(f"uploaded: {commit.commit_url}")

    url = space_url(SPACE_ID)
    print(f"waiting for {url}/ready")
    print(f"ready: {wait_ready(url)}")


if __name__ == "__main__":
    main()
