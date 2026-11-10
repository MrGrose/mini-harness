def page_offset(page: int, size: int) -> int:
    """Return the offset for a one-based page number."""
    return page * size
