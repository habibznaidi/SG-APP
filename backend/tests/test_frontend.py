def test_frontend_served_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ServicePulse" in resp.text


def test_static_assets_served(client):
    resp = client.get("/js/app.js")
    assert resp.status_code == 200
    resp = client.get("/css/style.css")
    assert resp.status_code == 200
