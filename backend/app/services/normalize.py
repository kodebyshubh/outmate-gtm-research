import re
from typing import Optional
from urllib.parse import urlparse

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def normalize_domain(raw: Optional[str]) -> Optional[str]:
    """Return a bare lowercase domain from a URL or domain string, or None if it is not valid."""
    if not raw or not raw.strip():
        return None
    text = raw.strip().lower()
    if "://" not in text:
        text = "http://" + text
    host = urlparse(text).hostname or ""
    host = host.removeprefix("www.")
    return host if _DOMAIN_RE.match(host) else None


def domain_from_url(url: str) -> Optional[str]:
    return normalize_domain(url)


def label_for(company_name: Optional[str], domain: Optional[str]) -> str:
    """Text used in search queries: the name if given, otherwise the domain stem."""
    if company_name and company_name.strip():
        return company_name.strip()
    return (domain or "").split(".")[0]
