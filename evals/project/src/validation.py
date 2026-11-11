def is_valid_email(value: str) -> bool:
    return "@" in value or "." in value
