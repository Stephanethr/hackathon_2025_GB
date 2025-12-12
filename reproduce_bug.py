
import requests
import json
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/api/auth/login"
CHAT_URL = f"{BASE_URL}/api/chat/message"

# 1. Login to get token
session = requests.Session()
# Assuming a test user exists. If not, I'll need to use seed.py or existing user.
# The user from conversation history seems to be "AD" or similar.
# I'll try a default user if I know one.
# Let's try 'alice@example.com' 'password' (common seed) or checking seed.py?
# I'll check seed.py first if this fails.

# Actually, I'll make the script generic and use seed.py to check users first.
# For now, I'll assume I can find a user.

def reproduce_bug():
    # 1. Login
    # I'll try connecting with credentials that are likely in seed.py
    # Let's peek at seed.py first in next step, but for this script I'll assume:
    email = "admin@gbook.com" 
    password = "password"
    
    resp = session.post(LOGIN_URL, json={"username": "admin", "password": password})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return

    init_data = resp.json()
    token = init_data.get('token')
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Simulate User Request: "Réserve une salle pour lundi"
    # This should yield intent="BOOK_INTENT", slots={"start_time": "...", "attendees": null}
    # We expect the agent to ASK for attendees.
    # We expect the agent NOT to propose an event from TODAY.
    
    # Note: We can't easily force NLPService to parse "lundi" without mocking OpenAI.
    # But we can assume the NLP works and just check the logic in chat.py?
    # No, to run this end-to-end I need real NLP or I need to mock NLPService.
    # Since I can't restart the server easily to inject mocks, I have to rely on real NLP.
    
    msg = "Réserve une salle pour lundi"
    print(f"Sending message: {msg}")
    
    resp = session.post(CHAT_URL, json={"message": msg}, headers=headers)
    
    print("Response Status:", resp.status_code)
    # The response is streaming (ndjson).
    content = resp.text
    print("Response Content:", content)
    
    # Check if response contains "Je vois que vous avez un événement" (indicating proactive suggestion)
    # vs "Combien de personnes ?" (indicating standard flow)
    
    if "Je vois que vous avez un événement" in content:
        print("BUG REPRODUCED: Agent proposed an existing event instead of asking for details for Monday.")
    else:
        print("Behavior seems correct (or different bug).")

if __name__ == "__main__":
    reproduce_bug()
