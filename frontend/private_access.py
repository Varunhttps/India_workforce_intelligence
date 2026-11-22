"""Fail-closed private-access configuration helpers for the Streamlit dashboard."""

REQUIRED_AUTH_KEYS = frozenset({"client_id", "client_secret", "redirect_uri", "cookie_secret"})


def parse_allowed_emails(configured):
    """Normalize a comma-separated string or sequence of email addresses."""
    if isinstance(configured, str):
        entries = configured.split(",")
    elif isinstance(configured, (list, tuple, set)):
        entries = configured
    else:
        entries = []
    return {
        str(entry).strip().casefold()
        for entry in entries
        if str(entry).strip()
    }


def missing_auth_keys(auth_config):
    """Return required OIDC keys that are absent from the provided mapping."""
    if not hasattr(auth_config, "keys"):
        auth_config = {}
    return sorted(REQUIRED_AUTH_KEYS - set(auth_config.keys()))


def is_email_allowed(email, allowed_emails):
    """Check a normalized email against an exact allowlist match."""
    normalized = str(email or "").strip().casefold()
    if not normalized:
        return False
    normalized_allowlist = {
        str(entry).strip().casefold()
        for entry in (allowed_emails or ())
        if str(entry).strip()
    }
    return normalized in normalized_allowlist
