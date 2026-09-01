"""The one place the scraper touches the network. Tests stub `fetch`, so nothing
else in the package can reach out by accident."""

import json
import urllib.error
import urllib.request

USER_AGENT = "jobhunt-scraper/0.1 (+https://github.com/crypticnull/jobhunt)"
TIMEOUT = 20


class HttpError(Exception):
    def __init__(self, url, status=None, reason=""):
        self.url, self.status, self.reason = url, status, reason
        super().__init__(f"{status or 'network'} {reason} <{url}>")


def fetch(url, timeout=TIMEOUT, accept="application/json"):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise HttpError(url, e.code, str(e.reason)) from None
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
