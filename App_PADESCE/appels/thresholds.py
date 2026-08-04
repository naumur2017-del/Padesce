PAS_FORME_II_THRESHOLD_PERCENT = 10


def pas_forme_ii_threshold_target(total: int) -> int:
    """Return the minimum completed forms, rounded up to a whole person."""
    total = int(total or 0)
    if total <= 0:
        return 0
    return max(1, (total * PAS_FORME_II_THRESHOLD_PERCENT + 99) // 100)
