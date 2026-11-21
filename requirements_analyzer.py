from pathlib import Path

from app.analyzers.base import finding
from app.analyzers.requirements_data import read_declarations


def analyze(root):
    root = Path(root)
    findings = []
    declarations, errors, manifests = read_declarations(root)
    for path, message in errors:
        findings.append(
            finding(
                "error",
                "requirements",
                "Dependency manifest could not be parsed",
                message,
                path,
            )
        )

    if not manifests:
        findings.append(
            finding(
                "warning",
                "requirements",
                "No dependency manifest found",
                "Add requirements.txt or declare dependencies in pyproject.toml.",
            )
        )
    else:
        findings.append(
            finding(
                "info",
                "requirements",
                "Dependency manifests inspected",
                "Found {} manifest(s) and {} dependency declaration(s).".format(
                    len(manifests), len(declarations)
                ),
            )
        )
    return findings
