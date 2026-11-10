def is_valid_email(value: str) -> bool:
    """Return True for a simple e-mail address."""
    return "@" in value or "." in value
