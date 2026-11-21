import logging
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import RequestEntityTooLarge

from app.config import Config
from app.database.connection import initialize_database


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app.logger.setLevel(logging.INFO)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    initialize_database(app.config["DATABASE"])

    from app.routes.analyses import analyses_bp
    from app.routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(analyses_bp, url_prefix="/api")

    @app.get("/health")
    def health():
        try:
            with sqlite3.connect(app.config["DATABASE"]) as connection:
                connection.execute("SELECT 1").fetchone()
            return jsonify({"status": "healthy", "database": "available"})
        except sqlite3.Error:
            app.logger.exception("Health check database validation failed.")
            return jsonify({"status": "degraded", "database": "unavailable"}), 503

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
        )
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_request(error):
        del error
        if request.path.startswith("/api/"):
            return jsonify({"error": "The upload exceeds the 25 MB limit."}), 413
        return "The upload exceeds the 25 MB limit.", 413

    @app.errorhandler(404)
    def handle_not_found(error):
        del error
        if request.path.startswith("/api/"):
            return jsonify({"error": "The requested resource was not found."}), 404
        return render_template("error.html", code=404, title="Page not found", message="The requested page does not exist or may have moved."), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        del error
        if request.path.startswith("/api/"):
            return jsonify({"error": "This method is not allowed for the requested resource."}), 405
        return render_template("error.html", code=405, title="Method not allowed", message="Use one of the application navigation links or supported actions."), 405

    @app.errorhandler(500)
    def handle_internal_error(error):
        del error
        app.logger.exception("An internal application error occurred.")
        if request.path.startswith("/api/"):
            return jsonify({"error": "An internal server error occurred."}), 500
        return render_template("error.html", code=500, title="Something went wrong", message="The application encountered an unexpected error. The event was logged."), 500

    @app.errorhandler(sqlite3.Error)
    def handle_database_error(error):
        del error
        app.logger.exception("A database operation failed.")
        if request.path.startswith("/api/"):
            return jsonify({"error": "The local database operation failed."}), 500
        return "The local database operation failed.", 500

    return app
