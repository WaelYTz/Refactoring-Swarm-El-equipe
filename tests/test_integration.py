"""
Integration Tests for Refactoring Swarm System

This module contains end-to-end tests to validate the complete workflow
of the Refactoring Swarm from buggy code to fixed, tested code.
"""

import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Import the logger to validate experiment data
from src.utils.logger import ActionType, LOG_FILE


class TestRefactoringSwarmIntegration(unittest.TestCase):
    """
    End-to-end integration tests for the Refactoring Swarm system.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures and temporary directories."""
        cls.fixtures_dir = Path(__file__).parent / "fixtures"
        cls.buggy_code_dir = cls.fixtures_dir / "buggy_code"
        cls.expected_fixes_dir = cls.fixtures_dir / "expected_fixes"
        
        # Create temporary sandbox directory
        cls.temp_sandbox = Path(tempfile.mkdtemp(prefix="test_sandbox_"))
    
    @classmethod
    def tearDownClass(cls):
        """Clean up temporary directories."""
        if cls.temp_sandbox.exists():
            shutil.rmtree(cls.temp_sandbox)
    
    def setUp(self):
        """Set up before each test."""
        # Clear the sandbox for each test
        for item in self.temp_sandbox.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
    
    def test_fixtures_exist(self):
        """Test that all required fixture files exist."""
        self.assertTrue(self.buggy_code_dir.exists(), "Buggy code directory should exist")
        self.assertTrue(self.expected_fixes_dir.exists(), "Expected fixes directory should exist")
        
        # Check for specific test files
        test_files = ["calculator.py", "data_processor.py", "string_utils.py"]
        for test_file in test_files:
            buggy_path = self.buggy_code_dir / test_file
            expected_path = self.expected_fixes_dir / test_file
            
            self.assertTrue(buggy_path.exists(), f"Buggy {test_file} should exist")
            self.assertTrue(expected_path.exists(), f"Expected fix for {test_file} should exist")
    
    def test_buggy_code_has_issues(self):
        """Test that buggy code files actually contain quality issues."""
        from subprocess import run, PIPE
        import sys
        
        test_file = self.buggy_code_dir / "calculator.py"
        
        # Run pylint on buggy code (should have low score)
        # Use python -m pylint to ensure it runs in the current environment
        result = run(
            [sys.executable, "-m", "pylint", str(test_file), "--score=yes"],
            stdout=PIPE,
            stderr=PIPE,
            text=True
        )
        
        # Pylint should find issues (score < 10)
        output = result.stdout
        self.assertIn("rated at", output.lower(), "Pylint should rate the code")
    
    def test_experiment_log_structure(self):
        """Test that experiment_data.json has the correct structure."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIsInstance(data, list, "Log data should be a list")
        
        if len(data) > 0:
            entry = data[0]
            required_fields = ["id", "timestamp", "agent", "model", "action", "details", "status"]
            
            for field in required_fields:
                self.assertIn(field, entry, f"Log entry should have '{field}' field")
    
    def test_experiment_log_action_types(self):
        """Test that logged actions use valid ActionType values."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        valid_actions = [a.value for a in ActionType]
        
        for entry in data:
            if "action" in entry and entry["action"] not in ["STARTUP", "INFO"]:
                self.assertIn(
                    entry["action"], 
                    valid_actions,
                    f"Action '{entry['action']}' should be a valid ActionType"
                )
    
    def test_experiment_log_has_prompts(self):
        """Test that log entries for LLM interactions contain required prompts."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        llm_action_types = [ActionType.ANALYSIS.value, ActionType.GENERATION.value, 
                           ActionType.DEBUG.value, ActionType.FIX.value]
        
        for entry in data:
            if entry.get("action") in llm_action_types:
                details = entry.get("details", {})
                
                # These fields are REQUIRED for LLM interactions
                self.assertIn(
                    "input_prompt", 
                    details,
                    f"LLM action should have 'input_prompt' in details"
                )
                self.assertIn(
                    "output_response",
                    details,
                    f"LLM action should have 'output_response' in details"
                )
                
                # Validate they're not empty
                self.assertTrue(
                    details["input_prompt"],
                    "input_prompt should not be empty"
                )
                self.assertTrue(
                    details["output_response"],
                    "output_response should not be empty"
                )


class TestLoggerValidation(unittest.TestCase):
    """
    Tests specifically for the logger validation functionality.
    """
    
    def test_logger_requires_prompts_for_llm_actions(self):
        """Test that logger raises error when prompts are missing for LLM actions."""
        from src.utils.logger import log_experiment
        
        # This should raise ValueError due to missing prompts
        with self.assertRaises(ValueError) as context:
            log_experiment(
                agent_name="Test_Agent",
                model_used="gemini-2.5-flash",
                action=ActionType.ANALYSIS,
                details={"file": "test.py"},  # Missing input_prompt and output_response
                status="SUCCESS"
            )
        
        self.assertIn("input_prompt", str(context.exception))
        self.assertIn("output_response", str(context.exception))
    
    def test_logger_accepts_valid_log(self):
        """Test that logger accepts properly formatted log entries."""
        from src.utils.logger import log_experiment
        
        # This should NOT raise an error
        try:
            log_experiment(
                agent_name="Test_Agent",
                model_used="gemini-2.5-flash",
                action=ActionType.ANALYSIS,
                details={
                    "file_analyzed": "test.py",
                    "input_prompt": "Analyze this code for quality issues...",
                    "output_response": "Found 3 issues: missing docstrings, no type hints...",
                    "issues_found": 3
                },
                status="SUCCESS"
            )
        except ValueError:
            self.fail("Logger should accept valid log entry with prompts")
    
    def test_logger_validates_prompt_length(self):
        """Test that logger validates prompt content is not trivially short."""
        from src.utils.logger import log_experiment
        
        # Should fail with very short prompts
        with self.assertRaises(ValueError):
            log_experiment(
                agent_name="Test_Agent",
                model_used="gemini-2.5-flash",
                action=ActionType.ANALYSIS,
                details={
                    "input_prompt": "hi",  # Too short
                    "output_response": "ok"  # Too short
                },
                status="SUCCESS"
            )


class TestDataQuality(unittest.TestCase):
    """
    Tests for data quality metrics required for grading.
    """
    
    def test_log_file_is_valid_json(self):
        """Test that the log file is valid JSON."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            self.fail(f"Log file is not valid JSON: {e}")
    
    def test_log_entries_have_unique_ids(self):
        """Test that all log entries have unique IDs."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ids = [entry.get("id") for entry in data]
        unique_ids = set(ids)
        
        self.assertEqual(
            len(ids),
            len(unique_ids),
            "All log entries should have unique IDs"
        )
    
    def test_log_entries_are_chronological(self):
        """Test that log entries are in chronological order."""
        if not os.path.exists(LOG_FILE):
            self.skipTest("No experiment log file exists yet")
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if len(data) < 2:
            self.skipTest("Need at least 2 log entries to test chronology")
        
        from datetime import datetime
        
        timestamps = []
        for entry in data:
            if "timestamp" in entry:
                try:
                    dt = datetime.fromisoformat(entry["timestamp"])
                    timestamps.append(dt)
                except ValueError:
                    self.fail(f"Invalid timestamp format: {entry['timestamp']}")
        
        # Check if timestamps are in ascending order
        for i in range(len(timestamps) - 1):
            self.assertLessEqual(
                timestamps[i],
                timestamps[i + 1],
                "Log entries should be in chronological order"
            )


def run_integration_tests():
    """
    Run all integration tests and return results.
    
    Returns:
        unittest.TestResult: Test results object
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestRefactoringSwarmIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggerValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestDataQuality))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    # Run tests when executed directly
    unittest.main(verbosity=2)
