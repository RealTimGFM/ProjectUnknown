import os
import sys
import argparse
from datetime import datetime
from typing import Iterable, List, Set, Tuple

# ---------- Defaults tuned for StockAI ----------
DEFAULT_ROOT = "."
DEFAULT_OUTPUT = "dump.txt"
DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB

# Folders we usually exclude from **tree** to avoid noise; use --tree-all to include anyway
TREE_EXCLUDE_ANYWHERE: Set[str] = {".git", ".venv", "__pycache__", ".idea", ".vscode"}

# Folders we exclude from **content**, but still show in the tree
CONTENT_EXCLUDE_ANYWHERE: Set[str] = {
    ".git", ".venv", "__pycache__", ".idea", ".vscode", "node_modules",
    "dist", "build", ".mastra",
    # project artifacts
    "backtests", "notebooks",
}

# Filenames to ignore for content
IGNORE_FILES_ANYWHERE: Set[str] = {
    ".env", ".env.local", ".python-version", "Pipfile.lock",
    "package-lock.json", "tsconfig.json", "cookies.txt",
}

# Always include these names (even without extensions) in content
INCLUDE_FILENAMES: Set[str] = {"Makefile", "Dockerfile"}

# Binary-ish extensions (content skipped; still listed in tree)
BINARY_EXTS: Set[str] = {
    # archives / binaries
    ".zip", ".gz", ".tar", ".rar", ".7z", ".exe", ".dll", ".so", ".a",
    # db / parquet / arrow
    ".sqlite", ".sqlite3", ".db", ".db-journal", ".parquet", ".arrow",
    # images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".ico", ".webp",
    # docs
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    # audio/video
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".mkv",
}

# Text/code extensions included by default for content
DEFAULT_INCLUDE_EXTS: Set[str] = {
    ".py", ".toml", ".yaml", ".yml", ".json", ".md", ".txt", ".cfg", ".ini",
    ".sql", ".sh", ".bat", ".ps1", ".html", ".css", ".js", ".ts", ".tsx", ".jsx",
}
# ------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Dump project TREE + text/code contents into a single file.")
    p.add_argument("--root", default=DEFAULT_ROOT, help="Root directory to scan")
    p.add_argument("--output", default=DEFAULT_OUTPUT, help="Output file path")
    p.add_argument("--max-size", type=int, default=DEFAULT_MAX_FILE_SIZE, help="Max file size (bytes) for content")
    p.add_argument("--include-ext", default=",".join(sorted(DEFAULT_INCLUDE_EXTS)),
                   help="Comma-separated list of file extensions to include as content (e.g. .py,.toml,.yaml)")
    p.add_argument("--tree-all", action="store_true", help="Include ALL directories in the tree (even .git/.venv)")
    p.add_argument("--no-content", action="store_true", help="Only print the tree (no file contents)")
    p.add_argument("--placeholders", action="store_true",
                   help="Write placeholder blocks for skipped files (binary/large/not-included)")
    return p.parse_args()

def _normalize_exts(s: str) -> Set[str]:
    exts = set()
    for raw in s.split(","):
        e = raw.strip()
        if not e:
            continue
        if not e.startswith("."):
            e = "." + e
        exts.add(e.lower())
    return exts

def is_probably_binary(filepath: str, chunk_size: int = 1024) -> bool:
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(chunk_size)
            if not chunk:
                return False
            if b"\0" in chunk:
                return True
            text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)) - {0x7F})
            non_text = sum(1 for b in chunk if b not in text_chars)
            return (non_text / max(1, len(chunk))) > 0.30
    except Exception:
        return True

def should_hide_in_tree(name: str, include_all: bool) -> bool:
    return (name in TREE_EXCLUDE_ANYWHERE) and (not include_all)

def should_skip_content_dir(name: str) -> bool:
    return name in CONTENT_EXCLUDE_ANYWHERE

def should_include_content(fname: str, include_exts: Set[str]) -> bool:
    if fname in INCLUDE_FILENAMES:
        return True
    base, ext = os.path.splitext(fname)
    ext = ext.lower()
    if ext in BINARY_EXTS:
        return False
    if include_exts and ext not in include_exts:
        return False
    return True

