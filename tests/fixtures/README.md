# Test Fixtures for Refactoring Swarm

This directory contains sample code files used to test and validate the Refactoring Swarm system.

## Structure

### buggy_code/
Contains intentionally buggy Python files with various code quality issues:
- **calculator.py**: Missing docstrings, no type hints, poor formatting, division by zero
- **data_processor.py**: No error handling, empty list bugs, global variables
- **string_utils.py**: Inefficient algorithms, missing edge case handling, magic numbers

### expected_fixes/
Contains the expected corrected versions of the buggy code files with:
- Proper docstrings
- Type hints
- Error handling
- PEP 8 compliance
- Efficient implementations

## Usage

These fixtures are used by the integration tests to validate that the Refactoring Swarm system:
1. Detects code quality issues
2. Applies appropriate fixes
3. Improves Pylint scores
4. Maintains functionality

## Adding New Test Cases

When adding new test cases:
1. Create a buggy file in `buggy_code/`
2. Create the expected fixed version in `expected_fixes/`
3. Document the specific issues in comments
4. Update the integration tests accordingly
