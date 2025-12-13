'''# ====================================================================
# agent/quiz_solver.py
# Hybrid async QuizSolver: LLM-assisted + deterministic handlers
# ====================================================================
import re
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse, urlencode

import httpx

from agent.llm_client import LLMClient
from agent.prompts import SYSTEM_PROMPT, TASK_PLANNING_PROMPT

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Base origin for the TDS platform. Kept as default but will be inferred from URLs too.
DEFAULT_BASE = "https://tds-llm-analysis.s-anand.net"
SUBMIT_PATH = "/submit"


def clean_code_fences(text: str) -> str:
    """Remove surrounding triple-backtick fences or inline backticks."""
    if not isinstance(text, str):
        return text
    # strip fenced blocks if present
    m = re.search(r'```(?:\w*\n)?([\s\S]*?)\n?```', text)
    if m:
        return m.group(1).strip()
    return text.replace("`", "").strip()


def find_origin_from_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme and p.netloc:
        return f"{p.scheme}://{p.netloc}"
    return DEFAULT_BASE


class QuizSolver:
    """
    Hybrid quiz solver that uses LLM to parse tasks and deterministic logic
    for common project2 problems. Designed to be called as:

        solver = QuizSolver()
        result = await solver.solve_quiz_chain(start_url, email=<email>, secret=<secret>)

    Returns a dict: {"message": str, "quizzes_solved": int}
    """

    def __init__(self, timeout: float = 30.0):
        self.llm = LLMClient()
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)

    # ----------------------
    async def fetch_page(self, full_url: str) -> str:
        """Fetch quiz page HTML. full_url may be absolute or relative."""
        # ensure absolute
        if not urlparse(full_url).netloc:
            full_url = urljoin(DEFAULT_BASE, full_url)
        logger.info(f"GET {full_url}")
        r = await self.client.get(full_url)
        r.raise_for_status()
        return r.text

    # ----------------------
    async def parse_quiz_with_llm(self, html: str) -> Dict[str, Any]:
        """
        Ask the LLM to parse the quiz page and return a JSON object describing:
        - task (string)
        - data_source (string or "none")
        - analysis_type
        - answer_format (string)
        - hint (optional)
        - submit_url (or "none")
        - payload_template (if present)
        """
        sample = html[:12000]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Parse the following HTML quiz page and return ONLY a JSON object (no explanation).\n"
                    "Keys (include at least these; use \"none\" when not available):\n"
                    "- task: short description of what to do\n"
                    "- data_source: URL to fetch or 'none'\n"
                    "- analysis_type: what to compute\n"
                    "- answer_format: one of [string, json, number, base64, command]\n"
                    "- submit_url: the endpoint to submit to if present in HTML, otherwise 'none'\n"
                    "- payload_template: example payload structure if visible, otherwise 'none'\n\n"
                    "HTML:\n\n"
                    f"{sample}\n\n"
                    "Return pure JSON only."
                ),
            },
        ]

        logger.info("Asking LLM to parse quiz page...")
        resp = await self.llm.chat(messages, temperature=0.0)
        resp = clean_code_fences(resp)
        try:
            parsed = json.loads(resp)
            logger.info("LLM returned valid JSON parsing.")
            return parsed
        except Exception:
            # fallback: try to extract JSON object from noisy text
            m = re.search(r'(\{[\s\S]*\})', resp)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                    return parsed
                except Exception:
                    logger.exception("Failed to parse JSON from LLM fallback.")
            # final fallback: return minimal structure
            logger.warning("LLM parsing failed; returning minimal inferred structure.")
            return {
                "task": "unknown",
                "data_source": "none",
                "analysis_type": "none",
                "answer_format": "string",
                "submit_url": "none",
                "payload_template": "none"
            }

    # ----------------------
    def _heuristic_detect_uv_get(self, html: str) -> Optional[Dict[str, str]]:
        """
        Detect instructions asking to craft a uv http get command.
        If found, return a small dict with 'endpoint_template' (may include ?email=<your email>).
        """
        # look for "uv http get" or "uv http get" mentions in text
        if re.search(r"\buv\s+http\s+get\b", html, re.I):
            # try to find the path mentioned close to it, like /project2/uv.json?email=<your email>
            m = re.search(r"(/[\w\-/.]+(?:\?[^<\s'\"]*)?)", html)
            endpoint = None
            if m:
                endpoint = m.group(1)
            return {"type": "uv_get", "endpoint": endpoint or "/project2/uv.json?email=<your email>"}
        return None

    # ----------------------
    def _build_uv_command(self, origin: str, endpoint_template: str, email: str) -> str:
        """
        Construct the exact uv http get command string per instructions.
        endpoint_template may contain '?email=<your email>' or just be a path.
        """
        # if endpoint_template is a full URL, respect it; else join with origin
        if endpoint_template.startswith("http://") or endpoint_template.startswith("https://"):
            url = endpoint_template.replace("<your email>", email).replace("&lt;your email&gt;", email)
        else:
            # ensure ?email fragment exists if not present
            ep = endpoint_template.replace("<your email>", email).replace("&lt;your email&gt;", email)
            # If template does not include scheme/host, join with origin
            url = urljoin(origin, ep)
        # build command with header
        cmd = f'uv http get {url} -H "Accept: application/json"'
        return cmd

    # ----------------------
    async def compute_answer(self, page_url: str, html: str, email: str, parsed_instructions: Optional[Dict[str, Any]] = None) -> Any:
        """
        Hybrid function: try deterministic handlers first (fast), then fall back to LLM generation.
        Returns the final answer (string, dict for json, number, etc).
        """
        origin = find_origin_from_url(page_url)

        # 1) Heuristic: uv http get command
        uv = self._heuristic_detect_uv_get(html)
        if uv:
            ep = uv.get("endpoint") or "/project2/uv.json?email=<your email>"
            cmd = self._build_uv_command(origin, ep, email)
            logger.info(f"Built uv command via heuristic: {cmd}")
            return cmd

        # 2) If parsed_instructions explicitly request a command/GET, try to construct
        if parsed_instructions:
            fmt = str(parsed_instructions.get("answer_format", "")).lower()
            task = parsed_instructions.get("task", "")
            data_src = parsed_instructions.get("data_source", "")
            # If LLM says data_source is an http URL that includes <your email>, substitute
            if data_src and isinstance(data_src, str) and data_src.startswith("http"):
                ds = data_src.replace("<your email>", email).replace("&lt;your email&gt;", email)
                if "uv" in task.lower() or "http get" in task.lower():
                    cmd = f'uv http get {ds} -H "Accept: application/json"'
                    logger.info("Built uv command from parsed_instructions")
                    return cmd

        # 3) LLM fallback: ask it to compute the exact answer in the specified format
        logger.info("Using LLM to compute the answer (fallback).")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "You are given a quiz page HTML and must return ONLY the final answer in the exact format required.\n\n"
                    "HTML:\n\n"
                    f"{html[:12000]}\n\n"
                    f"Context:\n - page_url: {page_url}\n - email: {email}\n\n"
                    "Return ONLY the answer (no explanation, no markdown, no code fences)."
                )
            }
        ]
        raw = await self.llm.chat(messages, temperature=0.0)
        raw = clean_code_fences(raw)
        return raw

    # ----------------------
    async def submit_answer(self, quiz_page_url: str, email: str, secret: str, answer: Any) -> Dict[str, Any]:
        """
        Always POST to /submit on the platform with payload:
            { email, secret, url, answer }
        """
        origin = find_origin_from_url(quiz_page_url)
        submit_url = urljoin(origin, SUBMIT_PATH)
        payload = {
            "email": email,
            "secret": secret,
            "url": quiz_page_url,
            "answer": answer
        }

        preview = {
    "email": email,
    "url": quiz_page_url,
    "answer": (
        str(answer)[:80] + "..."
        if isinstance(answer, str) and len(answer) > 80
        else answer
    ),
}
        logger.info(f"POST {submit_url} payload={preview}")
        r = await self.client.post(submit_url, json=payload)
        try:
            r.raise_for_status()
        except Exception as e:
            # try to include body for debugging
            body = None
            try:
                body = r.json()
            except Exception:
                body = r.text
            logger.error(f"Submit failed {r.status_code}: {body}")
            raise

        j = r.json()
        logger.info(f"Submit response: {j}")
        # Normalize keys: some endpoints return 'url' or 'next'
        return {
            "correct": j.get("correct", False),
            "next_url": j.get("url") or j.get("next") or j.get("next_url"),
            "raw": j
        }

    # ----------------------
    async def solve_single_quiz(self, page_url: str, email: str, secret: str) -> Dict[str, Any]:
        """
        Solve one quiz page: fetch, parse, compute answer, submit.
        Returns dict with keys: correct (bool), next_url (str|None), raw (response JSON)
        """
        logger.info(f"Solving single quiz: {page_url}")

        html = await self.fetch_page(page_url)

        # first attempt: quick deterministic heuristic
        try:
            answer = await self.compute_answer(page_url, html, email)
        except Exception as e:
            logger.exception("Heuristic compute failed, will try LLM parsing.")
            answer = None

        # if heuristics didn't result in answer, ask LLM to parse instructions then compute
        if answer is None:
            parsed = await self.parse_quiz_with_llm(html)
            try:
                answer = await self.compute_answer(page_url, html, email, parsed_instructions=parsed)
            except Exception:
                logger.exception("Compute from parsed instructions failed; will fallback to LLM generation.")
                # LLM fallback to generate final answer explicitly
                answer = await self.compute_answer(page_url, html, email=None, parsed_instructions=None)

        # final sanity: string-ify JSON answers if any
        if isinstance(answer, dict) or isinstance(answer, list):
            answer_payload = answer
        else:
            # ensure stripped string
            answer_payload = str(answer).strip()

        submit_result = await self.submit_answer(page_url, email, secret, answer_payload)
        return submit_result

    # ----------------------
    async def solve_quiz_chain(self, start_url: str, email: Optional[str] = None, secret: Optional[str] = None):
        """
        Main loop: iteratively solve pages until no next_url is returned or a repeat is detected.
        Returns {"message": str, "quizzes_solved": int}
        """
        if not email or not secret:
            raise ValueError("Email and secret must be provided to solve_quiz_chain")

        # normalize start_url to absolute or path as passed-through
        current_url = start_url
        solved = 0
        visited = set()
        max_steps = 40

        while current_url and solved < max_steps:
            if current_url in visited:
                logger.warning("Encountered repeated URL; stopping to avoid loops.")
                return {"message": "Reached repeated URL; stopping.", "quizzes_solved": solved}
            visited.add(current_url)

            try:
                res = await self.solve_single_quiz(current_url, email, secret)
            except Exception as e:
                logger.exception("Error during solving step.")
                return {"message": f"Failed at step {solved+1}: {str(e)}", "quizzes_solved": solved}

            solved += 1

            next_url = res.get("next_url")
            # sometimes next_url may be absolute or relative; leave it as returned
            if not next_url:
                # chain ended
                return {"message": "Final quiz solved.", "quizzes_solved": solved}
            logger.info(f"Moving to next URL: {next_url}")
            current_url = next_url

        return {"message": f"Stopped after {solved} steps (max reached?).", "quizzes_solved": solved}

    # ----------------------
    async def close(self):
        await self.client.aclose() '''

