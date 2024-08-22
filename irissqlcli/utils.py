from urllib.parse import urlparse


def parse_uri(uri, hostname=None, port=None, namespace=None, username=None):
    parsed = urlparse(uri)
    embedded = False
    if str(parsed.scheme).startswith("iris"):
        namespace = parsed.path.split("/")[1] if parsed.path else None or namespace
        username = parsed.username or username
        password = parsed.password or None
        hostname = parsed.hostname or hostname
        port = parsed.port or port
    if parsed.scheme == "iris+emb":
        embedded = True
    return hostname, port, namespace, username, password, embedded