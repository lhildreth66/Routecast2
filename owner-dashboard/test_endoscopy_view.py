import pytest
import endoscopy_view as v


def data():
    return {"schema": 1, "as_of": "2026-11-27T15:35:00+00:00",
            "counts": {k: 1 for k in (*v.LABELS, *v.WEEKS)},
            "modules": [{"title": "<example>", "completed_lessons": 1}]}


def test_render(monkeypatch):
    monkeypatch.setattr(v, "fetch", lambda: v.validate(data()))
    output = v.render_endoscopy(v.PRODUCT)
    assert "Registered users" in output and "&lt;example&gt;" in output
    assert "<example>" not in output
    assert v.render_endoscopy("routecast") == ""


def test_invalid_counts():
    d = data(); d["counts"]["active"] = -1
    with pytest.raises(ValueError): v.validate(d)


def test_missing(monkeypatch):
    monkeypatch.delenv(v.KEY_NAME, raising=False)
    assert "not connected" in v.render_endoscopy(v.PRODUCT)


def test_error_is_sanitized(monkeypatch):
    def fail(): raise RuntimeError("private-secret")
    monkeypatch.setattr(v, "fetch", fail)
    assert "private-secret" not in v.render_endoscopy(v.PRODUCT)
