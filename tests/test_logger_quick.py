"""
Quick test script to validate the logger functionality.
Run this to ensure the logger is working correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import log_experiment, ActionType

def test_logger():
    """Test the logger with valid and invalid inputs."""
    
    print("="*70)
    print("Testing Logger Functionality")
    print("="*70)
    
    # Test 1: Valid log entry
    print("\n✅ Test 1: Valid log entry with all required fields")
    try:
        log_experiment(
            agent_name="Test_Auditor",
            model_used="gemini-2.5-flash",
            action=ActionType.ANALYSIS,
            details={
                "file_analyzed": "test.py",
                "input_prompt": "Analyze this Python code for quality issues and bugs...",
                "output_response": "Found 3 issues: missing docstrings, no type hints, and potential division by zero.",
                "issues_found": 3
            },
            status="SUCCESS"
        )
        print("   ✅ PASSED: Valid log entry accepted")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
    
    # Test 2: Missing input_prompt
    print("\n❌ Test 2: Should FAIL - Missing input_prompt")
    try:
        log_experiment(
            agent_name="Test_Fixer",
            model_used="gemini-2.5-flash",
            action=ActionType.FIX,
            details={
                "file_fixed": "test.py",
                "output_response": "Fixed the issues"
                # Missing input_prompt - should fail
            },
            status="SUCCESS"
        )
        print("   ❌ FAILED: Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ PASSED: Correctly raised error - {str(e)[:80]}...")
    
    # Test 3: Empty prompts
    print("\n❌ Test 3: Should FAIL - Empty prompts")
    try:
        log_experiment(
            agent_name="Test_Agent",
            model_used="gemini-2.5-flash",
            action=ActionType.DEBUG,
            details={
                "input_prompt": "",  # Empty - should fail
                "output_response": ""  # Empty - should fail
            },
            status="SUCCESS"
        )
        print("   ❌ FAILED: Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ PASSED: Correctly raised error - {str(e)[:80]}...")
    
    # Test 4: Prompt too short
    print("\n❌ Test 4: Should FAIL - Prompt too short")
    try:
        log_experiment(
            agent_name="Test_Agent",
            model_used="gemini-2.5-flash",
            action=ActionType.GENERATION,
            details={
                "input_prompt": "hi",  # Too short - should fail
                "output_response": "ok"  # Too short - should fail
            },
            status="SUCCESS"
        )
        print("   ❌ FAILED: Should have raised ValueError")
    except ValueError as e:
        print(f"   ✅ PASSED: Correctly raised error - {str(e)[:80]}...")
    
    # Test 5: Valid with default status
    print("\n✅ Test 5: Valid with default status parameter")
    try:
        log_experiment(
            agent_name="Test_Judge",
            model_used="gemini-2.5-flash",
            action=ActionType.ANALYSIS,
            details={
                "test_file": "test_code.py",
                "input_prompt": "Run pytest on this file and report results...",
                "output_response": "All tests passed successfully. Coverage: 95%",
                "tests_passed": 10
            }
            # No status parameter - should use default "SUCCESS"
        )
        print("   ✅ PASSED: Default status parameter works")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
    
    print("\n" + "="*70)
    print("Logger Tests Complete!")
    print("="*70)
    print("\n✅ Check logs/experiment_data.json to see the logged entries\n")

if __name__ == "__main__":
    test_logger()
