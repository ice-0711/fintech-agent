"""Single admin login (lead decision 2026-10-21: keep it simple).

Only the lead logs in, with ADMIN_PASSWORD from the server environment. A signed session
cookie (FLASK_SECRET_KEY) then authorises the research API from the browser, so the
API token never reaches the page. Visitors only read published content.
"""

from __future__ import annotations

import hmac
import os

from flask import Blueprint, current_app, redirect, render_template_string, request, session, url_for

bp = Blueprint("admin", __name__, url_prefix="/admin")

LOGIN_PAGE = """<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>組長登入</title>
<body style="font-family:system-ui;max-width:360px;margin:15vh auto;padding:0 16px">
<h1 style="font-size:20px">組長登入</h1>
{% if error %}<p style="color:#b00">{{ error }}</p>{% endif %}
{% if not configured %}<p style="color:#b00">伺服器尚未設定 ADMIN_PASSWORD，無法登入。</p>{% endif %}
<form method="post"><input type="password" name="password" placeholder="密碼" autofocus
 style="width:100%;padding:10px;font-size:16px;box-sizing:border-box">
<button style="margin-top:12px;width:100%;padding:10px;font-size:16px">登入</button></form>
{% if logged_in %}<p>已登入。<a href="{{ url_for('admin.logout') }}">登出</a></p>{% endif %}
</body></html>"""


def is_admin() -> bool:
    return bool(session.get("admin"))


def configure(app) -> None:
    """Session settings; call once when the app is created."""
    app.secret_key = app.secret_key or os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=bool(os.getenv("RENDER")))


@bp.route("/login", methods=["GET", "POST"])
def login():
    expected = current_app.config.get("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    error = None
    if request.method == "POST":
        supplied = (request.form.get("password") or "").encode("utf-8", "surrogateescape")
        if expected and hmac.compare_digest(supplied, expected.encode()):
            session.clear()
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("admin.login"))
        error = "密碼錯誤"
    return render_template_string(LOGIN_PAGE, error=error, configured=bool(expected), logged_in=is_admin())


@bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))
