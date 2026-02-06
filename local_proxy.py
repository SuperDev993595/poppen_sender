"""
Local HTTP proxy that forwards to an upstream proxy with credentials.
Chrome connects to 127.0.0.1:local_port (no auth); this proxy adds
Proxy-Authorization when talking to the upstream proxy, so no dialog appears.
"""
import socket
import threading
import base64


def _add_proxy_auth(headers_bytes: bytes, username: str, password: str) -> bytes:
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    auth_header = f"Proxy-Authorization: Basic {auth}\r\n"
    # Insert after first line (request line)
    first_crlf = headers_bytes.find(b"\r\n")
    if first_crlf == -1:
        return headers_bytes
    return headers_bytes[: first_crlf + 2] + auth_header.encode() + headers_bytes[first_crlf + 2 :]


def _handle_client(
    client_sock: socket.socket,
    upstream_host: str,
    upstream_port: int,
    username: str,
    password: str,
):
    try:
        # Read request headers (until \r\n\r\n)
        buf = b""
        while b"\r\n\r\n" not in buf and len(buf) < 65536:
            chunk = client_sock.recv(4096)
            if not chunk:
                return
            buf += chunk
        if b"\r\n\r\n" not in buf:
            return
        headers_end = buf.index(b"\r\n\r\n") + 4
        headers = buf[:headers_end]
        body = buf[headers_end:]

        # Don't add Proxy-Authorization if already present
        if b"Proxy-Authorization:" not in headers and b"proxy-authorization:" not in headers:
            headers = _add_proxy_auth(headers, username, password)

        upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        upstream.settimeout(60)
        upstream.connect((upstream_host, upstream_port))
        upstream.sendall(headers)
        if body:
            upstream.sendall(body)

        # First line: CONNECT vs normal
        first_line = headers.split(b"\r\n")[0].decode("utf-8", errors="ignore")
        if first_line.upper().startswith("CONNECT "):
            # HTTPS: read upstream response, forward to client, then bidirectional tunnel
            response = b""
            while b"\r\n\r\n" not in response and len(response) < 8192:
                response += upstream.recv(4096)
            client_sock.sendall(response)
            if b"200" not in response.split(b"\r\n")[0]:
                upstream.close()
                client_sock.close()
                return
            # Tunnel both ways
            client_sock.setblocking(False)
            upstream.setblocking(False)
            import select
            while True:
                r, _, _ = select.select([client_sock, upstream], [], [], 60)
                if not r:
                    break
                for s in r:
                    try:
                        data = s.recv(8192)
                        if not data:
                            return
                        (upstream if s is client_sock else client_sock).sendall(data)
                    except (BlockingIOError, BrokenPipeError, ConnectionResetError):
                        return
        else:
            # HTTP: relay response
            while True:
                chunk = upstream.recv(8192)
                if not chunk:
                    break
                try:
                    client_sock.sendall(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
        upstream.close()
    except Exception:
        pass
    finally:
        try:
            client_sock.close()
        except Exception:
            pass


def start_local_proxy(
    upstream_host: str,
    upstream_port: int,
    username: str,
    password: str,
    listen_port: int = 0,
) -> int:
    """
    Start a local proxy on 127.0.0.1 that forwards to upstream with Proxy-Authorization.
    Returns the port the proxy is listening on.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", listen_port))
    port = server.getsockname()[1]
    server.settimeout(1.0)
    server.listen(50)

    def run():
        while True:
            try:
                client, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            t = threading.Thread(
                target=_handle_client,
                args=(client, upstream_host, upstream_port, username, password),
                daemon=True,
            )
            t.start()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return port
