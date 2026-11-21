import shutil
import stat
import tempfile
import uuid
import zipfile
import zlib
from pathlib import Path, PurePosixPath, PureWindowsPath

from werkzeug.datastructures import FileStorage

from app.analyzers.base import EXCLUDED_DIRECTORIES


class UploadValidationError(ValueError):
    """Raised when an uploaded archive is invalid or exceeds configured limits."""


def extract_project_zip(upload: FileStorage, upload_folder, limits):
    filename = (upload.filename or "").replace("\\", "/")
    if not filename or PurePosixPath(filename).suffix.lower() != ".zip":
        raise UploadValidationError("Choose a ZIP archive.")
    if upload.mimetype == "application/x-msdownload":
        raise UploadValidationError("This file type is not accepted.")

    upload_root = Path(upload_folder).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    workspace = upload_root / uuid.uuid4().hex
    workspace.mkdir()
    archive_path = None

    successful = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".zip", dir=str(upload_root), delete=False
        ) as staged:
            archive_path = Path(staged.name)
            received = 0
            while True:
                chunk = upload.stream.read(64 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > limits["max_upload_bytes"]:
                    raise UploadValidationError("ZIP archive exceeds the upload limit.")
                staged.write(chunk)

        extraction_root = workspace / "project"
        extraction_root.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                extracted_size = _extract_members(archive, extraction_root, limits)
        except (
            zipfile.BadZipFile,
            zipfile.LargeZipFile,
            OSError,
            NotImplementedError,
            zlib.error,
            EOFError,
            RuntimeError,
        ) as error:
            raise UploadValidationError("The uploaded ZIP archive is invalid.") from error

        project_root = _single_project_root(extraction_root)
        display_name = PurePosixPath(filename).name
        successful = True
        return {
            "project_path": project_root,
            "upload_root": workspace,
            "project_name": display_name,
            "expanded_size": extracted_size,
        }
    finally:
        if archive_path is not None:
            try:
                archive_path.unlink()
            except FileNotFoundError:
                pass
        if not successful:
            shutil.rmtree(workspace)


def _extract_members(archive, destination, limits):
    members = archive.infolist()
    if len(members) > limits["max_files"]:
        raise UploadValidationError("ZIP archive contains too many entries.")

    seen = set()
    file_count = 0
    total_size = 0
    actual_total_size = 0
    for member in members:
        relative = _safe_member_path(member, limits)
        if relative is None:
            continue

        normalized = relative.as_posix().casefold()
        if normalized in seen:
            raise UploadValidationError("ZIP archive contains duplicate file paths.")
        seen.add(normalized)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue

        file_type = stat.S_IFMT(member.external_attr >> 16)
        if file_type not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise UploadValidationError("ZIP archive contains a link or special file.")
        if member.flag_bits & 0x1:
            raise UploadValidationError("Encrypted ZIP archives are not supported.")
        if member.is_dir():
            continue

        file_count += 1
        if file_count > limits["max_files"]:
            raise UploadValidationError("ZIP archive contains too many files.")
        if member.file_size > limits["max_file_bytes"]:
            raise UploadValidationError("A ZIP entry exceeds the per-file size limit.")
        total_size += member.file_size
        if total_size > limits["max_total_bytes"]:
            raise UploadValidationError("Expanded ZIP archive exceeds the size limit.")
        if member.file_size > 1024 * 1024 and member.file_size / max(
            member.compress_size, 1
        ) > limits["max_compression_ratio"]:
            raise UploadValidationError("ZIP archive has a suspicious compression ratio.")

        target = destination.joinpath(*relative.parts)
        resolved_target = target.resolve()
        if not resolved_target.is_relative_to(destination.resolve()):
            raise UploadValidationError("ZIP archive contains an unsafe path.")
        target.parent.mkdir(parents=True, exist_ok=True)
        actual_size = 0
        with archive.open(member, "r") as source, target.open("xb") as output:
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                actual_size += len(chunk)
                actual_total_size += len(chunk)
                if actual_size > limits["max_file_bytes"]:
                    raise UploadValidationError("A ZIP entry exceeds the per-file size limit.")
                if actual_total_size > limits["max_total_bytes"]:
                    raise UploadValidationError("Expanded ZIP archive exceeds the size limit.")
                output.write(chunk)
        if actual_size != member.file_size:
            raise UploadValidationError("ZIP entry size did not match its directory record.")
    return actual_total_size


def _safe_member_path(member, limits):
    raw_name = member.filename
    if (
        not raw_name
        or "\x00" in raw_name
        or "\\" in raw_name
        or raw_name.startswith("/")
        or PureWindowsPath(raw_name).drive
    ):
        raise UploadValidationError("ZIP archive contains an unsafe path.")

    path = PurePosixPath(raw_name)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in ("", ".", "..") for part in path.parts)
        or any(":" in part or part.endswith((" ", ".")) for part in path.parts)
        or any(PureWindowsPath(part).is_reserved() for part in path.parts)
        or len(path.parts) > limits["max_depth"]
        or any(len(part) > 255 for part in path.parts)
    ):
        raise UploadValidationError("ZIP archive contains an unsafe path.")
    return path


def _single_project_root(extraction_root):
    entries = list(extraction_root.iterdir())
    if len(entries) == 1 and entries[0].is_dir() and not entries[0].is_symlink():
        return entries[0]
    return extraction_root
