import ast
from pathlib import Path

from app.analyzers.base import finding, iter_project_files, relative_path


def analyze(root, max_files=1000, max_file_bytes=1024 * 1024):
    root = Path(root)
    findings = []
    checked = 0
    for path in iter_project_files(root, {".py"}, max_files):
        try:
            if path.stat().st_size > max_file_bytes:
                findings.append(
                    finding(
                        "warning",
                        "code",
                        "Source file skipped",
                        "File exceeds the configured analysis size limit.",
                        relative_path(root, path),
                    )
                )
                continue
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
            checked += 1
        except SyntaxError as error:
            findings.append(
                finding(
                    "error",
                    "code",
                    "Python syntax error",
                    "Line {}: {}".format(error.lineno or "?", error.msg),
                    relative_path(root, path),
                )
            )
        except (OSError, UnicodeError) as error:
            findings.append(
                finding(
                    "warning",
                    "code",
                    "Source file could not be read",
                    str(error),
                    relative_path(root, path),
                )
            )

    findings.append(
        finding(
            "info",
            "code",
            "Python source inspection complete",
            "Parsed {} Python source file(s) without executing them.".format(checked),
        )
    )
    return findings
