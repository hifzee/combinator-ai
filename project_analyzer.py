import ast
from pathlib import Path

from app.analyzers.base import finding, iter_project_files


def analyze(root):
    root = Path(root)
    py_files = list(iter_project_files(root, {".py"}, 1000))
    js_files = list(iter_project_files(root, {".js", ".ts", ".tsx", ".jsx"}, 1000))
    languages = []
    if py_files:
        languages.append("Python")
    if js_files:
        languages.append("JavaScript/TypeScript")

    frameworks = []
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError):
            continue
        imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for _ in node.names}
        imports.update(node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module)
        if "flask" in imports:
            frameworks.append("Flask")
        if "django" in imports:
            frameworks.append("Django")
        if "fastapi" in imports:
            frameworks.append("FastAPI")

    entry_points = []
    for name in ("main.py", "app.py", "run.py", "manage.py"):
        for path in py_files:
            if path.name == name:
                entry_points.append(str(path.relative_to(root)))

    package_files = [
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name in {"pyproject.toml", "requirements.txt", "package.json", "Dockerfile", "docker-compose.yml", "compose.yml"}
    ]

    metadata = {
        "languages": sorted(set(languages)),
        "frameworks": sorted(set(frameworks)),
        "entry_points": sorted(set(entry_points)),
        "python_files": len(py_files),
        "web_files": len(js_files),
        "configuration_files": sorted(set(package_files)),
        "root_directories": sorted([p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")])[:30],
    }
    return metadata, [finding("info", "project", "Project structure detected", "Languages: {}. Frameworks: {}.".format(
        ", ".join(metadata["languages"]) or "None detected",
        ", ".join(metadata["frameworks"]) or "None detected",
    ))]
