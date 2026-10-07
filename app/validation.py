import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME = 100
MAX_EMAIL = 254
MAX_ACHIEVEMENT = 200


def validate_recipient(raw, seen_emails: set[str]) -> tuple[dict | None, str | None]:
    """Validate one recipient.

    Returns (clean_data, None) when valid or (None, error_message) when invalid.
    `seen_emails` is mutated so duplicate emails within one job are rejected.
    """
    if not isinstance(raw, dict):
        return None, "Recipient must be an object"

    errors = []

    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("name is required")
        name = None
    else:
        name = " ".join(name.split())
        if len(name) > MAX_NAME:
            errors.append(f"name must be at most {MAX_NAME} characters")

    email = raw.get("email")
    if not isinstance(email, str) or not email.strip():
        errors.append("email is required")
        email = None
    else:
        email = email.strip().lower()
        if len(email) > MAX_EMAIL or not EMAIL_RE.match(email):
            errors.append("email is not a valid email address")
        elif email in seen_emails:
            errors.append("duplicate email in this request")

    achievement = raw.get("achievement")
    if achievement is not None:
        if not isinstance(achievement, str):
            errors.append("achievement must be a string")
            achievement = None
        else:
            achievement = achievement.strip() or None
            if achievement and len(achievement) > MAX_ACHIEVEMENT:
                errors.append(f"achievement must be at most {MAX_ACHIEVEMENT} characters")

    if errors:
        return None, "; ".join(errors)

    seen_emails.add(email)
    return {"name": name, "email": email, "achievement": achievement}, None
