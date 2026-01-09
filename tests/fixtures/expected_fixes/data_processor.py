"""
Data Processor with proper error handling, documentation, and best practices.
"""

from typing import List, Dict, Optional


def process_data(data: List[int]) -> List[int]:
    """
    Process data by doubling all positive numbers.
    
    Args:
        data: List of integers to process
    
    Returns:
        List of doubled positive integers
    """
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result


def filter_even_numbers(numbers: List[int]) -> List[int]:
    """
    Filter and return only even numbers from the input list.
    
    Args:
        numbers: List of integers to filter
    
    Returns:
        List containing only even numbers
    """
    return [n for n in numbers if n % 2 == 0]


def get_max_value(values: List[int]) -> Optional[int]:
    """
    Find and return the maximum value in the list.
    
    Args:
        values: List of integers to search
    
    Returns:
        Maximum value, or None if list is empty
    """
    if not values:
        return None
    return max(values)


def parse_csv_line(line: str) -> Optional[Dict[str, str]]:
    """
    Parse a CSV line and return a dictionary.
    
    Args:
        line: CSV line with format 'name,age,city'
    
    Returns:
        Dictionary with parsed data, or None if parsing fails
    """
    try:
        parts = line.split(',')
        if len(parts) != 3:
            return None
        return {
            'name': parts[0].strip(),
            'age': int(parts[1].strip()),
            'city': parts[2].strip()
        }
    except (ValueError, IndexError):
        return None


class DataAnalyzer:
    """
    Analyzer for numerical data with statistical operations.
    """
    
    def __init__(self, data: List[int]):
        """
        Initialize the analyzer with data.
        
        Args:
            data: List of integers to analyze
        """
        self.data = data
        self.results: Optional[float] = None
    
    def analyze(self) -> Optional[float]:
        """
        Calculate the average of the data.
        
        Returns:
            Average value, or None if data is empty
        """
        if not self.data:
            return None
        
        total = sum(self.data)
        self.results = total / len(self.data)
        return self.results
    
    def get_summary(self) -> str:
        """
        Get a summary string of the analysis.
        
        Returns:
            Summary string with average, or message if not analyzed yet
        """
        if self.results is None:
            return "No analysis performed yet. Call analyze() first."
        return f"Average: {self.results:.2f}"
