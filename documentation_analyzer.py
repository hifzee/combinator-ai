from pathlib import Path

from app.analyzers.base import finding

MAX_DOCUMENT_BYTES = 1024 * 1024

RECOMMENDED_SECTIONS = {
    "installation": ("installation", "install", "getting started", "setup"),
    "usage": ("usage", "how to use", "quickstart", "quick start"),
    "testing": ("test", "testing"),
}


def analyze(root):
    root = Path(root)
    readme = next(
        (
            candidate
            for candidate in (root / "README.md", root / "README.rst", root / "README.txt")
            if candidate.is_file()
        ),
        None,
    )
    if readme is None:
        return [
            finding(
                "warning",
                "documentation",
                "README is missing",
                "Add a README with project purpose, setup, usage, and testing guidance.",
            )
        ]

    findings = []
    try:
        if readme.stat().st_size > MAX_DOCUMENT_BYTES:
            return [
                finding(
                    "warning",
                    "documentation",
                    "README exceeds the inspection limit",
                    "README files larger than 1 MB are skipped.",
                    readme.name,
                )
            ]
        content = readme.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [
            finding(
                "warning",
                "documentation",
                "README could not be read",
                str(error),
                readme.name,
            )
        ]

    lowered = content.lower()
    missing = [
        label
        for label, terms in RECOMMENDED_SECTIONS.items()
        if not any(term in lowered for term in terms)
    ]
    if missing:
        findings.append(
            finding(
                "warning",
                "documentation",
                "README sections may be incomplete",
                "Consider adding guidance for: {}.".format(", ".join(missing)),
                readme.name,
            )
        )
    else:
        findings.append(
            finding(
                "info",
                "documentation",
                "README content checks passed",
                "README contains recognizable installation, usage, and testing guidance.",
                readme.name,
            )
        )

    if not (root / "LICENSE").is_file() and not (root / "LICENSE.txt").is_file():
        findings.append(
            finding(
                "info",
                "documentation",
                "License file not found",
                "Consider including a license if the project will be distributed.",
            )
        )
    return findings
