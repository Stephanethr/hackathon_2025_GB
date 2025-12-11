from app import create_app, db
from app.models.user import User
from app.models.event import Event
from app.models.room import Room
from app.models.booking import Booking
from app.services.calendar_service import CalendarService
from datetime import datetime, timedelta
import pytz

app = create_app()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['TESTING'] = True
ctx = app.app_context()
ctx.push()
db.create_all()

# Setup Data
user = User(username='testuser', email='test@example.com')
db.session.add(user)

room = Room(name='Boardroom', capacity=12)
db.session.add(room)
db.session.commit()

now = datetime.now(pytz.utc)
start = now + timedelta(hours=2)
end = start + timedelta(hours=1)

# Event 1: No Booking, Needs Room
event1 = Event(uid='1', summary='Open Meeting', start_time=start, end_time=end, user_id=user.id, location='')
db.session.add(event1)

# Event 2: Linked Booking
event2 = Event(uid='2', summary='Booked Meeting', start_time=start, end_time=end, user_id=user.id, location='')
db.session.add(event2)
db.session.commit()

# Create Booking and Link
booking = Booking(user_id=user.id, room_id=room.id, start_time=start, end_time=end, title='Booked Meeting')
db.session.add(booking)
db.session.commit()

CalendarService.link_event_to_booking(event2.id, booking.id)

# Verify Output
events = CalendarService.get_stored_events(user)
print(f"Total events: {len(events)}")

found_booked = False
for e in events:
    print(f"Event: {e['summary']}, Location: '{e['location']}', Needs Room: {e['needs_room']}")
    if e['summary'] == 'Booked Meeting':
        if e['location'] == 'Boardroom' and not e['needs_room']:
            found_booked = True
            print("SUCCESS: Booked Meeting has correct location and needs_room=False")
        else:
            print("FAILURE: Booked Meeting incorrect.")
    elif e['summary'] == 'Open Meeting':
        if e['needs_room']:
             print("SUCCESS: Open Meeting still needs room.")
        else:
             print("FAILURE: Open Meeting should need room.")

if found_booked:
    print("Verification PASSED")
else:
    print("Verification FAILED")
