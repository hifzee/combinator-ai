from pathlib import Path

from app.analyzers.base import finding


def analyze(root):
    root = Path(root)
    findings = []
    python_files = [p for p in root.rglob("*.py") if ".venv" not in p.parts and "venv" not in p.parts]
    dirs = sorted({str(p.parent.relative_to(root)) for p in python_files if p.parent != root})
    if not dirs:
        findings.append(finding("info", "architecture", "Flat Python layout detected", "Python source is concentrated at the project root; validate module separation as the project grows."))
    else:
        findings.append(finding("info", "architecture", "Python module layout detected", "Python modules are distributed across: {}.".format(", ".join(dirs[:20]))))

    if not (root / "app").is_dir() and not (root / "src").is_dir():
        findings.append(finding("info", "architecture", "No conventional source container", "The project does not use app/ or src/ as a conventional source container."))

    init_count = sum(1 for p in python_files if p.name == "__init__.py")
    if python_files and init_count == 0:
        findings.append(finding("warning", "architecture", "Package boundaries are unclear", "No __init__.py files were found; this may indicate ad hoc module organization."))
    return findings
