"""
String utilities with proper documentation, efficiency, and best practices.
"""

from typing import Optional


def reverse_string(s: str) -> str:
    """
    Reverse a string efficiently.
    
    Args:
        s: String to reverse
    
    Returns:
        Reversed string
    """
    return s[::-1]


def count_vowels(text: str, case_sensitive: bool = False) -> int:
    """
    Count the number of vowels in a text string.
    
    Args:
        text: Text to analyze
        case_sensitive: Whether to distinguish between upper and lowercase vowels
    
    Returns:
        Number of vowels found
    """
    vowels = set('aeiouAEIOU') if not case_sensitive else set('aeiou')
    if not case_sensitive:
        text = text.lower()
    return sum(1 for char in text if char in vowels)


def is_palindrome(word: str) -> bool:
    """
    Check if a word is a palindrome.
    
    Args:
        word: Word to check
    
    Returns:
        True if word is a palindrome, False otherwise
    """
    cleaned = word.lower().strip()
    return cleaned == cleaned[::-1]


def capitalize_words(sentence: str) -> str:
    """
    Capitalize the first letter of each word in a sentence.
    
    Args:
        sentence: Sentence to capitalize
    
    Returns:
        Sentence with capitalized words
    
    Raises:
        ValueError: If sentence is empty
    """
    if not sentence or not sentence.strip():
        raise ValueError("Sentence cannot be empty")
    
    words = sentence.split()
    capitalized = [word.capitalize() for word in words]
    return ' '.join(capitalized)


def remove_duplicates(text: str) -> str:
    """
    Remove duplicate characters from text while preserving order.
    
    Args:
        text: Text to process
    
    Returns:
        Text with duplicate characters removed
    """
    seen = set()
    result = []
    for char in text:
        if char not in seen:
            seen.add(char)
            result.append(char)
    return ''.join(result)


DEFAULT_TRUNCATE_LENGTH = 50
ELLIPSIS = "..."


def truncate_string(s: str, length: int = DEFAULT_TRUNCATE_LENGTH) -> str:
    """
    Truncate a string to a specified length and add ellipsis if needed.
    
    Args:
        s: String to truncate
        length: Maximum length (default: 50)
    
    Returns:
        Truncated string with ellipsis if applicable
    """
    if len(s) <= length:
        return s
    return s[:length] + ELLIPSIS


class StringManipulator:
    """
    A utility class for string manipulation operations.
    """
    
    def __init__(self, text: str):
        """
        Initialize the string manipulator.
        
        Args:
            text: The text to manipulate
        """
        self.text = text
    
    def to_upper(self) -> str:
        """
        Convert text to uppercase.
        
        Returns:
            Uppercase version of text
        """
        return self.text.upper()
    
    def to_lower(self) -> str:
        """
        Convert text to lowercase.
        
        Returns:
            Lowercase version of text
        """
        return self.text.lower()
    
    def word_count(self) -> int:
        """
        Count the number of words in the text.
        
        Returns:
            Number of words
        """
        # Split by whitespace and filter empty strings
        words = self.text.split()
        return len(words)
