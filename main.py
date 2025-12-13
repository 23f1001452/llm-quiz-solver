# ============================================================================
# main.py - FastAPI Application Entry Point
# ============================================================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
import os
from dotenv import load_dotenv
import asyncio
from agent.quiz_solver import QuizSolver
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(title="LLM Quiz Solver", version="1.0.0")

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Add this after app creation
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return 400 for invalid JSON/validation errors"""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid JSON or missing required fields"}
    )

# Configuration
STUDENT_EMAIL = os.getenv("STUDENT_EMAIL")
SECRET_KEY = os.getenv("SECRET_KEY")
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "180"))


class QuizRequest(BaseModel):
    email: EmailStr
    secret: str
    url: str


class QuizResponse(BaseModel):
    status: str
    message: str
    quizzes_solved: int = 0


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "LLM Quiz Solver",
        "version": "1.0.0"
    }


@app.post("/quiz")
async def solve_quiz(request: QuizRequest):
    """
    Main endpoint to receive and solve quiz tasks
    """
    logger.info(f"Received quiz request for URL: {request.url}")
    
    # Verify credentials
    if request.email != STUDENT_EMAIL or request.secret != SECRET_KEY:
        logger.warning(f"Authentication failed for email: {request.email}")
        raise HTTPException(status_code=403, detail="Invalid credentials")
    
    try:
        # Initialize quiz solver
        solver = QuizSolver()
        
        # Solve quiz with timeout
        solver = QuizSolver()
        result = await asyncio.wait_for(
    solver.solve_quiz_chain(request.url, email=request.email, secret=request.secret),
    timeout=TIMEOUT_SECONDS
)
        await solver.close()

        
        logger.info(f"Successfully solved {result['quizzes_solved']} quiz(es)")
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": result["message"],
                "quizzes_solved": result["quizzes_solved"]
            }
        )
        
    except asyncio.TimeoutError:
        logger.error("Quiz solving timed out")
        raise HTTPException(
            status_code=408,
            detail=f"Quiz solving exceeded {TIMEOUT_SECONDS} seconds timeout"
        )
    except Exception as e:
        logger.error(f"Error solving quiz: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error solving quiz: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"}
    )