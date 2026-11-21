from flask import Blueprint, render_template


main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def landing():
    return render_template("landing.html")


@main_bp.get("/workspace")
def workspace():
    return render_template("index.html")
