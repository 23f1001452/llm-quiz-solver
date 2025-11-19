# ============================================================================
# Fixed agent/quiz_solver.py - Hardened Quiz Solving Logic
# ============================================================================

import json
import logging
import re
from typing import Dict, Any, Optional
from agent.llm_client import LLMClient
from agent.tools import QuizTools
from agent.prompts import SYSTEM_PROMPT, TASK_PLANNING_PROMPT
import httpx
import os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def clean_code_fences(text: str) -> str:
    """Remove Markdown fenced code blocks and leading language tags."""
    if not text:
        return text
    # Remove ```lang ... ``` or ``` ... ```
    # If multiple code fences exist, prefer the largest JSON-like block
    fences = re.findall(r'```[\s\S]*?```', text)
    if fences:
        # choose fence with largest number of braces inside (likely the JSON)
        best = max(fences, key=lambda f: f.count('{'))
        inner = re.sub(r'^```\w*\n?', '', best)
        inner = re.sub(r'\n?```$', '', inner)
        return inner.strip()

    # Also strip inline backticks if present
    text = text.replace('`', '')
    return text.strip()


def extract_json_string(text: str) -> Optional[str]:
    """Attempt to find the most plausible JSON object inside text."""
    if not text:
        return None
    # First try to find a top-level JSON object
    m = re.search(r'(\{[\s\S]*\})', text)
    if m:
        return m.group(1).strip()

    # Fall back to a looser pattern (arrays included)
    m = re.search(r'(\[[\s\S]*\])', text)
    if m:
        return m.group(1).strip()

    return None


