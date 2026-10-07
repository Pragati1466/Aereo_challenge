import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import generator
from app.models import (ITEM_FAILED, ITEM_PENDING, ITEM_SUCCESS, JOB_COMPLETED,
                        JOB_COMPLETED_WITH_ERRORS, JOB_FAILED, JOB_PENDING,
                        JOB_PROCESSING, Item, Job)
from app.schemas import JobCreate
from app.validation import validate_recipient


def create_job(db: Session, payload: JobCreate) -> Job:
    """Validate every recipient and persist the job.

    Invalid recipients are stored immediately as FAILED items (with the reason)
    so the client sees them in the job status. Valid ones start as PENDING.
    """
    cert = payload.certificate
    job = Job(
        id=str(uuid.uuid4()),
        title=cert.title,
        event_name=cert.event_name,
        issuer=cert.issuer,
        issue_date=cert.issue_date.isoformat(),
        status=JOB_PENDING,
        total=len(payload.recipients),
    )
    seen_emails: set[str] = set()
    valid_count = 0
    for idx, raw in enumerate(payload.recipients):
        clean, error = validate_recipient(raw, seen_emails)
        if clean:
            valid_count += 1
            job.items.append(Item(row_index=idx, status=ITEM_PENDING, **clean))
        else:
            raw_name = raw.get("name") if isinstance(raw, dict) else None
            raw_email = raw.get("email") if isinstance(raw, dict) else None
            job.items.append(Item(
                row_index=idx, status=ITEM_FAILED, error=error,
                name=str(raw_name)[:255] if raw_name is not None else None,
                email=str(raw_email)[:255] if raw_email is not None else None,
            ))

    if valid_count == 0:  # nothing to generate -> finished immediately
        job.status = JOB_FAILED
        job.completed_at = datetime.now(timezone.utc)

    db.add(job)
    db.commit()
    return job


def get_counts(db: Session, job_id: str) -> dict:
    rows = db.execute(
        select(Item.status, func.count()).where(Item.job_id == job_id).group_by(Item.status)
    ).all()
    counts = {ITEM_PENDING: 0, ITEM_SUCCESS: 0, ITEM_FAILED: 0}
    counts.update({status: n for status, n in rows})
    return {"pending": counts[ITEM_PENDING], "success": counts[ITEM_SUCCESS], "failed": counts[ITEM_FAILED]}


def _finalize(db: Session, job: Job) -> None:
    counts = get_counts(db, job.id)
    if counts["success"] == 0:
        job.status = JOB_FAILED
    elif counts["failed"] > 0:
        job.status = JOB_COMPLETED_WITH_ERRORS
    else:
        job.status = JOB_COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def process_job(session_factory: sessionmaker, storage_dir: str, job_id: str) -> None:
    """Generate all pending certificates of a job (runs in the background).

    Each certificate is isolated in its own try/except and committed
    individually, so one failure never stops the others and the status
    endpoint shows live progress.
    """
    db = session_factory()
    try:
        job = db.get(Job, job_id)
        job.status = JOB_PROCESSING
        db.commit()

        items = db.scalars(
            select(Item).where(Item.job_id == job_id, Item.status == ITEM_PENDING).order_by(Item.row_index)
        ).all()

        for item in items:
            rel_path = os.path.join(job_id, f"{item.id}.pdf")
            try:
                generator.generate_certificate_pdf(
                    os.path.join(storage_dir, rel_path),
                    name=item.name, title=job.title, event_name=job.event_name,
                    issuer=job.issuer, issue_date=job.issue_date, achievement=item.achievement,
                )
                item.status = ITEM_SUCCESS
                item.file_path = rel_path
            except Exception as exc:  # noqa: BLE001 - isolate any per-item failure
                item.status = ITEM_FAILED
                item.error = f"Certificate generation failed: {exc}"[:500]
            db.commit()

        _finalize(db, job)
    except Exception as exc:  # noqa: BLE001 - something job-level went wrong
        db.rollback()
        job = db.get(Job, job_id)
        if job is not None:
            for item in db.scalars(select(Item).where(Item.job_id == job_id, Item.status == ITEM_PENDING)):
                item.status = ITEM_FAILED
                item.error = f"Job aborted: {exc}"[:500]
            db.commit()
            _finalize(db, job)
    finally:
        db.close()


def serialize_job(db: Session, job: Job, include_items: bool = True) -> dict:
    counts = get_counts(db, job.id)
    done = counts["success"] + counts["failed"]
    data = {
        "job_id": job.id,
        "status": job.status,
        "total": job.total,
        "counts": counts,
        "progress_percent": round(100 * done / job.total, 1) if job.total else 100.0,
        "certificate": {
            "title": job.title, "event_name": job.event_name,
            "issuer": job.issuer, "issue_date": job.issue_date,
        },
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "download_all_url": f"/jobs/{job.id}/download",
    }
    if include_items:
        items = db.scalars(select(Item).where(Item.job_id == job.id).order_by(Item.row_index)).all()
        data["items"] = [
            {
                "item_id": i.id, "row_index": i.row_index, "name": i.name, "email": i.email,
                "status": i.status, "error": i.error,
                "download_url": f"/jobs/{job.id}/certificates/{i.id}" if i.status == ITEM_SUCCESS else None,
            }
            for i in items
        ]
    return data
