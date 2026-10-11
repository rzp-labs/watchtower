#!/usr/bin/env python3
"""Create immutable deterministic Watchtower plugin release artifacts (no publishing)."""
# Modified by rzp-labs, 2026-10-11. Released under GNU AGPL version 3; see LICENSE.
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

UPSTREAM = "35eb0518d33e710612beb88f29678900841dd33d"
REVIEWED = "91cbfc46737bca36e59b4f6749541f9e5910d9fd"
REPOSITORY = "https://github.com/rzp-labs/watchtower"
FEED_URL = REPOSITORY + "/releases/latest/download/index.yml"
LICENSE_SHA256 = "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0"
ROOT_FILES = {
    "LICENSE", "NOTICE.md", "README.md", "CHANGELOG.md", "DISCOURSE_POST.md",
    "requirements.txt", "librarymanager.yml", "librarymanager.js", "librarymanager.css",
    "librarymanager.py", "librarymanager_core.py", "librarymanager_monitor.py",
    "librarymanager_reconciliation.py", "librarymanager_startup.py",
}
TREES = {"assets", "watchdog", "vendor-licenses"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def package_names(entries):
    selected = []
    for mode, name in entries:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("unsafe Git path")
        if name not in ROOT_FILES and path.parts[0] not in TREES:
            continue
        if mode not in {"100644", "100755"}:
            raise ValueError("package contains a symlink or non-regular file: " + name)
        if any(part.startswith(".") for part in path.parts) or path.suffix.lower() in {".db", ".sqlite3", ".json", ".log", ".lock", ".pyc"} or "sqlite3-" in name:
            raise ValueError("runtime/private file in package selection: " + name)
        selected.append((mode, name))
    missing = ROOT_FILES - {name for _, name in selected}
    if missing:
        raise ValueError("missing package files: " + ", ".join(sorted(missing)))
    return sorted(selected, key=lambda item: item[1])


def zip_bytes(files, timestamp):
    stream = io.BytesIO()
    # Stored entries avoid platform/zlib-dependent compression differences.
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
        for mode, name, data in sorted(files, key=lambda item: item[1]):
            info = zipfile.ZipInfo(name, timestamp)
            info.create_system = 3
            info.external_attr = (int(mode, 8) | 0o100000) << 16
            archive.writestr(info, data)
    return stream.getvalue()


def build(repo, ref, output):
    sha = git(repo, "rev-parse", ref + "^{commit}").decode().strip()
    subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", REVIEWED, sha], check=True)
    if git(repo, "status", "--porcelain", "--untracked-files=no").strip():
        raise ValueError("commit tracked changes before packaging")
    tree = git(repo, "rev-parse", sha + "^{tree}").decode().strip()
    records = git(repo, "ls-tree", "-rz", sha).split(b"\0")
    entries = [(record.split(b" ", 1)[0].decode(), record.split(b"\t", 1)[1].decode()) for record in records if record]
    names = package_names(entries)
    files = [(mode, name, git(repo, "show", sha + ":" + name)) for mode, name in names]
    contents = {name: data for _, name, data in files}
    if hashlib.sha256(contents["LICENSE"]).hexdigest() != LICENSE_SHA256:
        raise ValueError("LICENSE differs from canonical GNU AGPLv3 text")
    version = re.search(rb"^version: ([0-9]+\.[0-9]+\.[0-9]+-rzp\.[0-9]+)$", contents["librarymanager.yml"], re.M)
    if not version:
        raise ValueError("expected an explicit maintained release version")
    version = version.group(1).decode()
    when = dt.datetime.fromtimestamp(int(git(repo, "show", "-s", "--format=%ct", sha)), dt.timezone.utc)
    timestamp = (when.year, when.month, when.day, when.hour, when.minute, when.second // 2 * 2)
    provenance = {
        "repository": REPOSITORY, "source_commit": sha, "source_tree": tree,
        "upstream_base": UPSTREAM, "reviewed_ui_commit": REVIEWED,
        "version": version, "license": "AGPL-3.0",
        "license_text_url": "https://www.gnu.org/licenses/agpl-3.0.txt",
        "license_sha256": LICENSE_SHA256,
        "source_archive": REPOSITORY + "/archive/refs/tags/v" + version + ".tar.gz",
        "files": {name: hashlib.sha256(data).hexdigest() for _, name, data in files},
    }
    provenance_data = (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode()
    files.append(("100644", "SOURCE-PROVENANCE.json", provenance_data))
    package = zip_bytes(files, timestamp)
    digest = hashlib.sha256(package).hexdigest()
    feed = (
        "- id: librarymanager\n  name: Watchtower\n  metadata:\n"
        "    description: Maintained Watchtower with MUI host compatibility.\n"
        f"  version: {version}-{sha[:7]}\n  date: \"{when.strftime('%Y-%m-%d %H:%M:%S')}\"\n"
        f"  path: {REPOSITORY}/releases/download/v{version}/librarymanager.zip\n  sha256: {digest}\n"
    ).encode()
    output.mkdir(parents=True, exist_ok=True)
    for name, data in {"librarymanager.zip": package, "index.yml": feed,
                       "SOURCE-PROVENANCE.json": provenance_data,
                       "SHA256SUMS": (digest + "  librarymanager.zip\n").encode()}.items():
        (output / name).write_bytes(data)
    return {"source_commit": sha, "source_tree": tree, "version": version, "sha256": digest,
            "files": len(files), "feed_url": FEED_URL}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    print(json.dumps(build(repo, args.ref, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
