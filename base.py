import os
from pathlib import Path


EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
}


def iter_project_files(root, extensions, max_files=1000):
    count = 0
    for current, directories, filenames in os.walk(root, topdown=True):
        directories[:] = [
            name
            for name in directories
            if name not in EXCLUDED_DIRECTORIES and not name.startswith(".")
        ]
        for filename in filenames:
            path = Path(current, filename)
            if path.suffix.lower() not in extensions or path.is_symlink():
                continue
            yield path
            count += 1
            if count >= max_files:
                return


def finding(severity, category, title, message, path=None):
    return {
        "severity": severity,
        "category": category,
        "title": title,
        "message": message,
        "path": path,
    }


def relative_path(root, path):
    return str(Path(path).relative_to(root))
