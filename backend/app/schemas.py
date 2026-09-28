import ipaddress
import socket
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator


def _reject_private_targets(url: str) -> str:
    """Basic SSRF guard for the /check feature: it makes an outbound HTTP
    request to whatever URL the caller supplies, so without this check
    someone could point it at internal infrastructure (localhost, a
    cloud metadata endpoint like 169.254.169.254, an internal admin
    panel...). A hostname that simply doesn't resolve is NOT rejected —
    that's a legitimate "service is down/misconfigured" case the tool
    should be able to track, not a security concern.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("l'URL doit commencer par http:// ou https://")
    if not parsed.hostname:
        raise ValueError("URL invalide")
    try:
        addrs = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return url
    for *_, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("les URL pointant vers une adresse privée/interne ne sont pas autorisées")
    return url


class ServiceBase(BaseModel):
    name: str
    url: str
    description: Optional[str] = None
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _reject_private_targets(v)


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        return v if v is None else _reject_private_targets(v)


class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    checked_at: datetime


class ServiceOut(ServiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ServiceWithLastCheck(ServiceOut):
    last_check: Optional[CheckOut] = None
    availability_percent: Optional[float] = None
    recent_checks: list[CheckOut] = []
