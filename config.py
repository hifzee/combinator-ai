import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-only")
    DATA_DIR = os.environ.get("DATA_DIR")
    DATABASE = os.environ.get(
        "COMBINATOR_DATABASE",
        os.path.join(DATA_DIR, "combinator.sqlite3") if DATA_DIR else os.path.join("instance", "combinator.sqlite3"),
    )
    UPLOAD_FOLDER = os.environ.get(
        "COMBINATOR_UPLOAD_FOLDER",
        os.path.join(DATA_DIR, "uploads") if DATA_DIR else os.path.join("instance", "uploads"),
    )
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    MAX_ANALYSIS_FILES = 1000
    MAX_SOURCE_FILE_BYTES = 1024 * 1024
    MAX_ARCHIVE_FILES = 3000
    MAX_ARCHIVE_FILE_BYTES = 20 * 1024 * 1024
    MAX_ARCHIVE_TOTAL_BYTES = 100 * 1024 * 1024
    MAX_STORED_PROJECT_BYTES = 500 * 1024 * 1024
    MAX_ARCHIVE_DEPTH = 20
    MAX_ARCHIVE_COMPRESSION_RATIO = 200
    TEST_TIMEOUT_SECONDS = 120
    TEST_OUTPUT_LIMIT_BYTES = 16 * 1024
    TEST_RUNNER_IMAGE = "combinator-ai-test-runner:py312"
    TEST_RUNNER_BINARY = os.environ.get("COMBINATOR_DOCKER", "docker")
