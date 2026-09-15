"""Bounded JSON requests and process-local single-flight caches. No secret URLs in logs."""
from collections import OrderedDict
from copy import deepcopy
import json
import logging
from threading import RLock
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import urlencode

LOGGER = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    pass


class Cache:
    def __init__(self, failure_ttl=60, clock=monotonic, capacity=256):
        self.entries = OrderedDict()
        self.lock = RLock()
        self.clock, self.failure_ttl, self.capacity = clock, failure_ttl, capacity

    def get(self, key, loader, ttl):
        # Hold the lock through the load: concurrent misses share one fetch, including failures.
        with self.lock:
            entry = self.entries.get(key)
            if entry and entry[0] > self.clock():
                self.entries.move_to_end(key)
                if entry[2]:
                    raise ProviderUnavailable("cached_provider_failure")
                return deepcopy(entry[1])
            try:
                value = loader()
            except Exception:
                self.entries[key] = (self.clock() + self.failure_ttl, None, True)
                self.entries.move_to_end(key)
                self._trim()
                raise ProviderUnavailable("provider_request_failed") from None
            self.entries[key] = (self.clock() + ttl, deepcopy(value), False)
            self.entries.move_to_end(key)
            self._trim()
            return deepcopy(value)

    def _trim(self):
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)


class RateGate:
    def __init__(self):
        self.lock = RLock()
        self.last = None

    def wait(self, interval):
        with self.lock:
            if self.last is not None:
                sleep(max(0, interval - (monotonic() - self.last)))
            self.last = monotonic()


SEC_GATE = RateGate()
FRED_GATE = RateGate()


class JsonClient:
    def __init__(self, settings):
        self.settings = settings

    def get(self, url, *, provider, params=None, user_agent=None):
        gate = SEC_GATE if provider == "sec" else FRED_GATE
        interval = self.settings.outlook_sec_request_interval if provider == "sec" else 0.5
        request = Request(url + ("?" + urlencode(params) if params else ""), headers={
            "User-Agent": user_agent or "TradePilotAI/Outlook", "Accept": "application/json",
        })
        for attempt in range(self.settings.outlook_http_attempts):
            gate.wait(interval)
            try:
                with urlopen(request, timeout=self.settings.outlook_http_timeout) as response:
                    payload = response.read(8 * 1024 * 1024 + 1)
                    if len(payload) > 8 * 1024 * 1024:
                        raise ValueError("payload_too_large")
                    return json.loads(payload)
            except HTTPError as error:
                # Do not retry 403/429; cache/backoff gives the provider breathing room.
                retryable = error.code in (500, 502, 503, 504)
                LOGGER.warning("outlook_request_failed provider=%s status=%s", provider, error.code)
            except Exception as error:
                retryable = isinstance(error, (TimeoutError, OSError))
                LOGGER.warning("outlook_request_failed provider=%s kind=%s", provider, type(error).__name__)
            if not retryable or attempt + 1 == self.settings.outlook_http_attempts:
                raise ProviderUnavailable("provider_request_failed") from None
        raise ProviderUnavailable("provider_request_failed")
