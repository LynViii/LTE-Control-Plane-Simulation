from __future__ import annotations

import argparse
import importlib.metadata as metadata
import shutil
import sys
from pathlib import Path

# Runtime/build components that can be present in the frozen Windows release.
# Optional/transitive entries are copied when installed; required entries fail the release build when absent.
REQUIRED = ("cryptography", "jsonschema", "PyYAML", "cffi", "pywebview", "PyInstaller")
OPTIONAL = ("attrs", "jsonschema-specifications", "referencing", "rpds-py", "pycparser", "proxy-tools", "typing_extensions", "pythonnet", "clr-loader", "altgraph", "pefile", "pywin32-ctypes", "packaging", "setuptools", "Pillow", "pyinstaller-hooks-contrib")
LICENSE_NAMES = {"LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt", "NOTICE", "NOTICE.txt"}


def _safe(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)


def _copy_distribution_licenses(dist_name: str, destination: Path) -> tuple[str, str, int]:
    dist = metadata.distribution(dist_name)
    version = dist.version
    copied = 0
    seen: set[Path] = set()
    for file in dist.files or []:
        basename = Path(str(file)).name
        upper = basename.upper()
        if upper not in {name.upper() for name in LICENSE_NAMES} and not upper.startswith(("LICENSE.", "NOTICE.")):
            continue
        source = Path(dist.locate_file(file))
        if not source.is_file() or source in seen:
            continue
        seen.add(source)
        target = destination / f"{_safe(dist.metadata['Name'] or dist_name)}-{_safe(version)}-{_safe(basename)}"
        shutil.copy2(source, target)
        copied += 1
    expression = dist.metadata.get("License-Expression") or dist.metadata.get("License") or "unspecified"
    return version, expression.replace("\n", " ").strip(), copied


def _copy_python_license(destination: Path) -> bool:
    candidates = [
        Path(sys.base_prefix) / "LICENSE_PYTHON.txt",
        Path(sys.base_prefix) / "LICENSE.txt",
        Path(sys.base_prefix) / "LICENSE",
        Path(sys.prefix) / "LICENSE.txt",
        Path(sys.prefix) / "LICENSE",
    ]
    candidates.extend((Path(sys.base_prefix)/'pkgs').glob(f'python-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}-*/LICENSE_PYTHON.txt'))
    for source in candidates:
        if source.is_file():
            shutil.copy2(source, destination / f"CPython-{sys.version_info.major}.{sys.version_info.minor}-LICENSE.txt")
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)

    inventory = [f"Python {sys.version.split()[0]}"]
    failures: list[str] = []
    for name in (*REQUIRED, *OPTIONAL):
        try:
            version, license_expression, copied = _copy_distribution_licenses(name, destination)
            inventory.append(f"{name}=={version} | license={license_expression} | copied_license_files={copied}")
            if name in REQUIRED and copied == 0:
                failures.append(f"{name}: no LICENSE/COPYING/NOTICE file found in installed distribution")
        except metadata.PackageNotFoundError:
            if name in REQUIRED:
                failures.append(f"{name}: distribution not installed")

    # Native runtime licenses from the actual Conda package cache, when present.
    import ssl
    openssl_version = ssl.OPENSSL_VERSION.split()[1]
    cache = Path(sys.base_prefix) / 'pkgs'
    native_patterns = {
        'OpenSSL': f'openssl-{openssl_version}-*/info/licenses/LICENSE.txt',
        'Tcl': 'tk-*/info/licenses/tcl*/license.terms',
        'Tk': 'tk-*/Library/lib/tk8.6/license.terms',
    }
    for component, pattern in native_patterns.items():
        found = list(cache.glob(pattern))
        for index, source in enumerate(found):
            shutil.copy2(source, destination / f'{component}-{index}-LICENSE.txt')
        inventory.append(f'{component} native license files copied={len(found)}')
    python_license = _copy_python_license(destination)
    inventory.append(f"CPython license copied={python_license}")
    if not python_license:
        failures.append("CPython: LICENSE.txt/LICENSE not found under sys.prefix")

    (destination / "dependency-inventory.txt").write_text("\n".join(inventory) + "\n", encoding="utf-8")
    if failures:
        print("Third-party license collection failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
