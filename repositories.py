import json
from contextlib import closing

from app.database.connection import connect


def create_analysis(
    database_path,
    project_path,
    summary,
    findings,
    project_name="",
    source_type="local",
    upload_root=None,
    upload_size_bytes=0,
    traceability=None,
    code_review=None,
    project_metadata=None,
    agent_runs=None,
):
    with closing(connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO analysis_runs
                    (
                        project_path, readiness_score, summary_json, findings_json,
                        project_name, source_type, upload_root, traceability_json,
                        code_review_json, upload_size_bytes, project_metadata_json,
                        agent_runs_json
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_path,
                    summary["readiness_score"],
                    json.dumps(summary),
                    json.dumps(findings),
                    project_name,
                    source_type,
                    upload_root,
                    json.dumps(traceability or []),
                    json.dumps(code_review or []),
                    upload_size_bytes,
                    json.dumps(project_metadata or {}),
                    json.dumps(agent_runs or []),
                ),
            )
            return cursor.lastrowid


def get_analysis(database_path, analysis_id):
    with closing(connect(database_path)) as connection:
        row = connection.execute(
            "SELECT * FROM analysis_runs WHERE id = ?", (analysis_id,)
        ).fetchone()
    if row is None:
        return None
    return _serialize(row)


def list_analyses(database_path, limit=50):
    with closing(connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT * FROM analysis_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_serialize(row) for row in rows]


def save_test_result(database_path, analysis_id, result):
    with closing(connect(database_path)) as connection:
        with connection:
            row = connection.execute(
                "SELECT summary_json FROM analysis_runs WHERE id = ?",
                (analysis_id,),
            ).fetchone()
            if row is None:
                return False
            summary = json.loads(row["summary_json"])
            summary["test_status"] = result["status"]
            if result["status"] == "passed":
                summary["submission_readiness"] = (
                    "Ready to submit"
                    if summary["errors"] == 0 and summary["warnings"] <= 2
                    else "Review recommended"
                )
            elif result["status"] == "failed":
                summary["submission_readiness"] = "Tests failed"
            elif result["status"] == "timed_out":
                summary["submission_readiness"] = "Tests timed out"
            else:
                summary["submission_readiness"] = "Test run unavailable"
            cursor = connection.execute(
                """
                UPDATE analysis_runs
                SET test_result_json = ?, summary_json = ?
                WHERE id = ?
                """,
                (json.dumps(result), json.dumps(summary), analysis_id),
            )
            return cursor.rowcount == 1


def _serialize(row):
    test_result = (
        json.loads(row["test_result_json"]) if row["test_result_json"] else None
    )
    if test_result and not test_result.get("runner") and test_result.get("status") in {
        "passed",
        "failed",
        "timed_out",
    }:
        test_result = {
            "status": "legacy_unisolated",
            "return_code": test_result.get("return_code"),
            "output": test_result.get("output", ""),
            "message": "This result predates the isolated pytest runner and is not an isolated test result.",
        }
    summary = json.loads(row["summary_json"])
    summary.setdefault("quality_score", summary.get("readiness_score", 0))
    summary.setdefault("test_status", test_result["status"] if test_result else "not_run")
    summary.setdefault(
        "submission_readiness",
        "Tests pending" if not test_result else "Review recommended",
    )
    return {
        "id": row["id"],
        "project_path": row["project_path"],
        "project_name": row["project_name"],
        "source_type": row["source_type"],
        "upload_root": row["upload_root"],
        "created_at": row["created_at"],
        "readiness_score": row["readiness_score"],
        "summary": summary,
        "findings": json.loads(row["findings_json"]),
        "traceability": json.loads(row["traceability_json"]),
        "code_review": json.loads(row["code_review_json"]),
        "project_metadata": json.loads(row["project_metadata_json"]),
        "agent_runs": json.loads(row["agent_runs_json"]),
        "test_result": test_result,
    }


def delete_analysis(database_path, analysis_id):
    with closing(connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM analysis_runs WHERE id = ?", (analysis_id,)
            )
            return cursor.rowcount == 1


def stored_upload_bytes(database_path):
    with closing(connect(database_path)) as connection:
        row = connection.execute(
            "SELECT COALESCE(SUM(upload_size_bytes), 0) AS total FROM analysis_runs"
        ).fetchone()
    return row["total"]
