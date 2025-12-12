import requests
from app import create_app, db
from app.models import User, Event, Booking
from datetime import datetime, timedelta
import pytz

from werkzeug.security import generate_password_hash

app = create_app()

def test_greeting():
    with app.app_context():
        # 1. Setup User
        user = User.query.filter_by(username="test_verify").first()
        if not user:
            # Check if email exists
            if User.query.filter_by(email="test@verify.com").first():
                 # Should not happen unless username changed. Cleanup just in case.
                 User.query.filter_by(email="test@verify.com").delete()
                 
            user = User(username="test_verify", email="test@verify.com")
            user.password_hash = generate_password_hash("password")
            db.session.add(user)
            db.session.commit()
        
        # Login to get token
        client = app.test_client()
        res = client.post('/api/auth/login', json={"username": "test_verify", "password": "password"})
        token = res.get_json()['token']
        headers = {'Authorization': f'Bearer {token}'}

        # 2. Cleanup previous data
        Event.query.filter_by(user_id=user.id).delete()
        Booking.query.filter_by(user_id=user.id).delete()
        db.session.commit()

        print(f"Events after cleanup: {Event.query.filter_by(user_id=user.id).count()}")

        # 3. Test Case 1: No events -> Default Greeting
        print("\n--- Test 1 ---", flush=True)
        res = client.get('/api/chat/greeting', headers=headers)
        print(f"T1_STATUS:{res.status_code}", flush=True)
        data = res.get_json() or {}
        print(f"T1_TYPE:{data.get('type')}", flush=True)
        print(f"T1_MSG:{data.get('message')}", flush=True)
        
        # 4. Test Case 2: event with room -> Default Greeting
        print("\n--- Test 2 ---", flush=True)
        now = datetime.now(pytz.utc)
        evt_with_loc = Event(
            uid="test_uid_1",
            summary="Meeting with Room",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            location="Room A",
            user_id=user.id
        )
        db.session.add(evt_with_loc)
        db.session.commit()
        
        res = client.get('/api/chat/greeting', headers=headers)
        print(f"T2_STATUS:{res.status_code}", flush=True)
        data = res.get_json() or {}
        print(f"T2_TYPE:{data.get('type')}", flush=True)

        # 5. Test Case 3: Event WITHOUT location -> Suggestion
        print("\n--- Test 3 ---", flush=True)
        evt_no_loc = Event(
            uid="test_uid_2",
            summary="Brainstorming",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            location="", # Empty location
            user_id=user.id,
            attendee_count=4
        )
        db.session.add(evt_no_loc)
        db.session.commit()
        
        res = client.get('/api/chat/greeting', headers=headers)
        print(f"T3_STATUS:{res.status_code}", flush=True)
        data = res.get_json() or {}
        print(f"T3_TYPE:{data.get('type')}", flush=True)
        print(f"T3_MSG:{data.get('message')}", flush=True)
        if data.get('data'):
             print(f"T3_PAYLOAD:{data['data'].get('action_required')}", flush=True)

if __name__ == "__main__":
    test_greeting()
