"""
Calculator module with proper documentation, type hints, and error handling.
This is the expected fixed version.
"""

from typing import Union


def add(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Add two numbers together.
    
    Args:
        a: First number to add
        b: Second number to add
    
    Returns:
        The sum of a and b
    """
    return a + b


def subtract(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Subtract b from a.
    
    Args:
        a: Number to subtract from
        b: Number to subtract
    
    Returns:
        The difference between a and b
    """
    return a - b


def multiply(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    """
    Multiply two numbers.
    
    Args:
        a: First number to multiply
        b: Second number to multiply
    
    Returns:
        The product of a and b
    """
    return a * b


def divide(a: Union[int, float], b: Union[int, float]) -> float:
    """
    Divide a by b.
    
    Args:
        a: Dividend
        b: Divisor
    
    Returns:
        The quotient of a divided by b
    
    Raises:
        ValueError: If b is zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


def power(base: Union[int, float], exp: int) -> Union[int, float]:
    """
    Raise base to the power of exp.
    
    Args:
        base: The base number
        exp: The exponent
    
    Returns:
        base raised to the power of exp
    """
    return base ** exp


class Calculator:
    """
    A simple calculator class for basic arithmetic operations.
    """
    
    def __init__(self):
        """Initialize the calculator."""
        pass
    
    def calculate(self, operation: str, a: Union[int, float], b: Union[int, float]) -> Union[int, float, None]:
        """
        Perform a calculation based on the specified operation.
        
        Args:
            operation: The operation to perform ('add', 'subtract', 'multiply', 'divide')
            a: First operand
            b: Second operand
        
        Returns:
            The result of the calculation, or None if operation is invalid
        
        Raises:
            ValueError: If attempting to divide by zero
        """
        if operation == "add":
            return a + b
        elif operation == "subtract":
            return a - b
        elif operation == "multiply":
            return a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Cannot divide by zero")
            return a / b
        else:
            return None
