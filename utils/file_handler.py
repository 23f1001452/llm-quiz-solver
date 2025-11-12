# ============================================================================
# utils/file_handler.py - File Processing Utilities
# ============================================================================

import io
import pandas as pd
import PyPDF2
import pdfplumber
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class FileHandler:
    """
    Handle various file formats (PDF, CSV, Excel)
    """
    
    async def process_pdf(self, content: bytes) -> str:
        """
        Extract text from PDF
        """
        try:
            # Try pdfplumber first (better for tables)
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    
                    # Extract tables if present
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            text += "\n\nTable:\n"
                            text += str(table)
                
                return text
        except Exception as e:
            logger.warning(f"pdfplumber failed, trying PyPDF2: {str(e)}")
            
            # Fallback to PyPDF2
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""
                return text
            except Exception as e2:
                logger.error(f"PDF processing failed: {str(e2)}")
                raise
    
    async def process_csv(self, content: bytes) -> pd.DataFrame:
        """
        Parse CSV into pandas DataFrame
        """
        try:
            df = pd.read_csv(io.BytesIO(content))
            logger.info(f"Loaded CSV with shape: {df.shape}")
            return df
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}")
            raise
    
    async def process_excel(self, content: bytes) -> Dict[str, pd.DataFrame]:
        """
        Parse Excel file (all sheets)
        """
        try:
            excel_file = pd.ExcelFile(io.BytesIO(content))
            sheets = {}
            for sheet_name in excel_file.sheet_names:
                sheets[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name)
            
            logger.info(f"Loaded Excel with {len(sheets)} sheets")
            return sheets
        except Exception as e:
            logger.error(f"Excel processing failed: {str(e)}")
            raise