PAS_FORME_II_THRESHOLD_PERCENT = 10


def pas_forme_ii_threshold_target(total: int) -> int:
    """Return the minimum completed forms, rounded up to a whole person."""
    total = int(total or 0)
    if total <= 0:
        return 0
    return max(1, (total * PAS_FORME_II_THRESHOLD_PERCENT + 99) // 100)


def pas_forme_ii_threshold_reached(total: int, completed: int) -> bool:
    total = int(total or 0)
    completed = int(completed or 0)
    return bool(total > 0 and completed >= pas_forme_ii_threshold_target(total))
