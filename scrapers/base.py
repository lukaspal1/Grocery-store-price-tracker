# scrapers/base.py
import time
import logging
from urllib.robotparser import RobotFileParser
import httpx

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class CompliantScraper:
    USER_AGENT = "PortfolioPriceTracker/1.0 (+https://github.com/lukaspal1)"
    DELAY_SECONDS = 2.0

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.robots = RobotFileParser()
        self.client = httpx.Client(
            headers={"User-Agent": self.USER_AGENT},
            timeout=20,
            follow_redirects=True,
        )
        self._load_robots()

    def _load_robots(self):
        """Fetch robots.txt with httpx and feed it to RobotFileParser.

        We don't use RobotFileParser.read() because urllib's SSL handling
        is broken on Python 3.13+ on Windows, and because read() silently
        sets disallow_all=True on failure, which is ambiguous.
        """
        robots_url = f"{self.base_url}/robots.txt"
        try:
            r = self.client.get(robots_url)
        except httpx.HTTPError as e:
            log.warning(f"Could not fetch robots.txt for {self.base_url}: {e}")
            log.warning("Defaulting to ALLOW ALL — override if you want stricter behavior")
            self.robots.allow_all = True
            return

        if r.status_code == 200:
            self.robots.parse(r.text.splitlines())
            log.info(f"Loaded robots.txt for {self.base_url}")
        elif r.status_code in (401, 403):
            self.robots.disallow_all = True
            log.warning(f"robots.txt returned {r.status_code} — disallowing all")
        elif 400 <= r.status_code < 500:
            self.robots.allow_all = True
            log.info(f"robots.txt returned {r.status_code} — allowing all (no rules exist)")
        else:
            self.robots.allow_all = True
            log.warning(f"robots.txt returned {r.status_code} — allowing all")

    def can_fetch(self, url: str) -> bool:
        allowed = self.robots.can_fetch(self.USER_AGENT, url)
        if not allowed:
            log.warning(f"robots.txt disallows: {url}")
        return allowed

    def get(self, url: str, **kwargs):
        if not self.can_fetch(url):
            return None
        time.sleep(self.DELAY_SECONDS)
        try:
            r = self.client.get(url, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPError as e:
            log.error(f"Fetch failed for {url}: {e}")
            return None

    def post(self, url: str, **kwargs):
        if not self.can_fetch(url):
            return None
        time.sleep(self.DELAY_SECONDS)
        try:
            r = self.client.post(url, **kwargs)
            r.raise_for_status()
            return r
        except httpx.HTTPError as e:
            log.error(f"POST failed for {url}: {e}")
            return None

    def close(self):
        self.client.close()