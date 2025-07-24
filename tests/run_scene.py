"""
This script runs a sample scene using the TestHarness.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from tests.test_lib import TestHarness

def run_scene():
    """
    Runs a sample scene.
    """
    harness = TestHarness()
    try:
        harness.setup()
        harness.set_entity_data_dirs(["tests/test_data"])
        harness.set_location("test_room_01")
        harness.send_command("look around")
        time.sleep(5)
        harness.send_command("examine the goblet")
        time.sleep(5)
        harness.send_command("examine the spoon")
        time.sleep(5)
        harness.send_command("go to the kitchen") # This should fail
    finally:
        harness.teardown()

if __name__ == "__main__":
    run_scene() 