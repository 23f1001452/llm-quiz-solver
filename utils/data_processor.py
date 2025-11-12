# ============================================================================
# utils/data_processor.py - Data Analysis Utilities
# ============================================================================

import pandas as pd
import numpy as np
from typing import Any, List, Dict
import logging

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Data processing and analysis utilities
    """
    
    def sum_column(self, df: pd.DataFrame, column: str) -> float:
        """Sum values in a column"""
        return df[column].sum()
    
    def filter_data(
        self,
        df: pd.DataFrame,
        column: str,
        condition: str,
        value: Any
    ) -> pd.DataFrame:
        """
        Filter DataFrame based on condition
        
        condition: '==', '!=', '>', '<', '>=', '<='
        """
        if condition == "==":
            return df[df[column] == value]
        elif condition == "!=":
            return df[df[column] != value]
        elif condition == ">":
            return df[df[column] > value]
        elif condition == "<":
            return df[df[column] < value]
        elif condition == ">=":
            return df[df[column] >= value]
        elif condition == "<=":
            return df[df[column] <= value]
        else:
            raise ValueError(f"Unknown condition: {condition}")
    
    def group_by_aggregate(
        self,
        df: pd.DataFrame,
        group_by: str,
        agg_column: str,
        agg_func: str = "sum"
    ) -> pd.DataFrame:
        """
        Group by and aggregate
        
        agg_func: 'sum', 'mean', 'count', 'min', 'max'
        """
        return df.groupby(group_by)[agg_column].agg(agg_func).reset_index()
    
    def sort_data(
        self,
        df: pd.DataFrame,
        column: str,
        ascending: bool = True
    ) -> pd.DataFrame:
        """Sort DataFrame by column"""
        return df.sort_values(by=column, ascending=ascending)
    
    def get_statistics(self, df: pd.DataFrame, column: str) -> Dict[str, float]:
        """Get basic statistics for a column"""
        return {
            "mean": df[column].mean(),
            "median": df[column].median(),
            "std": df[column].std(),
            "min": df[column].min(),
            "max": df[column].max(),
            "count": len(df[column])
        }
    
    def pivot_table(
        self,
        df: pd.DataFrame,
        index: str,
        columns: str,
        values: str,
        aggfunc: str = "sum"
    ) -> pd.DataFrame:
        """Create pivot table"""
        return pd.pivot_table(
            df,
            index=index,
            columns=columns,
            values=values,
            aggfunc=aggfunc
        )