class QuizSolver:
    """
    Hardened quiz solver that uses both HTML extraction and LLM parsing,
    validates LLM outputs, and sanitizes answers before submit.
    """

    def __init__(self):
        self.llm = LLMClient()
        self.tools = QuizTools()
        self.email = os.getenv("STUDENT_EMAIL")
        self.secret = os.getenv("SECRET_KEY")

    async def solve_quiz_chain(self, initial_url: str) -> Dict[str, Any]:
        current_url = initial_url
        quizzes_solved = 0
        max_quizzes = 10  # safety

        while current_url and quizzes_solved < max_quizzes:
            logger.info(f"Solving quiz {quizzes_solved + 1}: {current_url}")
            try:
                result = await self.solve_single_quiz(current_url)
                quizzes_solved += 1
                current_url = result.get("next_url")
                if not current_url:
                    logger.info("No more quizzes in chain")
                    break
            except Exception as e:
                logger.error(f"Error solving quiz: {str(e)}", exc_info=True)
                return {
                    "message": f"Failed at quiz {quizzes_solved + 1}: {str(e)}",
                    "quizzes_solved": quizzes_solved,
                }

        return {
            "message": f"Successfully completed {quizzes_solved} quiz(es)",
            "quizzes_solved": quizzes_solved,
        }

    async def solve_single_quiz(self, quiz_url: str) -> Dict[str, Any]:
        try:
            logger.info(f"Fetching quiz from: {quiz_url}")
            quiz_content = await self.tools.fetch_page(quiz_url)
            logger.info(f"Fetched {len(quiz_content)} characters from quiz page")

            # Prefer deterministic extraction from HTML
            submit_url_from_html = self._extract_submit_url_from_html(quiz_content)

            logger.info("Parsing quiz instructions via LLM...")
            instructions = await self.parse_quiz(quiz_content)
            logger.info(f"Parsed instructions: {instructions}")

            # If HTML provided a submit action, prefer it
            submit_url = None
            if submit_url_from_html:
                submit_url = submit_url_from_html
                logger.info(f"Found submit URL in HTML: {submit_url}")

            # Otherwise, take from LLM instructions (but validate)
            if not submit_url:
                submit_url = instructions.get("submit_url")

            if not submit_url or str(submit_url).lower() == "none":
                raise ValueError(f"No submit_url found in HTML or LLM output: {submit_url}")

            # Validate submit_url doesn't contain nonsense like 'origin + /submit'
            if any(token in str(submit_url).lower() for token in ["origin", "+", "current"]):
                raise ValueError(f"Invalid submit_url returned by LLM: {submit_url}")

            # Convert relative to absolute
            submit_url = urljoin(quiz_url, submit_url)

            logger.info("Executing solution...")
            answer = await self.execute_solution(instructions)
            logger.info(f"Generated raw answer: {answer}")

            logger.info(f"Submitting answer to: {submit_url}")
            result = await self.submit_answer(submit_url, answer)
            return result

        except Exception as e:
            logger.error(f"Error in solve_single_quiz: {str(e)}", exc_info=True)
            raise

    async def parse_quiz(self, html_content: str) -> Dict[str, Any]:
        """
        Use an LLM to parse the quiz page but with strict instructions to not
        invent URLs or make guesses. If possible, the caller should prefer
        HTML-extracted submit URL over the LLM value.
        """
        # Shorten HTML content so we don't exceed context too much
        sample = html_content[:12000]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Parse this quiz page and extract the information.\n\n"
                    "Return ONLY a valid JSON object (no explanation, no markdown) with these keys:\n"
                    "- task: description of what to do\n"
                    "- data_source: URL or description of data to fetch (or \"none\")\n"
                    "- analysis_type: what kind of analysis\n"
                    "- answer_format: expected format (number, string, json, base64, etc.)\n"
                    "- submit_url: EXACT submit endpoint as found in the HTML (e.g. /submit or https://site/submit).\n"
                    "   IMPORTANT: DO NOT GUESS. If the submit URL is not present in the HTML, return \"none\".\n"
                    "- payload_template: sample JSON structure for submission (if available)\n\n"
                    "HTML Content:\n"
                    f"{sample}\n\n"
                    "Response must be pure JSON only, starting with { and ending with }."
                ),
            },
        ]

        response = await self.llm.chat(messages, temperature=0.0)
        response = response.strip()

        # remove code fences if the model wrapped the JSON in them
        response = clean_code_fences(response)

        try:
            parsed = json.loads(response)
            logger.info("Successfully parsed JSON from LLM response")
            return parsed
        except json.JSONDecodeError:
            # Try to extract JSON object from noisy text
            json_str = extract_json_string(response)
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    logger.info("Extracted JSON using fallback regex")
                    return parsed
                except Exception:
                    logger.exception("Fallback JSON extraction failed")

        raise ValueError("Could not parse quiz instructions from LLM response")

    async def execute_solution(self, instructions: Dict[str, Any]) -> Any:
        """
        Execute the required task. Enforce that the LLM returns the answer without
        Markdown code-blocks and in the requested format.
        """
        task = instructions.get("task", "")
        data_source = instructions.get("data_source", "")
        analysis_type = instructions.get("analysis_type", "")
        answer_format = instructions.get("answer_format", "string")

        # Step 1: Fetch data if needed
        data = None
        if data_source and isinstance(data_source, str) and data_source.startswith("http"):
            data = await self.tools.fetch_data(data_source)
        else:
            logger.info("No external data source needed or not a http URL")

        # Step 2: Ask LLM to solve the task with strict formatting instructions
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n"
                    f"Analysis Type: {analysis_type}\n"
                    f"Expected Answer Format: {answer_format}\n\n"
                    "Important instructions:\n"
                    "- Provide ONLY the final answer in the required format. No explanations.\n"
                    "- Do NOT wrap the answer in code fences or backticks. No markdown.\n"
                    "- If the expected format is JSON, return a raw JSON object (not a string).\n"
                    "- If you cannot compute the answer from the provided information, return the string \"none\".\n\n"
                    f"{f'Here is the data: {str(data)[:4000]}' if data else ''}\n\n"
                    "Answer:"
                ),
            },
        ]

        response = await self.llm.chat(messages, temperature=0.0, max_tokens=2000)
        raw = response.strip()

        # Clean fences and extract JSON if needed
        raw = clean_code_fences(raw)

        # Convert to proper type according to answer_format
        if answer_format == "number":
            # extract possible number
            m = re.search(r'[-+]?[0-9]*\.?[0-9]+', raw)
            if m:
                num_str = m.group(0)
                return float(num_str) if '.' in num_str else int(num_str)
            else:
                return raw

        if answer_format == "json":
            # Attempt to extract JSON and parse
            json_str = extract_json_string(raw)
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    return parsed
                except Exception:
                    logger.exception("Failed to parse JSON answer from LLM output")
                    # As a last resort, return the raw cleaned text
                    return raw
            else:
                logger.warning("No JSON found in LLM response for json answer_format")
                return raw

        # default: return cleaned string
        return raw

    def _extract_submit_url_from_html(self, html: str) -> Optional[str]:
        """Attempt to get the form action or script-defined submit URL directly from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Look for <form action>
            form = soup.find("form", action=True)
            if form and form.get("action"):
                return form.get("action").strip()

            # Look for common JS patterns: fetch('.../submit') or fetch(".../submit")
            scripts = "\n".join(s.get_text() for s in soup.find_all("script"))
            m = re.search(r"fetch\(\s*['\"]([^'\"]+/submit)['\"]", scripts)
            if m:
                return m.group(1)

            # Look for a meta tag or link rel that indicates submit
            meta = soup.find("meta", attrs={"name": "submit-url"})
            if meta and meta.get("content"):
                return meta.get("content").strip()

        except Exception:
            logger.exception("Failed to extract submit URL from HTML")

        return None

    async def submit_answer(self, submit_url: str, answer: Any) -> Dict[str, Any]:
        """Submit the answer payload to the quiz endpoint. Accept answer as dict or scalar."""
        payload = {
            "email": self.email,
            "secret": self.secret,
            "answer": answer,
        }

        logger.info(f"Submitting to {submit_url}: {payload}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(submit_url, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Try to surface any helpful error body
                body = None
                try:
                    body = response.json()
                except Exception:
                    body = response.text
                logger.error(f"Submission failed {response.status_code}: {body}")
                raise

            result = response.json()
            logger.info(f"Submission result: {result}")

            return {
                "correct": result.get("correct", False),
                "next_url": result.get("url"),
                "message": result.get("message", ""),
            }
