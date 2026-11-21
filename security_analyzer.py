import ast
from pathlib import Path

from app.analyzers.base import finding, iter_project_files, relative_path


def analyze(root, max_files=1000, max_file_bytes=1024 * 1024):
    root = Path(root)
    findings = []
    dangerous_calls = {"pickle.load": "Deserializing untrusted data", "yaml.load": "YAML loading may permit unsafe object construction", "requests.get": "Verify trusted endpoints and TLS behavior"}
    for path in iter_project_files(root, {".py"}, max_files):
        relative = relative_path(root, path)
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name in dangerous_calls:
                    severity = "warning" if name == "requests.get" else "error"
                    findings.append(finding(severity, "security", name + " usage requires review", dangerous_calls[name], "{}:{}".format(relative, node.lineno)))
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "secret" in target.id.lower():
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            findings.append(finding("error", "security", "Potential hard-coded secret", "A secret-like variable is assigned a string literal.", "{}:{}".format(relative, node.lineno)))
    if not findings:
        findings.append(finding("info", "security", "Static security review complete", "No configured secret or unsafe-deserialization rules were triggered."))
    return findings


def _call_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))
