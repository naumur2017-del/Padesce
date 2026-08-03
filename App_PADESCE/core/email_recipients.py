"""Helpers for normalising configured report email recipients."""

import os
import re


def merge_email_recipients(value: str | None) -> list[str]:
    """Combine configured and extra recipients, preserving first-seen order."""
    raw_values = (value or "", os.getenv("REPORT_EMAIL_EXTRA_RECIPIENTS", ""))
    recipients = []
    seen = set()
    for raw in raw_values:
        for address in re.split(r"[,;\s]+", str(raw or "")):
            address = address.strip()
            key = address.lower()
            if address and key not in seen:
                seen.add(key)
                recipients.append(address)
    return recipients
