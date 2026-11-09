"""Lead 11/09: / redirects to the research workbench (the old query page's Supabase project returns 503)."""

from web_app import app


def test_home_redirects_to_research():
    r = app.test_client().get("/")
    assert r.status_code == 302 and r.headers["Location"].endswith("/research")
