# ============================================================================
# utils/web_scraper.py - Web Scraping Utilities
# ============================================================================

import httpx
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Web scraping utilities
    """
    
    async def scrape_text(self, url: str) -> str:
        """
        Scrape text content from URL
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style
            for element in soup(['script', 'style', 'nav', 'footer']):
                element.decompose()
            
            return soup.get_text(separator='\n', strip=True)
    
    async def scrape_table(self, url: str) -> List[Dict]:
        """
        Scrape tables from URL
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            tables = soup.find_all('table')
            
            result = []
            for table in tables:
                rows = []
                headers = [th.get_text(strip=True) for th in table.find_all('th')]
                
                for tr in table.find_all('tr')[1:]:  # Skip header row
                    cells = [td.get_text(strip=True) for td in tr.find_all('td')]
                    if cells:
                        if headers:
                            rows.append(dict(zip(headers, cells)))
                        else:
                            rows.append(cells)
                
                result.append(rows)
            
            return result
    
    async def fetch_api(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict:
        """
        Fetch data from API
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, json=json)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()