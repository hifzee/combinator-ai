from pathlib import Path

from app.analyzers.base import finding, iter_project_files


def analyze(root, max_files=1000):
    root = Path(root)
    tests = [
        path
        for path in iter_project_files(root, {".py"}, max_files)
        if path.name.startswith("test_") or path.name.endswith("_test.py")
    ]

    if tests:
        return [
            finding(
                "info",
                "tests",
                "Tests discovered",
                "Found {} likely pytest-compatible test file(s). They were not executed.".format(
                    len(tests)
                ),
            )
        ]
    return [
        finding(
            "warning",
            "tests",
            "No tests discovered",
            "Add Python test files named test_*.py in the project root or tests directory.",
        )
    ]
