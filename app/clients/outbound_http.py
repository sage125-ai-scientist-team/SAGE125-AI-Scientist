"""Explicit outbound-HTTPS policy shared by Model Studio clients.

Only ``OUTBOUND_HTTPS_PROXY`` is honored.  Environment HTTP(S)_PROXY values
are deliberately ignored so a Windows/VPN proxy cannot silently alter a
request's route.  TLS verification remains enabled for every client.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.core.logging import mask_text

if TYPE_CHECKING:
    from app.core.config import Settings


_PROXY_CREDENTIALS = re.compile(r"(?i)(https?://)([^/@\s]+)@")


def explicit_outbound_https_proxy(settings: "Settings") -> str:
    """Return only the project-scoped proxy setting, never environment proxy values."""
    return str(getattr(settings, "outbound_https_proxy", "") or "").strip()


def build_outbound_requests_session(settings: "Settings"):
    """Build a TLS-verifying requests session with the project's explicit proxy policy."""
    import requests

    session = requests.Session()
    session.trust_env = False
    session.verify = True
    proxy = explicit_outbound_https_proxy(settings)
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    return session


def build_outbound_httpx_client(settings: "Settings", *, timeout):
    """Build a TLS-verifying httpx client with the project's explicit proxy policy."""
    import httpx

    kwargs = {"timeout": timeout, "trust_env": False, "verify": True}
    proxy = explicit_outbound_https_proxy(settings)
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(**kwargs)


def redact_outbound_error(value: object) -> str:
    """Mask API keys and proxy userinfo before an exception is logged or returned."""
    text = _PROXY_CREDENTIALS.sub(r"\1***@", str(value or ""))
    return mask_text(text)
