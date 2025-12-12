
import requests
import json
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Event
import pytz

# Setup App Context to manipulate DB directly
app = create_app()

def get_next_monday():
    today = datetime.now()
    days_ahead = 0 - today.weekday() + 7
    if days_ahead <= 0: # Target next week if today is Monday (or bug logic might be tricky, let's just say closest future Monday)
         days_ahead += 7
    return today + timedelta(days=days_ahead)

def setup_test_data():
    with app.app_context():
        # 1. Get Admin User
        user = User.query.filter_by(username='admin').first()
        if not user:
            print("User admin not found")
            return None
            
        # 2. Create an unbooked event for Next Monday at 10:00
        next_monday = get_next_monday()
        start = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        
        # Ensure UTC if models expect it (CalendarService uses pytz.utc)
        # But models might store naive if sqlite? 
        # app/services/calendar_service.py uses pytz.utc.localize
        
        # Let's clean up existing events for this user to avoid noise
        Event.query.filter_by(user_id=user.id).delete()
        
        event = Event(
            uid="test_monday_event_1",
            summary="Réunion Test Lundi",
            start_time=start,
            end_time=end,
            location="", # Empty location = needs room
            attendee_count=3,
            user_id=user.id
        )
        db.session.add(event)
        db.session.commit()
        print(f"Created test event: {event.summary} on {start}")
        return start

def test_chat():
    BASE_URL = "http://localhost:5000"
    LOGIN_URL = f"{BASE_URL}/api/auth/login"
    CHAT_URL = f"{BASE_URL}/api/chat/message"
    
    session = requests.Session()
    
    # Login
    resp = session.post(LOGIN_URL, json={"username": "admin", "password": "password"})
    if resp.status_code != 200:
        print("Login failed")
        return
        
    token = resp.json().get('token')
    headers = {"Authorization": f"Bearer {token}"}
    
    # Chat
    msg = "Réserve une salle pour lundi"
    print(f"Sending: {msg}")
    
    resp = session.post(CHAT_URL, json={"message": msg}, headers=headers)
    content = resp.text
    print("Response:", content)
    
    if "Réunion Test Lundi" in content:
        print("SUCCESS: Agent proposed the Monday event.")
    else:
        print("FAILURE: Agent did NOT propose the Monday event.")

if __name__ == "__main__":
    monday_date = setup_test_data()
    if monday_date:
        test_chat()
