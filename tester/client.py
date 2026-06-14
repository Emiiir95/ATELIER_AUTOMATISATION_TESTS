"""HTTP client wrapper avec timeout, retry simple et mesure de latence."""
import time
import requests


class ApiClient:
    """Wrapper minimaliste autour de requests, avec:

    - timeout strict (par défaut 5s)
    - 1 retry sur 429/5xx ou exception réseau
    - mesure de latence en millisecondes
    """

    def __init__(self, base_url, timeout=5.0, default_headers=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def call(self, method, path, **kwargs):
        """Exécute la requête et retourne (status_code, body_or_text, latency_ms, error)."""
        url = self.base_url + path
        kwargs.setdefault("timeout", self.timeout)

        for attempt in (1, 2):
            start = time.perf_counter()
            try:
                resp = self.session.request(method, url, **kwargs)
                latency_ms = int((time.perf_counter() - start) * 1000)

                # Retry si 429 (rate limit) ou 5xx
                if resp.status_code in (429,) or resp.status_code >= 500:
                    if attempt == 1:
                        time.sleep(1.0)
                        continue

                try:
                    body = resp.json()
                except ValueError:
                    body = resp.text

                return resp.status_code, body, latency_ms, None

            except requests.exceptions.RequestException as exc:
                latency_ms = int((time.perf_counter() - start) * 1000)
                if attempt == 1:
                    time.sleep(1.0)
                    continue
                return None, None, latency_ms, str(exc)

    def get(self, path, **kwargs):
        return self.call("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.call("POST", path, **kwargs)
