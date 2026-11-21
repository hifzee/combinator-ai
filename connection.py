import sqlite3
from contextlib import closing
from pathlib import Path


def connect(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path):
    with closing(connect(database_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_path TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    readiness_score INTEGER NOT NULL,
                    summary_json TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    test_result_json TEXT
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(analysis_runs)")
            }
            migrations = {
                "project_name": "TEXT NOT NULL DEFAULT ''",
                "source_type": "TEXT NOT NULL DEFAULT 'local'",
                "upload_root": "TEXT",
                "upload_size_bytes": "INTEGER NOT NULL DEFAULT 0",
                "traceability_json": "TEXT NOT NULL DEFAULT '[]'",
                "code_review_json": "TEXT NOT NULL DEFAULT '[]'",
                "project_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
                "agent_runs_json": "TEXT NOT NULL DEFAULT '[]'",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    connection.execute(
                        "ALTER TABLE analysis_runs ADD COLUMN {} {}".format(
                            name, declaration
                        )
                    )
