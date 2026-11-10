def slugify(text: str) -> str:
    """Return a lower-case slug with hyphens instead of spaces."""
    return text.replace(" ", "-")
