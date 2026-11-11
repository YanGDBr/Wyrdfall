"""Best-effort local IP detection, so a host can tell a joiner what to type.

This finds the LAN IP the OS would use to reach the outside world -- it
does not send any packets (UDP "connect" just picks a local address for
routing). It has no way to know about a Tailscale interface specifically,
so a Tailscale-only setup needs the user to look up their `tailscale ip`
themselves; the host screen says so.
"""

from __future__ import annotations

import socket


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()
