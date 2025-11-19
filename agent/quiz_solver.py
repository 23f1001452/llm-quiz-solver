# ============================================================================
# agent/quiz_solver.py - Main Quiz Solving Logic
# ============================================================================

import json
import logging
from typing import Dict, Any, Optional
from agent.llm_client import LLMClient
from agent.tools import QuizTools
from agent.prompts import SYSTEM_PROMPT, TASK_PLANNING_PROMPT
import httpx
import os

logger = logging.getLogger(__name__)


class QuizSolver:
    """
    Main quiz solver that orchestrates the entire process
    """
    
    def __init__(self):
        self.llm = LLMClient()
        self.tools = QuizTools()
        self.email = os.getenv("STUDENT_EMAIL")
        self.secret = os.getenv("SECRET_KEY")
    
    async def solve_quiz_chain(self, initial_url: str) -> Dict[str, Any]:
        """
        Solve a chain of quizzes starting from initial_url
        
        Returns:
            dict: Summary of results
        """
        current_url = initial_url
        quizzes_solved = 0
        max_quizzes = 10  # Safety limit
        
        while current_url and quizzes_solved < max_quizzes:
            logger.info(f"Solving quiz {quizzes_solved + 1}: {current_url}")
            
            try:
                # Solve single quiz
                result = await self.solve_single_quiz(current_url)
                quizzes_solved += 1
                
                # Check if there's another quiz
                current_url = result.get("next_url")
                
                if not current_url:
                    logger.info("No more quizzes in chain")
                    break
                    
            except Exception as e:
                logger.error(f"Error solving quiz: {str(e)}", exc_info=True)
                return {
                    "message": f"Failed at quiz {quizzes_solved + 1}: {str(e)}",
                    "quizzes_solved": quizzes_solved
                }
        
        return {
            "message": f"Successfully completed {quizzes_solved} quiz(es)",
            "quizzes_solved": quizzes_solved
        }
    
    async def solve_single_quiz(self, quiz_url: str) -> Dict[str, Any]:
        """
        Solve a single quiz
        
        Steps:
        1. Fetch and render the quiz page
        2. Extract quiz instructions
        3. Plan solution approach
        4. Execute solution
        5. Submit answer
        6. Return result with potential next URL
        """
        try:
            logger.info(f"Fetching quiz from: {quiz_url}")
            
            # Step 1: Fetch quiz page
            quiz_content = await self.tools.fetch_page(quiz_url)
            logger.info(f"Fetched {len(quiz_content)} characters from quiz page")
            
            # Step 2: Parse quiz instructions
            logger.info("Parsing quiz instructions...")
            instructions = await self.parse_quiz(quiz_content)
            logger.info(f"Parsed instructions: {instructions}")
            
            # Step 3: Plan and execute solution
            logger.info("Executing solution...")
            answer = await self.execute_solution(instructions)
            logger.info(f"Generated answer: {answer}")
            
            # Step 4: Submit answer
            submit_url = instructions.get("submit_url")
            if not submit_url or submit_url.lower() == "none":
                raise ValueError(f"LLM returned invalid submit_url: {submit_url}")
            if "origin" in submit_url or "+" in submit_url:
                raise ValueError(f"Invalid submit_url guessed by LLM: {submit_url}")
            from urllib.parse import urljoin

            # Convert relative submit URL to absolute
            submit_url = urljoin(quiz_url, submit_url)

            
            logger.info(f"Submitting answer to: {submit_url}")
            result = await self.submit_answer(submit_url, answer)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in solve_single_quiz: {str(e)}", exc_info=True)
            raise
    
    async def parse_quiz(self, html_content: str) -> Dict[str, Any]:
        """
        Use LLM to parse quiz instructions from HTML
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""
Parse this quiz page and extract the information.

HTML Content:
{html_content[:8000]}

Return ONLY a valid JSON object (no explanation, no markdown, no extra text) with these keys:
- task: description of what to do
- data_source: URL or description of data to fetch (or "none" if not needed)
- analysis_type: what kind of analysis (sum, filter, visualization, etc.)
- answer_format: expected format (number, string, json, base64, etc.)
- submit_url: EXACTLY the value found in the HTML form/action or API script.
  DO NOT guess. DO NOT invent text like "origin + /submit".
  If submit URL is relative (e.g. "/submit"), return it exactly as-is.
  If not present in HTML, return "none".
- payload_template: the JSON structure for submission

Response must be pure JSON only, starting with {{ and ending with }}.
"""}
        ]
        
        response = await self.llm.chat(messages, temperature=0.0)
        
        try:
            # Try to extract JSON from response
            # Handle markdown code blocks
            response = response.strip()
            
            # Remove markdown code block markers
            if response.startswith('```'):
                # Remove ```json or ``` at start
                response = response.split('\n', 1)[1] if '\n' in response else response[3:]
            if response.endswith('```'):
                response = response.rsplit('\n', 1)[0] if '\n' in response else response[:-3]
            
            # Find JSON object boundaries
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")
            
            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)
            
            logger.info(f"Successfully parsed quiz instructions")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Attempted to parse: {json_str[:500]}")
            
            # Try to extract JSON more aggressively
            try:
                # Look for the last complete JSON object
                import re
                json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
                if json_objects:
                    # Try each found JSON object
                    for json_obj in reversed(json_objects):
                        try:
                            parsed = json.loads(json_obj)
                            if 'task' in parsed and 'submit_url' in parsed:
                                logger.info("Extracted JSON using regex fallback")
                                return parsed
                        except:
                            continue
            except Exception as e2:
                logger.error(f"Regex extraction failed: {str(e2)}")
            
            raise ValueError("Could not parse quiz instructions")
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {response[:500]}")
            raise
    
    async def execute_solution(self, instructions: Dict[str, Any]) -> Any:
        """
        Execute the solution based on parsed instructions
        """
        task = instructions.get("task", "")
        data_source = instructions.get("data_source", "")
        analysis_type = instructions.get("analysis_type", "")
        answer_format = instructions.get("answer_format", "string")
        
        # Step 1: Fetch data if needed
        data = None
        if data_source:
            if data_source.startswith("http"):
                # Download file or fetch API
                data = await self.tools.fetch_data(data_source)
            else:
                logger.info("No external data source needed")
        
        # Step 2: Use LLM to solve the task
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"""
Task: {task}
Analysis Type: {analysis_type}
Expected Answer Format: {answer_format}

{f"Data: {str(data)[:4000]}" if data else ""}

Solve this task and provide ONLY the final answer in the required format.
Do not include explanations, just the answer value.

If the answer should be:
- A number: return just the number
- A string: return just the string (no quotes unless part of the answer)
- JSON: return valid JSON
- base64: return the base64 string

Answer:
"""}
        ]
        
        response = await self.llm.chat(messages, temperature=0.0, max_tokens=2000)
        
        # Clean up response
        answer = response.strip()
        
        # Convert to appropriate type
        if answer_format == "number":
            try:
                answer = float(answer) if "." in answer else int(answer)
            except:
                pass
        elif answer_format == "json":
            try:
                answer = json.loads(answer)
            except:
                pass
        
        return answer
    
    async def submit_answer(
        self,
        submit_url: str,
        answer: Any
    ) -> Dict[str, Any]:
        """
        Submit answer to the quiz endpoint
        """
        payload = {
            "email": self.email,
            "secret": self.secret,
            "answer": answer
        }
        
        logger.info(f"Submitting to {submit_url}: {payload}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(submit_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"Submission result: {result}")
            
            return {
                "correct": result.get("correct", False),
                "next_url": result.get("url"),
                "message": result.get("message", "")
            }