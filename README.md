# Bulk Certificate Generator

A robust backend API that accepts a list of recipients, validates them, generates a PDF
certificate for each valid recipient from one predefined template, tracks progress,
and lets the client download the results.

**Stack:** Python 3.10+, FastAPI, SQLAlchemy 2 + SQLite (relational DB), ReportLab (PDF), pytest.

---

## Table of Contents

- [Features](#features)
- [Project Overview](#project-overview)
- [Setup](#setup)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [API Documentation](#api-documentation)
  - [Submit a Certificate Generation Request](#1-submit-a-certificate-generation-request---post-jobs-returns-202-accepted)
  - [Check Job Status and Progress](#2-check-job-status-and-progress---get-jobsjob_id)
  - [Retrieve Generated Certificates](#3-retrieve-generated-certificates)
- [Configuration](#configuration)
- [Design Decisions](#design-decisions)
- [Known Limitations and Future Improvements](#known-limitations-and-future-improvements)
- [Project Layout](#project-layout)
- [Troubleshooting](#troubleshooting)

---

## Features

- ✅ **Bulk Certificate Generation**: Process hundreds or thousands of certificates in a single request
- ✅ **Asynchronous Processing**: Jobs run in the background without blocking the API
- ✅ **Real-time Progress Tracking**: Poll job status to see completion percentage and individual item results
- ✅ **Per-Recipient Validation**: Invalid recipients are caught and reported without blocking valid ones
- ✅ **Failure Isolation**: One certificate generation failure doesn't stop the rest
- ✅ **Flexible Download**: Download individual certificates or all successful ones as a ZIP
- ✅ **Sanitized File Handling**: Safe file storage with temp files and atomic renames
- ✅ **Comprehensive Testing**: 13 tests covering all critical functionality

---

## Project Overview

This API is designed for scenarios where you need to generate certificates for many recipients at once, such as:
- Course completion certificates
- Event participation certificates
- Achievement recognition
- Training program certifications

The system validates each recipient, generates PDF certificates using a customizable template, stores them securely, and provides download endpoints. The asynchronous design ensures that even large requests don't timeout.

---

## Setup

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Installation Steps

1. **Clone or extract the project**:
   ```bash
   # If you have a zip file
   unzip bulk_certificates.zip
   cd bulk_certificates
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   ```

3. **Activate the virtual environment**:
   ```bash
   # macOS/Linux
   source .venv/bin/activate

   # Windows
   .venv\Scripts\activate
   ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   This will install:
   - FastAPI (web framework)
   - Uvicorn (ASGI server)
   - SQLAlchemy 2 (ORM)
   - ReportLab (PDF generation)
   - pytest (testing framework)
   - And other supporting libraries

---

## Running the Application

### Development Mode (with auto-reload)

```bash
uvicorn app.main:create_app --factory --reload
```

The server will start at `http://127.0.0.1:8000`

### Production Mode

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 4
```

### Accessing Interactive API Documentation

Once the server is running, visit:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

These provide interactive documentation where you can test all endpoints directly from your browser.

---

## Running Tests

The project includes a comprehensive test suite with 13 tests covering all critical functionality.

### Run all tests

```bash
pytest
```

### Run with verbose output

```bash
pytest -v
```

### Run with coverage

```bash
pytest --cov=app --cov-report=html
```

### Test Coverage

The test suite covers:
- ✅ Job creation and API responses
- ✅ Input validation (empty lists, missing fields, limits)
- ✅ Per-recipient validation (email format, duplicates, required fields)
- ✅ PDF certificate generation
- ✅ Job status and progress tracking
- ✅ Individual certificate failure handling
- ✅ Certificate download (single and ZIP)
- ✅ Error handling for invalid/failure scenarios

---

## API Documentation

### 1. Submit a Certificate Generation Request — `POST /jobs` (returns `202 Accepted`)

Create a new job to generate certificates for multiple recipients.

**Endpoint**: `POST /jobs`

**Request Body**:

```json
{
  "certificate": {
    "title": "Certificate of Completion",
    "event_name": "Python Bootcamp 2026",
    "issuer": "Acme Academy",
    "issue_date": "2026-10-01"
  },
  "recipients": [
    {
      "name": "Asha Verma",
      "email": "asha@example.com"
    },
    {
      "name": "Rahul Singh",
      "email": "rahul@example.com",
      "achievement": "With Distinction"
    },
    {
      "name": "Priya Sharma",
      "email": "priya@example.com"
    }
  ]
}
```

**Field Descriptions**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `certificate.title` | string | Yes | Certificate title displayed on the PDF |
| `certificate.event_name` | string | Yes | Name of the event/course |
| `certificate.issuer` | string | Yes | Organization issuing the certificate |
| `certificate.issue_date` | string | No | Issue date (YYYY-MM-DD format). Defaults to today |
| `recipients[].name` | string | Yes | Recipient's full name |
| `recipients[].email` | string | Yes | Recipient's email address (must be valid format) |
| `recipients[].achievement` | string | No | Optional achievement text to display on certificate |

**Response** (202 Accepted):

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "PENDING",
  "total": 3,
  "counts": {
    "pending": 3,
    "success": 0,
    "failed": 0
  },
  "progress_percent": 0.0,
  "created_at": "2026-10-07T10:30:00Z",
  "completed_at": null
}
```

**Example using curl**:

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "certificate": {
      "title": "Certificate of Completion",
      "event_name": "Python Bootcamp 2026",
      "issuer": "Acme Academy",
      "issue_date": "2026-10-01"
    },
    "recipients": [
      {"name": "Asha Verma", "email": "asha@example.com"},
      {"name": "Rahul Singh", "email": "rahul@example.com", "achievement": "With Distinction"}
    ]
  }'
```

**Validation Rules**:
- At least 1 recipient required
- Maximum 5,000 recipients per request (configurable via `MAX_RECIPIENTS`)
- Each recipient must have a non-empty name and valid email
- Duplicate emails (case-insensitive) within the same job are rejected
- Recipients with invalid data are marked as FAILED but don't block valid ones

---

### 2. Check Job Status and Progress — `GET /jobs/{job_id}`

Retrieve the current status, progress, and results of a job.

**Endpoint**: `GET /jobs/{job_id}`

**Query Parameters**:
- `include_items` (boolean, default: `true`) - Whether to include individual recipient results

**Response**:

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "COMPLETED_WITH_ERRORS",
  "total": 3,
  "counts": {
    "pending": 0,
    "success": 2,
    "failed": 1
  },
  "progress_percent": 100.0,
  "created_at": "2026-10-07T10:30:00Z",
  "completed_at": "2026-10-07T10:30:05Z",
  "items": [
    {
      "item_id": 1,
      "row_index": 0,
      "name": "Asha Verma",
      "email": "asha@example.com",
      "status": "SUCCESS",
      "error": null,
      "download_url": "/jobs/abc123-def456-ghi789/certificates/1"
    },
    {
      "item_id": 2,
      "row_index": 1,
      "name": "Rahul Singh",
      "email": "rahul@example.com",
      "status": "SUCCESS",
      "error": null,
      "download_url": "/jobs/abc123-def456-ghi789/certificates/2"
    },
    {
      "item_id": 3,
      "row_index": 2,
      "name": "",
      "email": "broken",
      "status": "FAILED",
      "error": "name is required; email is not a valid email address",
      "download_url": null
    }
  ]
}
```

**Job Status Flow**:
- `PENDING` → Job created, waiting to start processing
- `PROCESSING` → Currently generating certificates
- `COMPLETED` → All certificates generated successfully
- `COMPLETED_WITH_ERRORS` → Some certificates failed, but at least one succeeded
- `FAILED` → No certificates were generated (all failed or validation rejected everything)

**Lightweight Polling**:

For frequent status checks without the full item list:

```bash
curl http://127.0.0.1:8000/jobs/{job_id}?include_items=false
```

**Example using curl**:

```bash
# Full status with items
curl http://127.0.0.1:8000/jobs/abc123-def456-ghi789

# Lightweight status (no items)
curl http://127.0.0.1:8000/jobs/abc123-def456-ghi789?include_items=false
```

---

### 3. Retrieve Generated Certificates

#### Download a Single Certificate

**Endpoint**: `GET /jobs/{job_id}/certificates/{item_id}`

**Response**: PDF file (application/pdf)

**Example**:

```bash
curl -OJ http://127.0.0.1:8000/jobs/abc123-def456-ghi789/certificates/1
```

The downloaded filename will be sanitized, e.g., `Asha_Verma_certificate.pdf`.

**Error Responses**:
- `404` - Job or certificate not found
- `409` - Certificate not available (generation failed or still in progress)
- `410` - Certificate file missing from storage

#### Download All Certificates as ZIP

**Endpoint**: `GET /jobs/{job_id}/download`

**Response**: ZIP file containing all successfully generated certificates (application/zip)

**Example**:

```bash
curl -OJ http://127.0.0.1:8000/jobs/abc123-def456-ghi789/download
```

The ZIP filename will be `certificates_{job_id}.zip`. Each PDF inside is named as `{row_index}_{sanitized_name}.pdf` (e.g., `0001_Asha_Verma.pdf`).

**Error Responses**:
- `404` - Job not found
- `409` - No certificates available yet (all failed or still processing)

---

## Configuration

The application can be configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./certs.db` | SQLAlchemy database URL. Can use PostgreSQL, MySQL, etc. |
| `CERT_STORAGE_DIR` | `./storage` | Directory where generated PDF certificates are stored |
| `MAX_RECIPIENTS` | `5000` | Maximum number of recipients allowed per request |

### Setting Environment Variables

**macOS/Linux**:
```bash
export DATABASE_URL="postgresql://user:pass@localhost/certs"
export CERT_STORAGE_DIR="/var/certificates"
export MAX_RECIPIENTS="10000"
uvicorn app.main:create_app --factory --reload
```

**Windows (PowerShell)**:
```powershell
$env:DATABASE_URL="postgresql://user:pass@localhost/certs"
$env:CERT_STORAGE_DIR="C:\certificates"
$env:MAX_RECIPIENTS="10000"
uvicorn app.main:create_app --factory --reload
```

**Using .env file** (requires python-dotenv):
```bash
# Create a .env file in the project root
DATABASE_URL=postgresql://user:pass@localhost/certs
CERT_STORAGE_DIR=/var/certificates
MAX_RECIPIENTS=10000
```

---

## Design Decisions

This section explains the key architectural and implementation decisions made during development.

### 1. Background Processing (Asynchronous)

**Decision**: Certificate generation runs in the background using FastAPI's `BackgroundTask` rather than synchronously in the request handler.

**Rationale**:
- A request may contain thousands of recipients, and generating PDFs is CPU-intensive
- Synchronous generation would cause HTTP timeouts for large requests
- Clients can poll for status while work progresses

**Trade-off**:
- Background tasks run in-process, so a server restart mid-job leaves the job unfinished
- For production, consider swapping in a task queue (Celery, RQ, or Arq)
- The API and DB design remain the same; only `process_job` needs to move to a worker

### 2. Per-Recipient Validation and Isolation

**Decision**: Recipients are validated individually, and invalid entries are marked as FAILED rather than rejecting the entire request.

**Rationale**:
- In real-world scenarios, CSV/Excel imports often have some bad rows
- Users prefer to see partial success with error details rather than all-or-nothing failure
- Invalid rows are saved with specific error messages for debugging

**Implementation**:
- Request-level validation (missing certificate info, empty list, over limit) returns `422`
- Per-recipient validation (empty name, invalid email, duplicates) marks items as `FAILED`
- Jobs with any valid recipients proceed; jobs with only invalid recipients are marked `FAILED`

### 3. Failure Isolation During Generation

**Decision**: Each certificate generation has its own `try/except` block and database commit.

**Rationale**:
- One rendering failure (e.g., font issue, name too long) shouldn't stop other certificates
- Progress is visible in real-time as items complete
- If the entire job crashes (e.g., disk full), remaining items are marked as FAILED rather than stuck in PENDING

**Implementation**:
- Each recipient is processed in its own transaction
- Status updates are committed immediately after each certificate
- Job-level exception handler marks remaining items as FAILED

### 4. Data Model

**Decision**: Two-table model with `jobs` (shared info) and `items` (per-recipient records).

**Rationale**:
- Separates shared certificate metadata from per-recipient data
- Enables efficient queries for job status and individual item status
- Counts are computed with `GROUP BY` rather than stored counters to prevent drift

**Schema**:
- `jobs`: job_id, certificate info, status, timestamps
- `items`: item_id, job_id, row_index, name, email, status, error, file_path

### 5. Safe File Handling

**Decision**: PDFs are stored with deterministic paths, written to temp files, and atomically renamed.

**Rationale**:
- Prevents path traversal attacks (no user-supplied names in paths)
- Avoids half-written certificates if generation crashes mid-file
- Prevents filename collisions and special character issues

**Implementation**:
- Storage path: `{storage_dir}/{job_id}/{item_id}.pdf`
- Write to `{path}.tmp`, then rename to `{path}` (atomic on most filesystems)
- Download filenames are sanitized (remove special characters)
- Items are looked up by both `job_id` and `item_id` for security

### 6. Certificate Template

**Decision**: Single template drawn with ReportLab in `app/generator.py`.

**Rationale**:
- ReportLab provides fine-grained control over PDF layout
- A4 landscape orientation with decorative borders
- Auto-shrinking font size for long names to fit the template
- Easy to customize by editing `generate_certificate_pdf()`

**Features**:
- Decorative border
- Title, event name, issuer, date
- Recipient name (auto-scaled)
- Optional achievement line
- QR code placeholder (can be added)

### 7. App Factory Pattern

**Decision**: Application is created via `create_app(settings)` function rather than global app instance.

**Rationale**:
- Enables dependency injection of settings for testing
- Tests can use temporary database and storage directory
- No global state between test runs
- Supports multiple app instances if needed

**Implementation**:
- Settings can be passed in or loaded from environment
- Session factory is created per app instance
- Storage directory is created on app startup

---

## Known Limitations and Future Improvements

### Current Limitations

1. **No Authentication**: The API has no authentication or authorization. Anyone who can access the endpoint can create jobs and download certificates.

2. **No Rate Limiting**: There's no protection against abuse or DoS attacks. A malicious user could submit many large jobs.

3. **No Job Recovery**: If the server restarts while a job is processing, that job remains stuck in `PROCESSING` state. There's no automatic recovery or retry mechanism.

4. **In-Process Background Tasks**: Background tasks run in the same process as the web server. A server crash loses all in-progress jobs.

5. **Local Storage Only**: Certificates are stored on the local filesystem. This doesn't scale across multiple servers or to cloud deployments.

6. **No Database Migrations**: Tables are created automatically with `create_all()`. There's no version control for schema changes.

### Recommended Improvements for Production

1. **Add Authentication**:
   - Implement API key authentication or OAuth2
   - Add user accounts and permission controls
   - Consider rate limiting per user

2. **Task Queue**:
   - Replace FastAPI `BackgroundTask` with Celery, RQ, or Arq
   - Enables job persistence across server restarts
   - Supports multiple worker processes for better performance
   - Allows retrying failed items

3. **Cloud Storage**:
   - Move PDF storage to S3, GCS, or Azure Blob Storage
   - Enables scaling across multiple servers
   - Provides better durability and backup options

4. **Database Migrations**:
   - Add Alembic for database version control
   - Enables safe schema changes in production

5. **Job Recovery**:
   - Add endpoint to retry failed items
   - Implement job resume after server restart
   - Add job cleanup/deletion endpoints

6. **Monitoring and Logging**:
   - Add structured logging (JSON format)
   - Integrate with monitoring tools (Prometheus, DataDog)
   - Add metrics for job processing times and success rates

7. **Enhanced Template System**:
   - Support multiple certificate templates
   - Allow custom templates via admin interface
   - Add support for logos, signatures, and backgrounds

---

## Project Layout

```
bulk_certificates/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app factory and route definitions
│   ├── service.py        # Business logic: create_job, process_job, serialization
│   ├── validation.py     # Per-recipient validation logic
│   ├── generator.py      # PDF certificate generation with ReportLab
│   ├── models.py         # SQLAlchemy ORM models (Job, Item)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── database.py       # Database engine and session factory
│   └── config.py         # Settings configuration from environment
├── tests/
│   ├── __init__.py
│   ├── conftest.py       # pytest fixtures (client, test settings)
│   └── test_jobs.py      # Comprehensive test suite (13 tests)
├── storage/              # Generated PDF certificates (created at runtime)
├── .gitignore
├── pytest.ini            # pytest configuration
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

### Key Files Explained

- **`app/main.py`**: Entry point with FastAPI app factory. Defines all API endpoints (`/jobs`, `/jobs/{id}`, download endpoints).

- **`app/service.py`**: Core business logic. Handles job creation, background processing, and data serialization for API responses.

- **`app/validation.py`**: Validates individual recipient data (name, email format, duplicates). Returns detailed error messages.

- **`app/generator.py`**: PDF generation using ReportLab. Contains the certificate template and logic to render individual certificates.

- **`app/models.py`**: SQLAlchemy ORM models. Defines `Job` and `Item` tables with relationships and status constants.

- **`app/schemas.py`**: Pydantic models for request validation and response serialization.

- **`app/database.py`**: Database connection management. Creates engine and session factory.

- **`app/config.py`**: Application settings. Loads configuration from environment variables with defaults.

- **`tests/test_jobs.py`**: Test suite covering job creation, validation, generation, status tracking, and downloads.

---

## Troubleshooting

### Common Issues and Solutions

#### 1. Port Already in Use

**Error**: `OSError: [Errno 48] Address already in use`

**Solution**: Either stop the process using port 8000 or use a different port:
```bash
# Use a different port
uvicorn app.main:create_app --factory --reload --port 8001
```

#### 2. Import Errors

**Error**: `ModuleNotFoundError: No module named 'app'`

**Solution**: Ensure you're running from the project root directory and the virtual environment is activated:
```bash
cd /path/to/bulk_certificates
source .venv/bin/activate
uvicorn app.main:create_app --factory --reload
```

#### 3. Database Lock Errors

**Error**: `sqlite3.OperationalError: database is locked`

**Solution**: This can happen with SQLite under high concurrent load. For production, use PostgreSQL or MySQL:
```bash
export DATABASE_URL="postgresql://user:pass@localhost/certs"
```

#### 4. Storage Directory Permissions

**Error**: `PermissionError: [Errno 13] Permission denied`

**Solution**: Ensure the application has write permissions to the storage directory:
```bash
mkdir -p storage
chmod 755 storage
```

Or configure a different storage directory:
```bash
export CERT_STORAGE_DIR="/tmp/certificates"
```

#### 5. PDF Generation Fails

**Error**: Certificate items show `FAILED` status with rendering errors

**Solution**: Check that ReportLab is properly installed and the system has required fonts:
```bash
pip install --upgrade reportlab
```

#### 6. Tests Fail with "No module named 'tests'"

**Error**: Tests fail to import modules

**Solution**: Run pytest from the project root directory:
```bash
cd /path/to/bulk_certificates
pytest
```

---

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `pytest`
2. New features include tests
3. Code follows existing style patterns
4. Documentation is updated if needed

