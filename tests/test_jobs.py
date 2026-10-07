import io
import zipfile

from app import generator
from tests.conftest import make_payload

GOOD = [
    {"name": "Asha Verma", "email": "asha@example.com"},
    {"name": "Rahul Singh", "email": "rahul@example.com", "achievement": "With Distinction"},
]


# ---------- Creating a job ----------
def test_create_job_returns_202_and_job_id(client):
    r = client.post("/jobs", json=make_payload(GOOD))
    assert r.status_code == 202
    body = r.json()
    assert body["job_id"]
    assert body["total"] == 2


# ---------- Input validation ----------
def test_request_level_validation(client):
    assert client.post("/jobs", json=make_payload([])).status_code == 422          # no recipients
    assert client.post("/jobs", json={"recipients": GOOD}).status_code == 422       # no certificate info
    too_many = [{"name": f"P{i}", "email": f"p{i}@example.com"} for i in range(51)]
    assert client.post("/jobs", json=make_payload(too_many)).status_code == 422     # over limit


def test_invalid_recipients_are_reported_but_do_not_block_valid_ones(client):
    recipients = GOOD + [
        {"name": "", "email": "x@example.com"},               # empty name
        {"name": "No Email"},                                  # missing email
        {"name": "Bad Email", "email": "not-an-email"},        # malformed email
        {"name": "Dup", "email": "ASHA@example.com"},          # duplicate (case-insensitive)
    ]
    body = client.post("/jobs", json=make_payload(recipients)).json()
    job = client.get(f"/jobs/{body['job_id']}").json()

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"] == {"pending": 0, "success": 2, "failed": 4}
    failed = [i for i in job["items"] if i["status"] == "FAILED"]
    assert all(i["error"] for i in failed)
    assert "name is required" in failed[0]["error"]
    assert "duplicate" in failed[3]["error"]


def test_all_invalid_job_is_failed_immediately(client):
    body = client.post("/jobs", json=make_payload([{"name": "", "email": ""}])).json()
    assert body["status"] == "FAILED"
    assert body["counts"]["failed"] == 1


# ---------- Certificate generation ----------
def test_generate_certificate_pdf_file(tmp_path):
    path = tmp_path / "out" / "cert.pdf"
    generator.generate_certificate_pdf(
        str(path), name="A Very Long Name " * 5, title="Certificate of Completion",
        event_name="Event", issuer="Issuer", issue_date="2026-10-01", achievement=None,
    )
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 500
    assert not (tmp_path / "out" / "cert.pdf.tmp").exists()


# ---------- Job status / progress ----------
def test_job_status_and_progress(client):
    job_id = client.post("/jobs", json=make_payload(GOOD)).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["progress_percent"] == 100.0
    assert job["counts"] == {"pending": 0, "success": 2, "failed": 0}
    assert job["completed_at"] is not None
    assert "items" not in client.get(f"/jobs/{job_id}?include_items=false").json()


def test_unknown_job_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404


# ---------- Individual certificate failure ----------
def test_one_generation_failure_does_not_stop_others(client, monkeypatch):
    real = generator.generate_certificate_pdf

    def flaky(path, **kwargs):
        if kwargs["name"] == "Boom":
            raise RuntimeError("render exploded")
        return real(path, **kwargs)

    monkeypatch.setattr(generator, "generate_certificate_pdf", flaky)
    recipients = [
        {"name": "First", "email": "1@example.com"},
        {"name": "Boom", "email": "2@example.com"},
        {"name": "Third", "email": "3@example.com"},
    ]
    job_id = client.post("/jobs", json=make_payload(recipients)).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert job["counts"] == {"pending": 0, "success": 2, "failed": 1}
    statuses = {i["name"]: i for i in job["items"]}
    assert statuses["Boom"]["status"] == "FAILED"
    assert "render exploded" in statuses["Boom"]["error"]
    assert statuses["Third"]["status"] == "SUCCESS"


def test_all_generations_failing_marks_job_failed(client, monkeypatch):
    def always_fail(path, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(generator, "generate_certificate_pdf", always_fail)
    job_id = client.post("/jobs", json=make_payload(GOOD)).json()["job_id"]
    assert client.get(f"/jobs/{job_id}").json()["status"] == "FAILED"


# ---------- Retrieving certificates ----------
def test_download_single_certificate(client):
    job_id = client.post("/jobs", json=make_payload(GOOD)).json()["job_id"]
    item = client.get(f"/jobs/{job_id}").json()["items"][0]
    r = client.get(item["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_download_zip_contains_only_successful_certificates(client):
    recipients = GOOD + [{"name": "Bad", "email": "bad"}]
    job_id = client.post("/jobs", json=make_payload(recipients)).json()["job_id"]
    r = client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(zf.namelist()) == 2
    assert all(n.endswith(".pdf") for n in zf.namelist())


def test_cannot_download_failed_or_foreign_certificate(client):
    job_id = client.post("/jobs", json=make_payload(GOOD + [{"name": "Bad", "email": "bad"}])).json()["job_id"]
    failed = [i for i in client.get(f"/jobs/{job_id}").json()["items"] if i["status"] == "FAILED"][0]
    assert client.get(f"/jobs/{job_id}/certificates/{failed['item_id']}").status_code == 409
    other = client.post("/jobs", json=make_payload(GOOD)).json()["job_id"]
    assert client.get(f"/jobs/{other}/certificates/{failed['item_id']}").status_code == 404
    assert client.get(f"/jobs/{job_id}/certificates/99999").status_code == 404


def test_zip_download_for_job_with_no_certificates_is_409(client):
    job_id = client.post("/jobs", json=make_payload([{"name": "", "email": ""}])).json()["job_id"]
    assert client.get(f"/jobs/{job_id}/download").status_code == 409
