import io
import os
import re
import zipfile

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from app import service
from app.config import Settings, get_settings
from app.database import make_session_factory
from app.models import ITEM_SUCCESS, JOB_PENDING, Item, Job
from app.schemas import JobCreate


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "certificate"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    session_factory = make_session_factory(settings.database_url)
    os.makedirs(settings.storage_dir, exist_ok=True)

    app = FastAPI(title="Bulk Certificate Generator", version="1.0.0")
    app.state.settings = settings
    app.state.session_factory = session_factory

    def get_db(request: Request):
        db = request.app.state.session_factory()
        try:
            yield db
        finally:
            db.close()

    def get_job_or_404(db, job_id: str) -> Job:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.post("/jobs", status_code=202)
    def create_job(payload: JobCreate, background_tasks: BackgroundTasks, db=Depends(get_db)):
        """Submit a bulk request. Returns immediately; generation runs in the background."""
        if len(payload.recipients) > settings.max_recipients:
            raise HTTPException(
                status_code=422,
                detail=f"Too many recipients (max {settings.max_recipients} per request)",
            )
        job = service.create_job(db, payload)
        if job.status == JOB_PENDING:
            background_tasks.add_task(service.process_job, session_factory, settings.storage_dir, job.id)
        return service.serialize_job(db, job)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, include_items: bool = Query(True), db=Depends(get_db)):
        """Status, progress and per-recipient results (including error reasons)."""
        return service.serialize_job(db, get_job_or_404(db, job_id), include_items)

    @app.get("/jobs/{job_id}/certificates/{item_id}")
    def download_certificate(job_id: str, item_id: int, db=Depends(get_db)):
        """Download a single certificate PDF."""
        get_job_or_404(db, job_id)
        item = db.scalars(select(Item).where(Item.id == item_id, Item.job_id == job_id)).first()
        if item is None:
            raise HTTPException(status_code=404, detail="Certificate not found")
        if item.status != ITEM_SUCCESS or not item.file_path:
            raise HTTPException(status_code=409, detail=f"Certificate not available (status: {item.status})")
        full_path = os.path.join(settings.storage_dir, item.file_path)
        if not os.path.exists(full_path):
            raise HTTPException(status_code=410, detail="Certificate file is missing from storage")
        return FileResponse(full_path, media_type="application/pdf",
                            filename=f"{_safe_filename(item.name)}_certificate.pdf")

    @app.get("/jobs/{job_id}/download")
    def download_all(job_id: str, db=Depends(get_db)):
        """Download every successfully generated certificate of the job as a ZIP."""
        job = get_job_or_404(db, job_id)
        items = db.scalars(
            select(Item).where(Item.job_id == job_id, Item.status == ITEM_SUCCESS).order_by(Item.row_index)
        ).all()
        if not items:
            raise HTTPException(status_code=409, detail="No certificates available yet")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:  # PDFs are already compressed
            for item in items:
                full_path = os.path.join(settings.storage_dir, item.file_path)
                if os.path.exists(full_path):
                    zf.write(full_path, f"{item.row_index + 1:04d}_{_safe_filename(item.name)}.pdf")
        return Response(
            buf.getvalue(), media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="certificates_{job.id}.zip"'},
        )

    return app
