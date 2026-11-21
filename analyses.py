import shutil
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from app.database.repositories import (
    create_analysis,
    delete_analysis,
    get_analysis,
    list_analyses,
    save_test_result,
    stored_upload_bytes,
)
from app.services.analysis_service import analyze_project
from app.services.project_service import validate_project_path
from app.services.report_service import export_json
from app.services.test_service import run_pytest_in_docker
from app.services.upload_service import UploadValidationError, extract_project_zip


analyses_bp = Blueprint("analyses", __name__)


@analyses_bp.post("/analyses")
def create():
    if not _same_origin_request():
        return _forbidden_origin()
    payload = request.get_json(silent=True) or {}
    try:
        project_path = validate_project_path(payload.get("project_path"))
        result = _analyze(project_path)
        analysis_id = create_analysis(
            current_app.config["DATABASE"],
            str(project_path),
            result["summary"],
            result["findings"],
            project_name=project_path.name,
            traceability=result["traceability"],
            code_review=result["code_review"],
            project_metadata=result["project_metadata"],
            agent_runs=result["agent_runs"],
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except (OSError, sqlite3.Error):
        current_app.logger.exception("Project analysis could not be saved.")
        return jsonify({"error": "The project could not be analyzed or saved."}), 500
    return jsonify(_public_analysis(get_analysis(current_app.config["DATABASE"], analysis_id))), 201


@analyses_bp.post("/analyses/upload")
def upload():
    if not _same_origin_request():
        return _forbidden_origin()
    uploaded_file = request.files.get("project_zip")
    if uploaded_file is None:
        return jsonify({"error": "Choose a ZIP archive to analyze."}), 400

    upload = None
    analysis_id = None
    limits = {
        "max_upload_bytes": current_app.config["MAX_CONTENT_LENGTH"],
        "max_files": current_app.config["MAX_ARCHIVE_FILES"],
        "max_file_bytes": current_app.config["MAX_ARCHIVE_FILE_BYTES"],
        "max_total_bytes": current_app.config["MAX_ARCHIVE_TOTAL_BYTES"],
        "max_depth": current_app.config["MAX_ARCHIVE_DEPTH"],
        "max_compression_ratio": current_app.config[
            "MAX_ARCHIVE_COMPRESSION_RATIO"
        ],
    }
    try:
        upload = extract_project_zip(
            uploaded_file,
            current_app.config["UPLOAD_FOLDER"],
            limits,
        )
        result = _analyze(upload["project_path"])
        if (
            stored_upload_bytes(current_app.config["DATABASE"])
            + upload["expanded_size"]
            > current_app.config["MAX_STORED_PROJECT_BYTES"]
        ):
            raise UploadValidationError(
                "Saved project storage is full. Delete an older analysis before uploading."
            )
        analysis_id = create_analysis(
            current_app.config["DATABASE"],
            str(upload["project_path"]),
            result["summary"],
            result["findings"],
            project_name=upload["project_name"],
            source_type="upload",
            upload_root=str(upload["upload_root"]),
            upload_size_bytes=upload["expanded_size"],
            traceability=result["traceability"],
            code_review=result["code_review"],
            project_metadata=result["project_metadata"],
            agent_runs=result["agent_runs"],
        )
    except UploadValidationError as error:
        return jsonify({"error": str(error)}), 400
    except (OSError, sqlite3.Error):
        current_app.logger.exception("Uploaded project could not be analyzed or saved.")
        return jsonify({"error": "The uploaded project could not be analyzed or saved."}), 500
    finally:
        if upload is not None and analysis_id is None:
            _remove_upload(upload["upload_root"])

    return jsonify(
        _public_analysis(get_analysis(current_app.config["DATABASE"], analysis_id))
    ), 201


@analyses_bp.get("/analyses")
def history():
    return jsonify(
        [
            {
                "id": item["id"],
                "project_name": item["project_name"],
                "source_type": item["source_type"],
                "created_at": item["created_at"],
                "readiness_score": item["readiness_score"],
                "summary": item["summary"],
            }
            for item in list_analyses(current_app.config["DATABASE"])
        ]
    )


@analyses_bp.get("/analyses/<int:analysis_id>")
def detail(analysis_id):
    analysis = get_analysis(current_app.config["DATABASE"], analysis_id)
    if analysis is None:
        return jsonify({"error": "Analysis not found."}), 404
    return jsonify(_public_analysis(analysis))


@analyses_bp.get("/analyses/<int:analysis_id>/export")
def export(analysis_id):
    analysis = get_analysis(current_app.config["DATABASE"], analysis_id)
    if analysis is None:
        return jsonify({"error": "Analysis not found."}), 404
    response = Response(
        export_json(_public_analysis(analysis)),
        mimetype="application/json",
    )
    response.headers["Content-Disposition"] = (
        'attachment; filename="combinator-analysis-{}.json"'.format(analysis_id)
    )
    return response


@analyses_bp.get("/analyses/<int:analysis_id>/report")
def html_report(analysis_id):
    analysis = get_analysis(current_app.config["DATABASE"], analysis_id)
    if analysis is None:
        return jsonify({"error": "Analysis not found."}), 404
    return render_template("report.html", analysis=_public_analysis(analysis))


@analyses_bp.post("/analyses/<int:analysis_id>/tests")
def run_tests(analysis_id):
    if not _same_origin_request():
        return _forbidden_origin()
    analysis = get_analysis(current_app.config["DATABASE"], analysis_id)
    if analysis is None:
        return jsonify({"error": "Analysis not found."}), 404
    if analysis["source_type"] != "upload" or not _is_managed_upload(
        analysis["project_path"]
    ):
        return jsonify({"error": "Upload a ZIP archive to run isolated tests."}), 409

    result = run_pytest_in_docker(
        analysis["project_path"],
        docker_binary=current_app.config["TEST_RUNNER_BINARY"],
        image=current_app.config["TEST_RUNNER_IMAGE"],
        timeout_seconds=current_app.config["TEST_TIMEOUT_SECONDS"],
        output_limit_bytes=current_app.config["TEST_OUTPUT_LIMIT_BYTES"],
    )
    if not save_test_result(current_app.config["DATABASE"], analysis_id, result):
        current_app.logger.error("Could not save test result for analysis %s.", analysis_id)
        return jsonify({"error": "Test results could not be saved."}), 500
    return jsonify(result)


@analyses_bp.post("/analyses/demo")
def demo():
    if not _same_origin_request():
        return _forbidden_origin()
    project_path = Path(current_app.root_path).parent / "demo_project"
    try:
        result = _analyze(project_path)
        analysis_id = create_analysis(
            current_app.config["DATABASE"],
            str(project_path),
            result["summary"],
            result["findings"],
            project_name="Acme Inventory Demo",
            source_type="demo",
            traceability=result["traceability"],
            code_review=result["code_review"],
            project_metadata=result["project_metadata"],
            agent_runs=result["agent_runs"],
        )
    except (OSError, sqlite3.Error):
        current_app.logger.exception("Demo project could not be analyzed or saved.")
        return jsonify({"error": "The demo project could not be analyzed."}), 500
    return jsonify(_public_analysis(get_analysis(current_app.config["DATABASE"], analysis_id))), 201


@analyses_bp.delete("/analyses/<int:analysis_id>")
def remove(analysis_id):
    if not _same_origin_request():
        return _forbidden_origin()
    analysis = get_analysis(current_app.config["DATABASE"], analysis_id)
    if analysis is None:
        return jsonify({"error": "Analysis not found."}), 404
    if not delete_analysis(current_app.config["DATABASE"], analysis_id):
        return jsonify({"error": "Analysis could not be deleted."}), 500
    if analysis["upload_root"]:
        _remove_upload(analysis["upload_root"])
    return jsonify({"deleted": True})


def _analyze(project_path):
    return analyze_project(
        project_path,
        max_files=current_app.config["MAX_ANALYSIS_FILES"],
        max_file_bytes=current_app.config["MAX_SOURCE_FILE_BYTES"],
    )


def _same_origin_request():
    origin = request.headers.get("Origin")
    if not origin:
        return False
    try:
        parsed_origin = urlsplit(origin)
        expected_origin = urlsplit(request.host_url)
    except ValueError:
        return False
    return (
        parsed_origin.scheme == expected_origin.scheme
        and parsed_origin.netloc == expected_origin.netloc
    )


def _forbidden_origin():
    return jsonify({"error": "This request must be initiated from this application."}), 403


def _is_managed_upload(project_path):
    try:
        root = Path(current_app.config["UPLOAD_FOLDER"]).resolve(strict=True)
        project = Path(project_path).resolve(strict=True)
    except (OSError, RuntimeError):
        return False
    return project.is_dir() and project.is_relative_to(root)


def _remove_upload(path):
    try:
        upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
        target = Path(path).resolve()
    except (OSError, RuntimeError):
        current_app.logger.exception("Could not resolve uploaded project storage path.")
        return
    if target == upload_root or not target.is_relative_to(upload_root):
        current_app.logger.error("Refused to remove a path outside the upload directory.")
        return
    try:
        shutil.rmtree(target)
    except FileNotFoundError:
        return
    except OSError:
        current_app.logger.exception("Could not remove uploaded project data.")


def _public_analysis(analysis):
    public = dict(analysis)
    public.pop("project_path", None)
    public.pop("upload_root", None)
    return public
