import unittest
from unittest.mock import patch, MagicMock
from app import create_app, db
from app.models.user import User
from app.models.event import Event
from app.services.calendar_service import CalendarService
from datetime import datetime
import pytz

class TestCalendarStorage(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.services.calendar_service.requests.get')
    def test_fetch_and_store_events(self, mock_get):
        # Mock ICS content
        ics_content = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
DTSTART:20251225T100000Z
DTEND:20251225T110000Z
DTSTAMP:20251211T120000Z
UID:test-uid-123
SUMMARY:Test Meeting
LOCATION:Room A
DESCRIPTION:This is a test meeting
END:VEVENT
END:VCALENDAR"""

        mock_response = MagicMock()
        mock_response.content = ics_content
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Create a user
        user = User(username='testuser', email='test@example.com', ics_url='http://example.com/calendar.ics')
        db.session.add(user)
        db.session.commit()

        # Fetch events
        CalendarService.sync_user_events(user)
        events = CalendarService.get_stored_events(user)

        # assert return value
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['summary'], 'Test Meeting')

        # Assert DB storage
        stored_event = Event.query.filter_by(uid='test-uid-123').first()
        self.assertIsNotNone(stored_event)
        self.assertEqual(stored_event.summary, 'Test Meeting')
        self.assertEqual(stored_event.attendee_count, 0) # Default
        
        # Test Update
        # Change summary in ICS
        ics_content_updated = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
DTSTART:20251225T100000Z
DTEND:20251225T110000Z
DTSTAMP:20251211T120000Z
UID:test-uid-123
SUMMARY:Updated Meeting
LOCATION:Room A
DESCRIPTION:This is a test meeting
ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;CN=Test User;X-NUM-GUESTS=0:mailto:test@example.com
END:VEVENT
END:VCALENDAR"""
        mock_response.content = ics_content_updated
        
        CalendarService.sync_user_events(user)
        events_updated = CalendarService.get_stored_events(user)
        self.assertEqual(len(events_updated), 1)
        self.assertEqual(events_updated[0]['summary'], 'Updated Meeting')
        self.assertEqual(events_updated[0]['attendee_count'], 1)
        
        stored_event_updated = Event.query.filter_by(uid='test-uid-123').first()
        self.assertEqual(stored_event_updated.summary, 'Updated Meeting')
        self.assertEqual(stored_event_updated.attendee_count, 1)
        # Check that we still only have 1 event
        self.assertEqual(Event.query.count(), 1)

if __name__ == '__main__':
    unittest.main()
