# ============================================================================
# utils/visualizer.py - Visualization Utilities
# ============================================================================

import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Visualizer:
    """
    Create charts and visualizations
    """
    
    def __init__(self):
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (10, 6)
    
    def create_bar_chart(
        self,
        data: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Bar Chart"
    ) -> str:
        """
        Create bar chart and return as base64 string
        """
        fig, ax = plt.subplots()
        data.plot(kind='bar', x=x, y=y, ax=ax)
        ax.set_title(title)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def create_line_chart(
        self,
        data: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Line Chart"
    ) -> str:
        """
        Create line chart and return as base64 string
        """
        fig, ax = plt.subplots()
        data.plot(kind='line', x=x, y=y, ax=ax, marker='o')
        ax.set_title(title)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def create_scatter_plot(
        self,
        data: pd.DataFrame,
        x: str,
        y: str,
        title: str = "Scatter Plot"
    ) -> str:
        """
        Create scatter plot and return as base64 string
        """
        fig, ax = plt.subplots()
        ax.scatter(data[x], data[y])
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(title)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def create_histogram(
        self,
        data: pd.DataFrame,
        column: str,
        bins: int = 30,
        title: str = "Histogram"
    ) -> str:
        """
        Create histogram and return as base64 string
        """
        fig, ax = plt.subplots()
        data[column].hist(bins=bins, ax=ax)
        ax.set_xlabel(column)
        ax.set_ylabel("Frequency")
        ax.set_title(title)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def _fig_to_base64(self, fig) -> str:
        """
        Convert matplotlib figure to base64 string
        """
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        # Return as data URI
        return f"data:image/png;base64,{img_base64}"

