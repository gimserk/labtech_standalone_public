"""Cyber City MicroPython HTTPS requests for an isolated classroom lab.

By default, accept any HTTPS certificate (including self-signed or expired)
without authentication. Encryption remains, but a network attacker can
impersonate LabTech and steal the provisioning key or tamper with OTA content.
Set LABTECH_TLS_VERIFY = True and configure LABTECH_CA_CERT_FILE to opt in to
certificate verification. Both modes restrict requests to the configured
LabTech firmware API origin; neither mode follows redirects.
"""
try:
    import usocket as socket
except ImportError:
    import socket
try:
    import ssl
except ImportError:
    import ussl as ssl
try:
    import ujson as json
except ImportError:
    import json
from bootstrap_config import LABTECH_URL

MAX_JSON_BYTES = 256 * 1024


def _origin():
    base = LABTECH_URL.rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("LabTech URL must use HTTPS")
    authority = base[8:]
    if (not authority or "/" in authority or "@" in authority or
            "?" in authority or "#" in authority or any(c.isspace() for c in authority)):
        raise ValueError("LabTech URL must be a single HTTPS origin")
    if authority.count(":") > 1:
        raise ValueError("IPv6 URLs are not supported; use the certificate DNS name")
    if ":" in authority:
        host, port_string = authority.rsplit(":", 1)
        if not port_string.isdigit():
            raise ValueError("Invalid HTTPS port")
        port = int(port_string)
    else:
        host, port = authority, 443
    if not host or not 1 <= port <= 65535:
        raise ValueError("Invalid LabTech HTTPS host/port")
    return base, authority, host, port


def _target(url):
    base, authority, host, port = _origin()
    if not isinstance(url, str) or not url.startswith(base + "/api/firmware/"):
        raise ValueError("HTTPS request must target the configured LabTech firmware API")
    path = url[len(base):]
    if "#" in path or any(c in path for c in ("\r", "\n", " ")):
        raise ValueError("Invalid HTTPS request path")
    return authority, host, port, path


def _trusted_context():
    try:
        from bootstrap_config import LABTECH_CA_CERT_FILE
    except ImportError:
        raise ValueError("Set LABTECH_CA_CERT_FILE in bootstrap_config.py")
    if not isinstance(LABTECH_CA_CERT_FILE, str) or not LABTECH_CA_CERT_FILE:
        raise ValueError("Configure a trusted LabTech CA certificate (DER file)")
    try:
        with open(LABTECH_CA_CERT_FILE, "rb") as handle:
            ca = handle.read(16384)
        if not ca or len(ca) >= 16384:
            raise ValueError("LabTech CA certificate is empty or too large")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ca)
        context.verify_mode = ssl.CERT_REQUIRED
        if context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("TLS certificate verification unavailable")
        return context
    except (OSError, AttributeError, TypeError) as exc:
        raise ValueError("MicroPython TLS cannot load/verify the LabTech CA: %s" % exc)



def _https_context():
    """Select HTTPS trust behavior for the isolated Cyber City lab.

    Explicitly set LABTECH_TLS_VERIFY = True in bootstrap_config.py to
    validate the server's certificate with LABTECH_CA_CERT_FILE. Existing
    bootstrap configs without the flag default to the requested lab mode.
    """
    import bootstrap_config
    verify = getattr(bootstrap_config, "LABTECH_TLS_VERIFY", False)
    if type(verify) is not bool:
        raise ValueError("LABTECH_TLS_VERIFY must be True or False")
    if verify:
        return _trusted_context()
    # Insecure lab-only mode: deliberately skip CA, expiry, and hostname
    # verification. Keep HTTPS and the existing same-origin API restriction.
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if hasattr(context, "check_hostname"):
            context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        if context.verify_mode != ssl.CERT_NONE:
            raise ValueError("TLS certificate verification could not be disabled")
        return context
    except (OSError, AttributeError, TypeError) as exc:
        raise ValueError("MicroPython TLS cannot enable unverified HTTPS: %s" % exc)


def _line(stream):
    if hasattr(stream, "readline"):
        line = stream.readline()
        if len(line) > 8192:
            raise ValueError("HTTPS header line too long")
        return line
    buf = bytearray()
    while len(buf) < 8192:
        b = stream.read(1)
        if not b:
            return bytes(buf)
        buf.extend(b)
        if b == b"\n":
            return bytes(buf)
    raise ValueError("HTTPS header line too long")


def _exact(stream, amount):
    result = bytearray()
    while len(result) < amount:
        data = stream.read(amount - len(result))
        if not data:
            raise OSError("Truncated HTTPS response")
        result.extend(data)
    return bytes(result)


