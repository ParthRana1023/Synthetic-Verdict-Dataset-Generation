# test_rotation.py
import time
from llm_manager import get_current_model, get_current_key, rotate_key, rotate_model, print_rotation_status, reset_rotation_counters

# Reset counters to start fresh
reset_rotation_counters()

# Print initial status
print("\n===== INITIAL STATUS =====")
print_rotation_status()

# Test key rotation for first model
print("\n===== TESTING KEY ROTATION FOR FIRST MODEL =====")
for i in range(3):
    print(f"\nRotation {i+1}:")
    rotate_key()
    time.sleep(1)

# Switch to second model
print("\n===== SWITCHING TO SECOND MODEL =====")
rotate_model()

# Test key rotation for second model
print("\n===== TESTING KEY ROTATION FOR SECOND MODEL =====")
for i in range(3):
    print(f"\nRotation {i+1} for second model:")
    rotate_key()
    time.sleep(1)

# Switch back to first model
print("\n===== SWITCHING BACK TO FIRST MODEL =====")
reset_rotation_counters()  # Reset everything
rotate_key()  # Use up first key of first model
rotate_model()  # Switch to second model
rotate_model()  # Switch to third model
rotate_model()  # Switch back to first model

# Check if keys for first model are still tracked correctly
print("\n===== CHECKING KEYS FOR FIRST MODEL AFTER CYCLE =====")
print_rotation_status()

# Reset and print final status
print("\n===== RESETTING COUNTERS =====")
reset_rotation_counters()