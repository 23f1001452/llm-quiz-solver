# ============================================================================
# agent/tools.py - Tool Functions
# ============================================================================

import logging
from typing import Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup
import pandas as pd
import io
import base64
from utils.file_handler import FileHandler
from utils.data_processor import DataProcessor

logger = logging.getLogger(__name__)


class QuizTools:
    """
    Tools for fetching, processing, and analyzing data
    """
    
    def __init__(self):
        self.file_handler = FileHandler()
        self.data_processor = DataProcessor()
    
    async def fetch_page(self, url: str) -> str:
        """
        Fetch and render a web page (handles JavaScript)
        Windows-compatible: uses httpx + manual JS execution
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
            
            # Check if page has base64 encoded content that needs decoding
            if 'atob(' in content or 'btoa(' in content:
                logger.info("Detected base64 encoded content, decoding...")
                content = self._decode_atob_content(content)
            
            return content
    
    def _decode_atob_content(self, html: str) -> str:
        """
        Decode base64 content from atob() JavaScript calls
        """
        import re
        import base64
        
        # Find atob() calls
        pattern = r'atob\([\'"`]([A-Za-z0-9+/=]+)[\'"`]\)'
        matches = re.findall(pattern, html)
        
        decoded_html = html
        for encoded in matches:
            try:
                decoded = base64.b64decode(encoded).decode('utf-8')
                # Replace the atob call with decoded content
                decoded_html = decoded_html.replace(f'atob("{encoded}")', f'`{decoded}`')
                decoded_html = decoded_html.replace(f"atob('{encoded}')", f'`{decoded}`')
                decoded_html = decoded_html.replace(f'atob(`{encoded}`)', f'`{decoded}`')
            except Exception as e:
                logger.warning(f"Failed to decode base64: {str(e)}")
        
        return decoded_html
    
    async def fetch_data(self, url: str) -> Any:
        """
        Fetch data from URL (file download or API call)
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            
            # Handle different content types
            if "json" in content_type:
                return response.json()
            elif "pdf" in content_type:
                return await self.file_handler.process_pdf(response.content)
            elif "csv" in content_type or "text/plain" in content_type:
                return await self.file_handler.process_csv(response.content)
            elif "excel" in content_type or "spreadsheet" in content_type:
                return await self.file_handler.process_excel(response.content)
            else:
                # Return as text
                return response.text
    
    def parse_html(self, html: str) -> str:
        """
        Parse HTML and extract text content
        """
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style tags
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text(separator="\n", strip=True)
        return text