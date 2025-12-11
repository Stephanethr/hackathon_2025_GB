import os
import sys

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from app.services.nlp_service import NLPService
from datetime import datetime

# Mock datetime to simulate the date reported by the user (2025-12-11 Thursday)
# We can't easily mock datetime.now() inside the class without external libraries like freezegun
# But we can check if the current system time matches what we expect for the test.
# The user metadata says it is 2025-12-11.

print(f"Current System Time: {datetime.now()}")

intent_text = "envoie-moi une salle pour lundi à 10h"
print(f"Testing text: '{intent_text}'")

intent, slots = NLPService.parse_intent(intent_text, [])

print(f"Detected Intent: {intent}")
print(f"Detected Slots: {slots}")

start_time = slots.get('start_time')
if start_time:
    print(f"Start Time: {start_time}")
    # We expect Monday Dec 15th, 2025
    if "2025-12-15" in start_time:
        print("SUCCESS: Correctly identified Monday Dec 15th")
    elif "2025-12-14" in start_time:
        print("FAILURE: Incorrectly identified Sunday Dec 14th")
    else:
        print(f"FAILURE: Identified unexpected date {start_time}")
else:
    print("FAILURE: No start_time detected")
