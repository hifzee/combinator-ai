import ast
import sys
from pathlib import Path

from app.analyzers.base import finding, iter_project_files, relative_path
from app.analyzers.requirements_data import read_declarations


IMPORT_TO_PACKAGE = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "Crypto": "pycryptodome",
    "dotenv": "python-dotenv",
    "jwt": "pyjwt",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
}


def analyze(root, max_files=1000, max_file_bytes=1024 * 1024):
    root = Path(root)
    declarations, _, _ = read_declarations(root)
    imports, local_modules = _collect_imports(root, max_files, max_file_bytes)
    by_normalized_name = {}
    for declaration in declarations:
        by_normalized_name.setdefault(declaration["normalized_name"], []).append(declaration)

    matrix = []
    undeclared = []
    for declaration in declarations:
        matching_imports = _imports_for_dependency(declaration["name"], imports)
        matrix.append(
            {
                "dependency": declaration["name"],
                "constraint": declaration["raw"][len(declaration["name"]) :],
                "declared_in": _location(declaration),
                "imported_as": sorted({item["module"] for item in matching_imports}),
                "evidence": sorted(
                    {
                        "{}:{}".format(item["path"], item["line"])
                        for item in matching_imports
                    }
                ),
                "status": "referenced" if matching_imports else "not observed in Python imports",
            }
        )

    for import_name, references in sorted(imports.items()):
        package_name = IMPORT_TO_PACKAGE.get(import_name, import_name)
        normalized = _normalize(package_name)
        if (
            import_name in sys.stdlib_module_names
            or import_name in local_modules
            or normalized in by_normalized_name
        ):
            continue
        evidence = [
            "{}:{}".format(reference["path"], reference["line"])
            for reference in references[:10]
        ]
        matrix.append(
            {
                "dependency": package_name,
                "constraint": "",
                "declared_in": "Not declared",
                "imported_as": [import_name],
                "evidence": evidence,
                "status": "possible undeclared dependency",
            }
        )
        undeclared.append(
            finding(
                "warning",
                "requirements",
                "Possible undeclared dependency",
                "Python import '{}' is not matched to a standard-library or declared package; observed at {} location(s).".format(
                    import_name, len(references)
                ),
                evidence[0],
            )
        )

    findings = [
        finding(
            "info",
            "requirements",
            "Requirements traceability generated",
            "Matched declared dependencies against import statements; this is a static heuristic.",
        )
    ]
    findings.extend(undeclared)

    return matrix, findings


def _collect_imports(root, max_files, max_file_bytes):
    imports = {}
    local_modules = set()
    files = list(iter_project_files(root, {".py"}, max_files))
    for path in files:
        relative = relative_path(root, path)
        local_modules.add(path.stem)
        try:
            if path.stat().st_size > max_file_bytes:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top_level = name.split(".", 1)[0]
                imports.setdefault(top_level, []).append(
                    {"module": name, "path": relative, "line": node.lineno}
                )
    local_modules.update(
        path.name for path in Path(root).iterdir() if path.is_dir()
    )
    return imports, local_modules


def _imports_for_dependency(package_name, imports):
    aliases = {
        import_name
        for import_name, distribution in IMPORT_TO_PACKAGE.items()
        if _normalize(distribution) == _normalize(package_name)
    }
    aliases.add(package_name)
    return [
        reference
        for import_name, references in imports.items()
        if import_name in aliases
        or _normalize(import_name) == _normalize(package_name)
        for reference in references
    ]


def _normalize(name):
    return name.lower().replace("_", "-").replace(".", "-")


def _location(declaration):
    line = declaration["line"]
    return (
        declaration["filename"]
        if line is None
        else "{}:{}".format(declaration["filename"], line)
    )
