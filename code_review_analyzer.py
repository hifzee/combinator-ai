import ast
import re
from pathlib import Path

from app.analyzers.base import finding, iter_project_files, relative_path


TODO_PATTERN = re.compile(r"\b(?:TODO|FIXME|XXX)\b", re.IGNORECASE)


def analyze(root, max_files=1000, max_file_bytes=1024 * 1024):
    root = Path(root)
    findings = []
    for path in iter_project_files(root, {".py"}, max_files):
        relative = relative_path(root, path)
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except SyntaxError:
            continue
        except (OSError, UnicodeError) as error:
            findings.append(
                finding(
                    "warning",
                    "code_review",
                    "File could not be reviewed",
                    str(error),
                    relative,
                )
            )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(
                    finding(
                        "warning",
                        "code_review",
                        "Bare exception handler",
                        "Catch a specific exception so unexpected failures are not hidden.",
                        "{}:{}".format(relative, node.lineno),
                    )
                )
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in {"eval", "exec"}:
                    findings.append(
                        finding(
                            "warning",
                            "code_review",
                            "Dynamic code execution",
                            "{} executes dynamically constructed code; review input trust and necessity.".format(
                                name
                            ),
                            "{}:{}".format(relative, node.lineno),
                        )
                    )
                elif name == "os.system":
                    findings.append(
                        finding(
                            "warning",
                            "code_review",
                            "Shell command invocation",
                            "Prefer subprocess with an argument list and shell=False.",
                            "{}:{}".format(relative, node.lineno),
                        )
                    )
                elif name.startswith("subprocess."):
                    shell_true = any(
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    )
                    if shell_true:
                        findings.append(
                            finding(
                                "error",
                                "code_review",
                                "Shell injection risk",
                                "subprocess uses shell=True; validate inputs and prefer an argument list.",
                                "{}:{}".format(relative, node.lineno),
                            )
                        )

        for line_number, line in enumerate(source.splitlines(), start=1):
            if TODO_PATTERN.search(line):
                findings.append(
                    finding(
                        "info",
                        "code_review",
                        "Unresolved code note",
                        "Review this TODO/FIXME marker before submission.",
                        "{}:{}".format(relative, line_number),
                    )
                )
    if not findings:
        findings.append(
            finding(
                "info",
                "code_review",
                "Automated code review complete",
                "No configured high-confidence review rules were triggered.",
            )
        )
    return findings


def _call_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))
