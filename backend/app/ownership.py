"""Ownership policy for identities asserted by a trusted upstream.

This does not authenticate headers. Reserved legacy identities are quarantined,
even when a client knows their exact value; an administrator must verify and
reassign ownership before those records can be accessed through booking APIs.
"""


def is_quarantined_owner(owner: str) -> bool:
    return owner.startswith("legacy_") or owner in {"anonymous", "unassigned"}
