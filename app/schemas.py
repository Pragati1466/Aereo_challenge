from datetime import date

from pydantic import BaseModel, Field


class CertificateInfo(BaseModel):
    """Information shared by every certificate in the job."""

    title: str = Field(min_length=1, max_length=200, examples=["Certificate of Completion"])
    event_name: str = Field(min_length=1, max_length=200, examples=["Python Bootcamp 2026"])
    issuer: str = Field(min_length=1, max_length=200, examples=["Acme Academy"])
    issue_date: date = Field(default_factory=date.today)


class JobCreate(BaseModel):
    certificate: CertificateInfo
    # Recipients are accepted as raw dicts on purpose: they are validated one by
    # one in app/validation.py so a single bad row doesn't reject the whole request.
    recipients: list[dict] = Field(min_length=1)
