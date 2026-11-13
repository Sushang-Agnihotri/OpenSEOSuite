"""SSRF protection.

Two layers:

1. ``validate_url`` - cheap syntactic checks (scheme, credentials, port, obvious internal hostnames,
   literal IPs) performed before a URL is queued or fetched.
2. ``SafeNetworkBackend`` - plugged into the HTTP connection pool. It resolves the hostname itself,
   rejects the connection if *any* resolved address is not public, and then connects to the vetted
   IP address. Because validation and connection use the same resolution, a DNS answer cannot be
   swapped between "check" and "use" (DNS rebinding). It runs for every connection, so redirect
   targets are covered as well.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpcore

ALLOWED_SCHEMES = {"http", "https"}
STRICT_PORTS = {80, 443, 8080, 8443}
_INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa", ".corp")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIXTOFOUR = ipaddress.ip_network("2002::/16")
_IPV4_COMPATIBLE = ipaddress.ip_network("::/96")  # deprecated ::a.b.c.d form
_SITE_LOCAL = ipaddress.ip_network("fec0::/10")  # deprecated, never globally routable


class UnsafeURLError(ValueError):
    """Raised when a URL or resolved address is not allowed to be fetched."""


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip in _SIXTOFOUR:
        return ipaddress.IPv4Address((int(ip) >> 80) & 0xFFFFFFFF)
    return None


def is_ip_allowed(ip_text: str, allow_private: bool = False) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        inner = _embedded_ipv4(ip)
        if inner is not None:
            ip = inner
    if ip.is_multicast or ip.is_unspecified:
        return False
    if allow_private:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and (ip in _IPV4_COMPATIBLE or ip in _SITE_LOCAL):
        return False  # Python's is_global still says True for these deprecated ranges
    return ip.is_global


def validate_url(url: str, allow_private: bool = False) -> str:
    """Return the URL if it is syntactically safe to fetch, else raise ``UnsafeURLError``."""
    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeURLError("URL is missing or too long")
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError(f"Malformed URL: {exc}") from exc
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs containing credentials are not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeURLError("URL has no hostname")
    if not allow_private:
        if port is not None and port not in STRICT_PORTS:
            raise UnsafeURLError(f"Port {port} is not allowed")
        if host == "localhost" or host.endswith(_INTERNAL_SUFFIXES):
            raise UnsafeURLError("Internal hostnames are not allowed")
    try:
        ipaddress.ip_address(host)
        literal = True
    except ValueError:
        literal = False
    if literal and not is_ip_allowed(host, allow_private):
        raise UnsafeURLError("IP address is not publicly routable")
    if not literal and not allow_private and "." not in host:
        raise UnsafeURLError("Single-label hostnames are not allowed")
    return url.strip()


async def resolve_and_check(host: str, port: int, allow_private: bool = False) -> list[str]:
    """Resolve ``host`` and return its addresses; raise if any address is not allowed."""
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise httpcore.ConnectError(f"DNS resolution failed for {host}: {exc}") from exc
    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    if not ips:
        raise httpcore.ConnectError(f"DNS returned no addresses for {host}")
    for ip in ips:
        if not is_ip_allowed(ip, allow_private):
            raise UnsafeURLError(f"{host} resolves to a non-public address ({ip})")
    return ips


class SafeNetworkBackend(httpcore.AsyncNetworkBackend):
    """Network backend that only ever connects to vetted IP addresses."""

    def __init__(self, allow_private: bool = False) -> None:
        self._inner = httpcore.AnyIOBackend()
        self._allow_private = allow_private

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        ips = await resolve_and_check(host, port, self._allow_private)
        last_exc: Exception | None = None
        for ip in ips:
            try:
                return await self._inner.connect_tcp(
                    ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                last_exc = exc
        raise last_exc or httpcore.ConnectError(f"Could not connect to {host}")

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise UnsafeURLError("Unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)
