"""Test isolation: import first in every test module.

Removes credentials from the environment and blocks every non-loopback network connection.
Tests that need a service must mock it (patch.object / patch.dict) or use a loopback server.
"""
import ipaddress
import os
import socket

SECRET_PREFIXES = ("HILDRETH_FIRST_PARTY_", "ENDOSCOPY_", "ADMIN_API", "DASHBOARD_", "PLAY_", "GA4_", "RC_", "GOOGLE_", "GCLOUD", "CLOUDSDK_")


class NetworkBlocked(OSError):
    pass


def is_loopback(host):
    if host in (None, "", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def clear_credentials():
    for name in [n for n in os.environ if n.startswith(SECRET_PREFIXES)]:
        del os.environ[name]


def install_network_guard():
    if getattr(socket, "_owner_dashboard_guard", False):
        return
    connect, connect_ex, getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def check(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0] if isinstance(address, tuple) else address
            if not is_loopback(host):
                raise NetworkBlocked(f"external network access blocked in tests: {host!r}")

    def guarded_connect(self, address, *args, **kwargs):
        check(self, address)
        return connect(self, address, *args, **kwargs)

    def guarded_connect_ex(self, address, *args, **kwargs):
        check(self, address)
        return connect_ex(self, address, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not is_loopback(host):
            raise NetworkBlocked(f"external DNS lookup blocked in tests: {host!r}")
        return getaddrinfo(host, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = guarded_connect, guarded_connect_ex, guarded_getaddrinfo
    socket._owner_dashboard_guard = True


clear_credentials()
install_network_guard()
