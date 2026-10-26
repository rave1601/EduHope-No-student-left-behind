"""
utils/validation.py — Input validators.
"""


def validate_approved_lte_enrolled(approved: int, enrolled: int, semester: str) -> str | None:
    """Return an error string if approved > enrolled, else None."""
    if approved > enrolled:
        return f"Approved units cannot exceed enrolled units for {semester} semester."
    return None


def clamp(value, lo, hi):
    return max(lo, min(hi, value))
