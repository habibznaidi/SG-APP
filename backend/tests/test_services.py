def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"

def test_create_and_list_service(client):
    resp = client.post("/services", json={"name": "GitHub", "url": "https://github.com"})
    assert resp.status_code == 201
    service_id = resp.json()["id"]

    resp = client.get("/services")
    assert resp.status_code == 200
    assert any(s["id"] == service_id for s in resp.json())


def test_get_service_not_found(client):
    resp = client.get("/services/9999")
    assert resp.status_code == 404


def test_update_service(client):
    resp = client.post("/services", json={"name": "Test", "url": "https://example.com"})
    service_id = resp.json()["id"]

    resp = client.put(f"/services/{service_id}", json={"name": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"


def test_delete_service(client):
    resp = client.post("/services", json={"name": "ToDelete", "url": "https://example.com"})
    service_id = resp.json()["id"]

    resp = client.delete(f"/services/{service_id}")
    assert resp.status_code == 204
    assert client.get(f"/services/{service_id}").status_code == 404


def test_check_service_records_result(client):
    resp = client.post("/services", json={"name": "Example", "url": "https://example.com"})
    service_id = resp.json()["id"]

    resp = client.post(f"/services/{service_id}/check")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("UP", "DOWN")


def test_check_service_unreachable_url_is_down(client):
    resp = client.post(
        "/services", json={"name": "Broken", "url": "https://this-domain-should-not-exist.invalid"}
    )
    service_id = resp.json()["id"]

    resp = client.post(f"/services/{service_id}/check")
    assert resp.status_code == 200
    assert resp.json()["status"] == "DOWN"


def test_reject_private_ip_target(client):
    resp = client.post("/services", json={"name": "Metadata", "url": "http://169.254.169.254/latest/meta-data"})
    assert resp.status_code == 422


def test_reject_localhost_target(client):
    resp = client.post("/services", json={"name": "Local", "url": "http://localhost:9000"})
    assert resp.status_code == 422


def test_reject_non_http_scheme(client):
    resp = client.post("/services", json={"name": "FileScheme", "url": "file:///etc/passwd"})
    assert resp.status_code == 422


def test_availability_and_recent_checks(client):
    resp = client.post("/services", json={"name": "Stats", "url": "https://example.com"})
    service_id = resp.json()["id"]

    client.post(f"/services/{service_id}/check")
    client.post(f"/services/{service_id}/check")

    resp = client.get("/services")
    service = next(s for s in resp.json() if s["id"] == service_id)
    assert 0 <= service["availability_percent"] <= 100
    assert len(service["recent_checks"]) == 2