# ====================================================================
# agent/quiz_solver.py
# ====================================================================
import re
import json
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import httpx

from agent.llm_client import LLMClient
from agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_BASE = "https://tds-llm-analysis.s-anand.net"
SUBMIT_PATH = "/submit"


def clean_code_fences(text: str) -> str:
    if not isinstance(text, str):
        return text
    m = re.search(r"```(?:\w*\n)?([\s\S]*?)```", text)
    return m.group(1).strip() if m else text.replace("`", "").strip()


def find_origin_from_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else DEFAULT_BASE


class QuizSolver:
    def __init__(self, timeout: float = 30.0):
        self.llm = LLMClient()
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch_page(self, url: str) -> str:
        if not urlparse(url).netloc:
            url = urljoin(DEFAULT_BASE, url)
        r = await self.client.get(url)
        r.raise_for_status()
        return r.text

    # ---------- Heuristic for project2-uv ----------
    def _build_uv_command(self, origin: str, email: str) -> str:
        url = f"{origin}/project2/uv.json?email={email}"
        return f'uv http get {url} -H "Accept: application/json"'

    async def compute_answer(self, page_url: str, html: str, email: str) -> Any:
        if re.search(r"\buv\s+http\s+get\b", html, re.I):
            origin = find_origin_from_url(page_url)
            return self._build_uv_command(origin, email)

        # fallback → LLM
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Return ONLY the final answer in the required format.\n\n"
                    f"HTML:\n{html[:12000]}"
                ),
            },
        ]
        raw = await self.llm.chat(messages, temperature=0.0)
        return clean_code_fences(raw)

    async def submit_answer(
        self, quiz_page_url: str, email: str, secret: str, answer: Any
    ) -> Dict[str, Any]:

        origin = find_origin_from_url(quiz_page_url)
        submit_url = urljoin(origin, SUBMIT_PATH)

        payload = {
            "email": email,
            "secret": secret,
            "url": quiz_page_url,
            "answer": answer,
        }

        # ✅ SAFE LOGGING (no f-string dict interpolation)
        logger.info(
            "POST %s | email=%s | url=%s | answer_preview=%s",
            submit_url,
            email,
            quiz_page_url,
            str(answer)[:80],
        )

        r = await self.client.post(submit_url, json=payload)
        r.raise_for_status()
        j = r.json()

        return {
            "correct": j.get("correct", False),
            "next_url": j.get("url") or j.get("next") or j.get("next_url"),
            "raw": j,
        }

    async def solve_single_quiz(self, url: str, email: str, secret: str):
        html = await self.fetch_page(url)
        answer = await self.compute_answer(url, html, email)
        return await self.submit_answer(url, email, secret, str(answer).strip())

    async def solve_quiz_chain(self, start_url: str, email: str, secret: str):
        current = start_url
        visited = set()
        solved = 0

        while current:
            if current in visited:
                return {"message": "Loop detected", "quizzes_solved": solved}

            visited.add(current)
            try:
                res = await self.solve_single_quiz(current, email, secret)
            except Exception as e:
                return {"message": f"Failed at step {solved+1}: {e}", "quizzes_solved": solved}

            solved += 1
            current = res.get("next_url")

            if not current:
                return {"message": "Final quiz solved.", "quizzes_solved": solved}

        return {"message": "Done", "quizzes_solved": solved}

    async def close(self):
        await self.client.aclose()
