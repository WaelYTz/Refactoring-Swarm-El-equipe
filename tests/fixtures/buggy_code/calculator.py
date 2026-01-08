"""
Calculator module with multiple bugs and code quality issues.
This file is intentionally broken for testing purposes.
"""

def add(a,b):
    # Missing docstring, no type hints, poor formatting
    return a+b

def substract(a, b):
    # Typo in function name (should be "subtract")
    # Missing docstring
    return a-b

def multiply(x,y):
    # Missing docstring, inconsistent parameter names
    result=x*y
    return result

def divide(a,b):
    # Missing docstring, no error handling for division by zero
    return a/b

def power(base,exp):
    # Missing docstring, inefficient implementation
    result=1
    for i in range(exp):
        result=result*base
    return result

class Calculator:
    # Missing docstring
    def __init__(self):
        pass
    
    def calculate(self,operation,a,b):
        # Missing docstring, no input validation, poor spacing
        if operation=="add":
            return a+b
        elif operation=="subtract":
            return a-b
        elif operation=="multiply":
            return a*b
        elif operation=="divide":
            return a/b
        else:
            return None

# Unused import
import sys
import os

# Dead code
def unused_function():
    x = 5
    y = 10
    z = x + y
    # Function does nothing useful
