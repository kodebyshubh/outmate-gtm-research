from app.services.normalize import label_for, normalize_domain


def test_strips_protocol_www_and_path():
    assert normalize_domain("https://www.Example.com/about?x=1") == "example.com"


def test_bare_domain():
    assert normalize_domain("example.io") == "example.io"


def test_invalid_returns_none():
    assert normalize_domain("not a domain") is None
    assert normalize_domain("") is None
    assert normalize_domain(None) is None


def test_label_prefers_name():
    assert label_for("Acme AI", "acme.com") == "Acme AI"
    assert label_for(None, "acme.com") == "acme"
