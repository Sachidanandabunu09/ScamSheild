"""Bounded, in-memory rate limiter for this single-process demo deployment."""

import time
from collections import OrderedDict
from threading import Lock


class RateLimiter:
    def __init__(self, requests=30, window=60, max_clients=10000):
        self.requests = requests
        self.window = window
        self.max_clients = max_clients
        self.clients = OrderedDict()
        self.lock = Lock()

    def allow(self, client):
        now = time.monotonic()
        with self.lock:
            # Entries stay in insertion order, with fixed window start times.
            while self.clients and next(iter(self.clients.values()))[0] <= now - self.window:
                self.clients.popitem(last=False)
            if client not in self.clients:
                if len(self.clients) >= self.max_clients:
                    return False
                self.clients[client] = [now, 0]
            entry = self.clients[client]
            if entry[1] >= self.requests:
                return False
            entry[1] += 1
            return True
