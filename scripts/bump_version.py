from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def is_valid_semver(v: str) -> bool:
    return bool(SEMVER_RE.match(v))


def read_package_json_version(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("version")
    except Exception:
        return None


def write_package_json_version(path: Path, new_version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = new_version
    path.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_tauri_conf_version(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("version")
    except Exception:
        return None


def write_tauri_conf_version(path: Path, new_version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = new_version
    path.write_text(
        json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def read_cargo_toml_version(path: Path) -> Optional[str]:
    text = path.read_text(encoding="utf-8")
    m_section = re.search(r"(?ms)^\[package\].*?(?=^\[|\Z)", text)
    if not m_section:
        return None
    section = m_section.group(0)
    m_ver = re.search(r"^version\s*=\s*\"([^\"]+)\"", section, flags=re.M)
    if m_ver:
        return m_ver.group(1)
    m_ver2 = re.search(r"^version\s*=\s*\"([^\"]+)\"", text, flags=re.M)
    return m_ver2.group(1) if m_ver2 else None


def write_cargo_toml_version(path: Path, new_version: str) -> None:
    text = path.read_text(encoding="utf-8")

    def _replace(match: re.Match) -> str:
        sec = match.group(0)
        sec_new, n = re.subn(
            r"^version\s*=\s*\"([^\"]+)\"",
            f'version = "{new_version}"',
            sec,
            flags=re.M,
        )
        return sec_new

    new_text, nsec = re.subn(r"(?ms)^\[package\].*?(?=^\[|\Z)", _replace, text, count=1)
    if nsec == 0:
        new_text, nver = re.subn(
            r"^version\s*=\s*\"([^\"]+)\"",
            f'version = "{new_version}"',
            text,
            count=1,
            flags=re.M,
        )
        if nver == 0:
            raise RuntimeError("Could not find version line in Cargo.toml")
    path.write_text(new_text, encoding="utf-8")


def gather_versions(root: Path) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    pkg = root / "package.json"
    cargo = root / "src-tauri" / "Cargo.toml"
    tauri = root / "src-tauri" / "tauri.conf.json"

    out[str(pkg.relative_to(root))] = (
        read_package_json_version(pkg) if pkg.exists() else None
    )
    out[str(cargo.relative_to(root))] = (
        read_cargo_toml_version(cargo) if cargo.exists() else None
    )
    out[str(tauri.relative_to(root))] = (
        read_tauri_conf_version(tauri) if tauri.exists() else None
    )
    return out


def apply_version(
    root: Path, new_version: str, apply: bool
) -> Dict[str, Dict[str, Optional[str]]]:
    results: Dict[str, Dict[str, Optional[str]]] = {}
    pkg = root / "package.json"
    cargo = root / "src-tauri" / "Cargo.toml"
    tauri = root / "src-tauri" / "tauri.conf.json"

    files = [
        (pkg, read_package_json_version, write_package_json_version),
        (cargo, read_cargo_toml_version, write_cargo_toml_version),
        (tauri, read_tauri_conf_version, write_tauri_conf_version),
    ]

    for path, reader, writer in files:
        key = str(path.relative_to(root))
        if not path.exists():
            results[key] = {"old": None, "new": None}
            continue
        old = reader(path)
        results[key] = {"old": old, "new": new_version}
        if apply:
            backup = path.with_suffix(path.suffix + ".bak")
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            writer(path, new_version)

    return results


def undo_version(root: Path) -> Dict[str, Dict[str, Optional[str]]]:
    results: Dict[str, Dict[str, Optional[str]]] = {}
    pkg = root / "package.json"
    cargo = root / "src-tauri" / "Cargo.toml"
    tauri = root / "src-tauri" / "tauri.conf.json"

    files = [
        (pkg, read_package_json_version),
        (cargo, read_cargo_toml_version),
        (tauri, read_tauri_conf_version),
    ]

    for path, reader in files:
        key = str(path.relative_to(root))
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            old = reader(path) if path.exists() else None
            results[key] = {"old": old, "new": None}
            continue

        try:
            backup_bytes = backup.read_bytes()
            path.write_bytes(backup_bytes)
            try:
                backup.unlink()
            except Exception:
                pass
            old = None
            new = reader(path)
            results[key] = {"old": old, "new": new}
        except Exception:
            old = reader(path) if path.exists() else None
            results[key] = {"old": old, "new": None}

    return results


def print_preview(results: Dict[str, Dict[str, Optional[str]]], apply: bool) -> None:
    if apply:
        print("Applied new version to files:")
    else:
        print("Dry-run preview (no files modified). To apply, pass --apply")
    for path, pair in results.items():
        old = pair.get("old")
        new = pair.get("new")
        if old is None and new is None:
            print(f" - {path}: <file not found>")
        else:
            marker = "->"
            print(f" - {path}: {old!s} {marker} {new}")


def print_undo_preview(results: Dict[str, Dict[str, Optional[str]]]) -> None:
    print("Reverted files from backups:")
    for path, pair in results.items():
        old = pair.get("old")
        new = pair.get("new")
        if old is None and new is None:
            print(f" - {path}: <no backup found and file missing>")
        elif new is None:
            print(f" - {path}: <no backup found> current={old!s}")
        else:
            print(f" - {path}: restored -> {new}")


def print_current_versions(versions: Dict[str, Optional[str]]) -> None:
    print("Detected versions:")
    for path, ver in versions.items():
        if ver is None:
            print(f" - {path}: <not found>")
        else:
            print(f" - {path}: {ver}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Bump project versions in three files.")
    p.add_argument(
        "version",
        nargs="?",
        help="New semantic version (semver) to write (if omitted, show current versions)",
    )
    p.add_argument(
        "--apply",
        "-a",
        action="store_true",
        help="Actually write changes to files (default: dry-run)",
    )
    p.add_argument(
        "--undo",
        action="store_true",
        help="Restore files from .bak backups (revert previous --apply)",
    )
    args = p.parse_args(argv)

    if args.version is None:
        if args.apply:
            print("Error: --apply requires a version to write.", file=sys.stderr)
            return 2
        if args.undo:
            results = undo_version(ROOT)
            print_undo_preview(results)
            return 0
        versions = gather_versions(ROOT)
        print_current_versions(versions)
        return 0

    new_version = args.version.strip()
    if not is_valid_semver(new_version):
        print(
            f"Error: '{new_version}' is not a valid semantic version.", file=sys.stderr
        )
        return 2

    if args.undo:
        print("Error: --undo cannot be used together with a version.", file=sys.stderr)
        return 2

    results = apply_version(ROOT, new_version, args.apply)
    print_preview(results, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
