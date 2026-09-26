"""Polite HTTP: one pacing clock per host, bounded retries, and a bot challenge treated as a stop, never as something to get past."""

import time
from urllib.parse import urlsplit

import httpx

from . import GITHUB, __version__

USER_AGENT = f"us-local-laws/{__version__} (+{GITHUB})"
INTERVAL = 1.0
# Hosts whose robots.txt asks for a longer wait between requests than INTERVAL: www.fema.gov gives "Crawl-delay: 15" for every user agent.
HOST_INTERVALS = {"www.fema.gov": 15.0}
RETRYABLE = (408, 429, 500, 502, 503, 504)


class Blocked(RuntimeError):
    """A bot challenge (for example Cloudflare's) answered instead of the resource."""


class Unavailable(RuntimeError):
    """Server errors, rate limits or network failures outlasted every retry."""


class Fetcher:
    def __init__(self, interval=INTERVAL, max_retries=4, timeout=120.0, transport=None, sleep=time.sleep):
        self.interval = interval
        self.max_retries = max_retries
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True, transport=transport)
        self.sleep = sleep
        self._next_at = {}
        self.requests = 0

    def _pace(self, host):
        now = time.monotonic()
        at = max(now, self._next_at.get(host, 0.0))
        self._next_at[host] = at + max(self.interval, HOST_INTERVALS.get(host, 0.0))
        if at > now:
            self.sleep(at - now)

    def get(self, url):
        """The response body. 404 and other client errors raise httpx.HTTPStatusError; a challenge raises Blocked."""
        host = urlsplit(url).hostname or ""
        last, delay = None, 0
        for attempt in range(self.max_retries + 1):
            if attempt:
                self.sleep(delay)
            self._pace(host)
            self.requests += 1
            try:
                response = self.client.get(url)
            except httpx.TransportError as error:
                last, delay = Unavailable(f"{type(error).__name__} from {host}"), min(300, 2 ** (attempt + 2))
                continue
            if response.status_code == 403 and (response.headers.get("cf-mitigated") == "challenge" or b"Just a moment" in response.content[:4096]):
                raise Blocked(f"bot challenge at {host}{urlsplit(url).path}")
            if response.status_code in RETRYABLE:
                retry_after = response.headers.get("Retry-After", "")
                last = Unavailable(f"HTTP {response.status_code} from {host}{urlsplit(url).path}")
                delay = min(600, int(retry_after)) if retry_after.isdigit() else min(300, 2 ** (attempt + 2))
                continue
            response.raise_for_status()
            return response.content
        raise last

    def close(self):
        self.client.close()
