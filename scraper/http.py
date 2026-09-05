"""The one place the scraper touches the network. Tests stub `fetch`, so nothing
else in the package can reach out by accident."""

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "jobhunt-scraper/0.1 (+https://github.com/crypticnull/jobhunt)"
TIMEOUT = 20


class HttpError(Exception):
    def __init__(self, url, status=None, reason=""):
        self.url, self.status, self.reason = url, status, reason
        super().__init__(f"{status or 'network'} {reason} <{url}>")


RETRY_STATUSES = (429, 500, 502, 503, 504)
BACKOFF = (2, 8, 30)  # seconds, then give up
MIN_GAP = 1.0  # seconds between two requests to one host
_last = {}
_sleep = time.sleep


def _retry_after(headers, fallback):
    try:
        v = float((headers or {}).get("Retry-After", ""))
        return v if 0 < v <= 120 else fallback
    except ValueError:
        return fallback


def _pace(url):
    host = urllib.parse.urlsplit(url).hostname or url
    wait = _last.get(host, 0) + MIN_GAP - time.monotonic()
    if wait > 0:
        _sleep(wait)
    _last[host] = time.monotonic()


def fetch(url, timeout=TIMEOUT, accept="application/json"):
    """One request, with the manners an unattended poller needs: at least a
    second between requests to one host, and a 429 or a 5xx retried three
    times with backoff, honouring Retry-After. Workable returned 429 on four
    boards every night for a week before this existed, and the seed import
    was probing the same host with slug guesses minutes before."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(len(BACKOFF) + 1):
        _pace(url)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in RETRY_STATUSES and attempt < len(BACKOFF):
                _sleep(_retry_after(e.headers, BACKOFF[attempt]))
                continue
            raise HttpError(url, e.code, str(e.reason)) from None
        except http.client.HTTPException as e:
            raise HttpError(url, None, f"{type(e).__name__}: {e}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise HttpError(url, None, str(e)) from None


def get_json(url, timeout=TIMEOUT):
    status, body = fetch(url, timeout)
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise HttpError(url, status, f"not JSON: {e}") from None


def get_text(url, timeout=TIMEOUT):
    return fetch(url, timeout, accept="text/html,*/*")[1]
