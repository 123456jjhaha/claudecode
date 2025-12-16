#!/usr/bin/env python3
"""
Simple Calculator Module

This module provides basic arithmetic operations and a Calculator class
to perform mathematical calculations.
"""

import operator
from typing import Union, Any


class Calculator:
    """A simple calculator class that supports basic arithmetic operations."""
    
    def __init__(self):
        """Initialize the calculator with a result of 0."""
        self.result = 0
        self.history = []
    
    def add(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Add two numbers."""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
    
    def subtract(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Subtract b from a."""
        result = a - b
        self.history.append(f"{a} - {b} = {result}")
        return result
    
    def multiply(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Multiply two numbers."""
        result = a * b
        self.history.append(f"{a} * {b} = {result}")
        return result
    
    def divide(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Divide a by b."""
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(f"{a} / {b} = {result}")
        return result
    
    def power(self, a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
        """Raise a to the power of b."""
        result = a ** b
        self.history.append(f"{a} ^ {b} = {result}")
        return result
    
    def clear_history(self):
        """Clear the calculation history."""
        self.history = []
    
    def get_history(self) -> list:
        """Get the calculation history."""
        return self.history.copy()


def calculate(expression: str) -> Any:
    """
    Evaluate a mathematical expression.
    
    Args:
        expression: A string containing a mathematical expression
        
    Returns:
        The result of the expression evaluation
    """
    try:
        # Simple expression evaluation (not secure for production)
        return eval(expression)
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")


def main():
    """Main function to demonstrate calculator usage."""
    calc = Calculator()
    
    print("Calculator Demo")
    print("===============")
    
    # Basic operations
    print(f"5 + 3 = {calc.add(5, 3)}")
    print(f"10 - 4 = {calc.subtract(10, 4)}")
    print(f"6 * 7 = {calc.multiply(6, 7)}")
    print(f"15 / 3 = {calc.divide(15, 3)}")
    print(f"2 ^ 3 = {calc.power(2, 3)}")
    
    print("\nCalculation History:")
    for record in calc.get_history():
        print(f"  {record}")


if __name__ == "__main__":
    main()