class _Body:
    def __init__(self, stream, length=None, chunked=False):
        self.stream = stream
        self.chunked = chunked
        self.remaining = 0 if chunked else (length if length is not None else -1)
        self.finished = False

    def read(self, n=-1):
        if n is None or n < 0:
            result = bytearray()
            while True:
                part = self.read(4096)
                if not part:
                    return bytes(result)
                result.extend(part)
        if n == 0 or self.finished:
            return b""
        result = bytearray()
        while len(result) < n:
            if self.chunked and self.remaining == 0:
                line = _line(self.stream).strip().split(b";", 1)[0]
                if not line:
                    raise OSError("Invalid HTTPS chunk header")
                self.remaining = int(line, 16)
                if self.remaining == 0:
                    while True:
                        trailer = _line(self.stream)
                        if not trailer or trailer == b"\r\n":
                            break
                    self.finished = True
                    break
            if self.remaining == 0:
                self.finished = True
                break
            count = n - len(result)
            if self.remaining > 0:
                count = min(count, self.remaining)
            piece = self.stream.read(count)
            if not piece:
                if self.remaining > 0:
                    raise OSError("Truncated HTTPS response body")
                self.finished = True
                break
            result.extend(piece)
            if self.remaining > 0:
                self.remaining -= len(piece)
            if self.chunked and self.remaining == 0:
                if _exact(self.stream, 2) != b"\r\n":
                    raise OSError("Invalid HTTPS chunk terminator")
        return bytes(result)

    def close(self):
        self.stream.close()


class _Response:
    def __init__(self, stream, status, length, chunked):
        self.status_code = status
        self.raw = _Body(stream, length=length, chunked=chunked)

    def json(self):
        data = bytearray()
        while True:
            part = self.raw.read(4096)
            if not part:
                return json.loads(bytes(data).decode("utf-8"))
            data.extend(part)
            if len(data) > MAX_JSON_BYTES:
                raise ValueError("LabTech JSON response too large")

    def close(self):
        self.raw.close()


def request(method, url, headers=None, data=None, stream=False):
    authority, host, port, path = _target(url)
    if method not in ("GET", "POST"):
        raise ValueError("Unsupported HTTPS method")
    if data is not None and isinstance(data, str):
        data = data.encode("utf-8")
    if data is not None and not isinstance(data, bytes):
        raise ValueError("HTTPS body must be bytes or text")
    if data is not None and len(data) > MAX_JSON_BYTES:
        raise ValueError("HTTPS request body too large")
    values = {"Host": authority, "Connection": "close", "Accept": "application/json"}
    if headers:
        for key, value in headers.items():
            if (not isinstance(key, str) or not isinstance(value, str) or
                    any(c in key + value for c in ("\r", "\n")) or
                    key.lower() in ("host", "connection", "content-length", "transfer-encoding")):
                raise ValueError("Invalid HTTPS header")
            values[key] = value
    if data is not None:
        values["Content-Length"] = str(len(data))
    addr = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]
    plain = socket.socket(addr[0], socket.SOCK_STREAM, addr[2])
    wrapped = None
    try:
        plain.settimeout(20)
        plain.connect(addr[-1])
        # Verifies the configured local CA AND requests hostname checking.
        # Unsupported MicroPython ports must fail closed, not retry insecure.
        wrapped = _https_context().wrap_socket(plain, server_hostname=host)
        message = method + " " + path + " HTTP/1.1\r\n"
        for key, value in values.items():
            message += key + ": " + value + "\r\n"
        message += "\r\n"
        wrapped.write(message.encode("utf-8"))
        if data is not None:
            wrapped.write(data)
        status_line = _line(wrapped).split(None, 2)
        if len(status_line) < 2 or not status_line[0].startswith(b"HTTP/"):
            raise OSError("Invalid LabTech HTTPS response")
        status = int(status_line[1])
        length = None
        chunked = False
        for _ in range(64):
            line = _line(wrapped)
            if line in (b"\r\n", b"\n"):
                break
            if not line or b":" not in line:
                raise OSError("Invalid HTTPS response headers")
            key, value = line.split(b":", 1)
            if key.strip().lower() == b"content-length":
                length = int(value.strip())
                if length < 0:
                    raise ValueError("Invalid HTTPS content length")
            elif key.strip().lower() == b"transfer-encoding" and b"chunked" in value.lower():
                chunked = True
        else:
            raise OSError("Too many HTTPS response headers")
        # Do not follow redirects: never forward the device key elsewhere.
        return _Response(wrapped, status, None if chunked else length, chunked)
    except Exception:
        (wrapped or plain).close()
        raise


def get(url, headers=None, stream=False):
    return request("GET", url, headers=headers, stream=stream)


def post(url, data=None, headers=None):
    return request("POST", url, data=data, headers=headers)
