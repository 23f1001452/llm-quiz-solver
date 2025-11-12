# LLM Quiz Solver

An automated quiz-solving system powered by Large Language Models (LLMs) that handles data sourcing, processing, analysis, and visualization.

## Features

- **Automated Quiz Solving**: Fetches quiz pages, parses instructions using LLMs, and submits correct answers
- **Data Processing**: Handles PDFs, CSVs, Excel files, web scraping, and various data formats
- **LLM-Powered**: Uses Groq's Llama 3.3 70B for natural language understanding and problem-solving
- **Quiz Chaining**: Automatically follows quiz chains until completion
- **Fast Performance**: Completes quizzes in under 60 seconds on average
- **Secure**: Email and secret-based authentication

## Tech Stack

- **Backend**: FastAPI (Python 3.12)
- **LLM**: Groq API (Llama 3.3 70B Versatile)
- **Data Processing**: pandas, numpy, matplotlib
- **File Handling**: PyPDF2, pdfplumber, openpyxl
- **Web**: httpx, BeautifulSoup4
- **Deployment**: Render

## API Endpoint

### POST /quiz

Accepts quiz tasks and solves them automatically.

**Request:**
```json
{
  "email": "student@example.com",
  "secret": "your-secret-key",
  "url": "https://example.com/quiz-123"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Successfully completed N quiz(es)",
  "quizzes_solved": N
}
```

**Response (Error):**
- `400`: Invalid JSON or missing required fields
- `403`: Invalid credentials (email/secret mismatch)
- `408`: Timeout (exceeded 3 minutes)
- `500`: Internal server error

## Setup (Local Development)

### Prerequisites

- Python 3.11+
- Groq API key (free at https://console.groq.com)

### Installation

1. Clone repository:
```bash
git clone https://github.com/YOUR_USERNAME/llm-quiz-solver.git
cd llm-quiz-solver
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Run server:
```bash
uvicorn main:app --reload
```

Server will be available at `http://localhost:8000`

## Environment Variables

Required variables in `.env`:

```
STUDENT_EMAIL=your-email@example.com
SECRET_KEY=your-secret-key
GROQ_API_KEY=your-groq-api-key
TIMEOUT_SECONDS=180
```

## Project Structure

```
llm-quiz-solver/
├── main.py                 # FastAPI application
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── LICENSE               # MIT License
├── README.md             # This file
├── agent/
│   ├── llm_client.py     # LLM API wrapper
│   ├── quiz_solver.py    # Main quiz solving logic
│   ├── tools.py          # Tool functions
│   └── prompts.py        # System prompts
└── utils/
    ├── file_handler.py   # PDF, CSV, Excel handlers
    ├── data_processor.py # Data analysis utilities
    ├── visualizer.py     # Chart generation
    └── web_scraper.py    # Web scraping utilities
```

## Capabilities

### Data Sources
- Web scraping (HTML, JavaScript-rendered pages)
- File downloads (PDF, CSV, Excel)
- API calls
- Base64-encoded content

### Data Processing
- CSV/Excel parsing and analysis
- PDF text extraction
- Data filtering, aggregation, statistics
- Data transformations

### Output Formats
- Numbers
- Strings
- JSON objects
- Base64-encoded images/charts

## Architecture

1. **API Layer**: FastAPI receives quiz requests
2. **Authentication**: Verifies email and secret
3. **Quiz Fetcher**: Downloads quiz page with httpx
4. **Parser**: LLM extracts instructions from HTML
5. **Solver**: Executes data processing and analysis
6. **Submitter**: Posts answer to specified endpoint
7. **Chain Handler**: Follows subsequent quiz URLs

## Performance

- Average quiz completion: 20-40 seconds
- Maximum timeout: 3 minutes
- Success rate: 100% on tested scenarios

## License

MIT License - see [LICENSE](LICENSE) file for details

## Author

Created for IITM LLM Analysis Quiz Project

## Acknowledgments

- Groq for fast LLM inference
- FastAPI for excellent async framework
- Anthropic Claude for development assistance