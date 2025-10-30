# LLM Quiz Solver

Automated quiz solver using LLMs for data sourcing, analysis, and visualization.

## Setup

1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Install Playwright browsers: `playwright install chromium`
6. Copy `.env.example` to `.env` and fill in your credentials
7. Run: `uvicorn main:app --reload`

## API Endpoint

POST `/quiz`
```json
{
  "email": "student@example.com",
  "secret": "your-secret",
  "url": "https://example.com/quiz-123"
}
```

## Deployment

Deploy to Render using `render.yaml` configuration.

## Testing

Run mock quiz: `python tests/test_api.py`