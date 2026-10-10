from urllib.parse import urlsplit


def host_only(url: str) -> str:
    """hostname:port with any embedded credentials stripped, for logging -
    never print a connection URL with a password in it.
    """
    parts = urlsplit(url)
    return f"{parts.hostname}:{parts.port}"
