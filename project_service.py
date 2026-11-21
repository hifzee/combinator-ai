from pathlib import Path


def validate_project_path(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Provide a project directory path.")
    try:
        project_path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError("The project directory could not be resolved.") from error
    if not project_path.is_dir():
        raise ValueError("The selected path is not a directory.")
    return project_path
