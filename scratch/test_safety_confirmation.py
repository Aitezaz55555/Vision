"""
Test two-step confirmation safety flow for sensitive operations (shutdown, restart).
"""
import sys
import os

sys.path.insert(0, os.path.abspath("."))
import vision
import modules.system

# Mock speak and execute_shutdown
spoken = []
vision.speak = lambda text: spoken.append(str(text))
modules.system.execute_shutdown = lambda restart=False: (True, f"Simulated {'restart' if restart else 'shutdown'} initiated.")

print("=== Testing Safety Confirmation Flow ===")

# Test 1: Shutdown requested then cancelled
spoken.clear()
vision.process_command("shutdown the pc")
print("1. After 'shutdown the pc':", spoken[-1] if spoken else "None")
assert "shut down your computer" in spoken[-1].lower()

spoken.clear()
vision.process_command("no")
print("2. After 'no':", spoken[-1] if spoken else "None")
assert "cancelled" in spoken[-1].lower()

# Test 2: Restart requested then confirmed
spoken.clear()
vision.process_command("restart the computer")
print("3. After 'restart the computer':", spoken[-1] if spoken else "None")
assert "restart your computer" in spoken[-1].lower()

spoken.clear()
vision.process_command("yes")
print("4. After 'yes':", spoken[-1] if spoken else "None")
assert "restart" in spoken[-1].lower()

print("\nALL SAFETY CONFIRMATION TESTS PASSED!")
