"""Build a reproducible source ZIP with an internal SHA-256 inventory.

Default output contains the complete project including ``devtools/``.  Use
``--without-devtools`` for a smaller runtime/development source package after
validation has already been completed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
BASE_TOP = {"src", "scripts", "scenarios", "packaging", "LICENSES", "docs", ".github"}
ROOT_FILES = {
    ".gitignore", ".gitattributes", "pyproject.toml",
    "README.md", "requirements.txt", "VERSION",
}
BANNED_ANYWHERE = {"__pycache__", ".pytest_cache", ".git", "node_modules"}
BANNED_TOP_LEVEL = {"var", "release", "build", "dist", ".venv", ".venv-build"}


def build_archive(*, include_devtools: bool = True, output_dir: Path | None = None) -> dict:
    top = set(BASE_TOP)
    suffix = "source"
    if include_devtools:
        top.add("devtools")
    else:
        suffix = "source-no-devtools"

    dest = Path(output_dir) if output_dir else ROOT / "release" / f"v{VERSION}"
    dest.mkdir(parents=True, exist_ok=True)
    archive_path = dest / f"LTE-Control-Plane-Simulator-v{VERSION}-{suffix}.zip"

    entries: list[tuple[str, bytes]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in BANNED_ANYWHERE or part.endswith(".egg-info") for part in rel.parts):
            continue
        # Build artefact directories are banned only at project root.  The
        # maintained helper package ``scripts/build/`` is source and must ship.
        if rel.parts[0] in BANNED_TOP_LEVEL:
            continue
        if path.suffix in {".pyc", ".pyo", ".tmp", ".log", ".exe"}:
            continue
        if rel.parts[:2] == ("docs", "weekly-reports") and path.suffix.lower() == ".pdf":
            continue
        if rel.parts[:2] == ("docs", "reference") and path.suffix.lower() == ".pdf":
            continue
        if rel.as_posix() == "packaging/SOURCE-MANIFEST.json":
            continue
        if not (rel.parts[0] in top or rel.as_posix() in ROOT_FILES):
            continue
        entries.append((rel.as_posix(), path.read_bytes()))

    manifest = {
        name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in entries
    }
    prefix = f"lte-control-plane-sim-engineering-v{VERSION}/"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in entries:
            archive.writestr(prefix + name, data)
        archive.writestr(
            prefix + "packaging/SOURCE-MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    return {
        "file": str(archive_path),
        "files": len(entries) + 1,
        "bytes": archive_path.stat().st_size,
        "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "devtoolsIncluded": include_devtools,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Package LTE simulator source")
    parser.add_argument(
        "--without-devtools",
        action="store_true",
        help="exclude optional tests/validation tools under devtools/",
    )
    parser.add_argument("--output-dir", type=Path, help="override output directory")
    args = parser.parse_args()
    print(json.dumps(build_archive(
        include_devtools=not args.without_devtools,
        output_dir=args.output_dir,
    ), ensure_ascii=False))


if __name__ == "__main__":
    main()