def tree_lines(root: str, include_all: bool) -> Tuple[List[str], int, int]:
    """
    Return (lines, dir_count, file_count) for a pretty tree.
    """
    lines: List[str] = []
    dir_count = 0
    file_count = 0

    def walk(dir_path: str, prefix: str = ""):
        nonlocal dir_count, file_count
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        # filter only for tree display
        entries = [e for e in entries if not (e.is_dir() and should_hide_in_tree(e.name, include_all))]
        total = len(entries)
        for idx, e in enumerate(entries):
            connector = "└── " if idx == total - 1 else "├── "
            if e.is_dir():
                lines.append(f"{prefix}{connector}{e.name}/")
                dir_count += 1
                next_prefix = f"{prefix}{'    ' if idx == total - 1 else '│   '}"
                walk(e.path, next_prefix)
            else:
                file_count += 1
                lines.append(f"{prefix}{connector}{e.name}")

    root_label = os.path.basename(os.path.abspath(root)) or root
    lines.append(f"{root_label}/")
    walk(root)
    return lines, dir_count, file_count

def write_header(dump, title: str):
    sep = "=" * max(80, len(title) + 10)
    dump.write(f"{sep}\n")
    dump.write(f"{title}\n")
    dump.write(f"{sep}\n\n")

def write_file_header(dump, rel_path: str):
    header = f"// Path: {rel_path}"
    sep_len = max(80, len(header))
    dump.write("=" * sep_len + "\n")
    dump.write(header + "\n")
    dump.write("=" * sep_len + "\n\n")

def iter_all_files(root: str) -> Iterable[str]:
    for cur_root, dirs, files in os.walk(root, topdown=True):
        dirs[:] = sorted(dirs)
        for fname in sorted(files):
            yield os.path.join(cur_root, fname)

def main():
    args = parse_args()
    root = args.root
    out_path = args.output
    include_exts = _normalize_exts(args.include_ext)

    if not os.path.isdir(root):
        print(f"ERROR: root directory not found: {root}")
        sys.exit(1)

    with open(out_path, "w", encoding="utf-8", errors="ignore") as dump:
        # 1) Project metadata
        write_header(dump, "PROJECT SUMMARY")
        dump.write(f"Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z\n")
        dump.write(f"Root: {os.path.abspath(root)}\n")
        dump.write(f"Python: {sys.version.split()[0]}\n\n")

        # 2) Tree
        write_header(dump, "PROJECT TREE")
        lines, dcnt, fcnt = tree_lines(root, include_all=args.tree_all)
        dump.write("\n".join(lines) + "\n\n")
        dump.write(f"Directories: {dcnt}  Files: {fcnt}\n\n")

        if args.no_content:
            print(f"Done (tree only). Wrote {out_path}")
            return

        # 3) File contents (text/code only)
        write_header(dump, "FILE CONTENTS")
        processed = 0
        skipped = 0

        for fpath in iter_all_files(root):
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            fname = os.path.basename(fpath)
            parent = os.path.basename(os.path.dirname(fpath))

            # Skip content if under excluded dirs
            if parent in CONTENT_EXCLUDE_ANYWHERE or any(p in CONTENT_EXCLUDE_ANYWHERE for p in rel.split("/") if p):
                # still optionally write placeholder
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: directory excluded from content]\n\n")
                skipped += 1
                continue

            # Skip content by rule
            if not should_include_content(fname, include_exts):
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: extension not in include list]\n\n")
                skipped += 1
                continue

            # Size & binary checks
            try:
                size = os.path.getsize(fpath)
            except OSError as e:
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: stat error: {e}]\n\n")
                skipped += 1
                continue

            if size > args.max_size:
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: large file ~{size} bytes]\n\n")
                skipped += 1
                continue

            if is_probably_binary(fpath):
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: binary-like file]\n\n")
                skipped += 1
                continue

            # Emit content
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as src:
                    content = src.read()
                write_file_header(dump, rel)
                dump.write(content)
                dump.write("\n\n")
                processed += 1
                if processed % 50 == 0:
                    print(f"... wrote {processed} files")
            except Exception as e:
                if args.placeholders:
                    write_file_header(dump, rel)
                    dump.write(f"// [skipped: read error: {e}]\n\n")
                skipped += 1
                continue

        dump.write(f"\n// Summary: wrote {processed} files, skipped {skipped} files.\n")

    print(f"Done. TREE + contents written to {out_path}")

if __name__ == "__main__":
    main()
