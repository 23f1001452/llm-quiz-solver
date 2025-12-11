# ============================================================================
# quiz_solver.py - Async Quiz Solver used by FastAPI
# ============================================================================

import re
import httpx
from urllib.parse import urljoin


BASE = "https://tds-llm-analysis.s-anand.net"


class QuizSolver:

    def __init__(self):
        # Async HTTP client
        self.client = httpx.AsyncClient(timeout=10)

    # ----------------------------------------------------------------------
    async def fetch_page(self, url: str) -> str:
        """GET the quiz step page."""
        full = urljoin(BASE, url)
        r = await self.client.get(full)
        r.raise_for_status()
        return r.text

    # ----------------------------------------------------------------------
    def extract_answer(self, html: str) -> str:
        """
        Extract the answer from the page.
        Supports:
        - <code>ANSWER</code>
        - Answer: XYZ
        - answer = XYZ
        """
        # Try <code>ANSWER</code>
        m = re.search(r"<code>(.*?)</code>", html, re.S)
        if m and m.group(1).strip():
            return m.group(1).strip()

        # Try “Answer: …”
        m = re.search(r"Answer[: ]+</?[^>]*>(.*?)<", html, re.I)
        if m and m.group(1).strip():
            return m.group(1).strip()

        # Try plain text "answer = xyz"
        m = re.search(r"answer\s*=\s*([^\s<]+)", html, re.I)
        if m:
            return m.group(1).strip()

        raise ValueError("Answer not found in page")

    # ----------------------------------------------------------------------
    async def submit(self, url: str, email: str, secret: str, answer: str) -> dict:
        """Always POST JSON to /submit."""
        payload = {
            "email": email,
            "secret": secret,
            "url": url,
            "answer": answer
        }

        r = await self.client.post(f"{BASE}/submit", json=payload)
        r.raise_for_status()
        return r.json()

    # ----------------------------------------------------------------------
    async def solve_step(self, url: str, email: str, secret: str) -> str | None:
        """Fetch → Extract → Submit → Return next URL."""
        html = await self.fetch_page(url)
        answer = self.extract_answer(html)
        resp = await self.submit(url, email, secret, answer)

        if resp.get("correct") and resp.get("next"):
            return resp["next"]
        return None

    # ----------------------------------------------------------------------
    async def solve_quiz_chain(self, start_url: str, email=None, secret=None):
        """
        Main chain solver.
        FastAPI passes email & secret through request model, not via environment.
        """
        if email is None or secret is None:
            # caller did not pass email/secret → raise error
            raise ValueError("Email and secret must be provided")

        url = start_url
        count = 0
        visited = set()

        while url and url not in visited:
            visited.add(url)
            count += 1

            try:
                next_url = await self.solve_step(url, email, secret)
            except Exception as e:
                return {
                    "message": f"Error at step {count}: {str(e)}",
                    "quizzes_solved": count - 1
                }

            if not next_url:
                return {
                    "message": "Final quiz solved.",
                    "quizzes_solved": count
                }

            url = next_url

        return {
            "message": "Reached a repeated URL or stopped.",
            "quizzes_solved": count
        }
