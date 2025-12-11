import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import pytz
from app.extensions import db
from app.models.event import Event

class CalendarService:
    @staticmethod
    def sync_user_events(user):
        """
        Fetches events from the user's ICS URL and updates the database.
        Returns the list of stored/updated Event objects (optional).
        """
        if not user.ics_url:
            return []

        try:
            response = requests.get(user.ics_url, timeout=10)
            response.raise_for_status()
            
            cal = Calendar.from_ical(response.content)
            events = []
            
            now = datetime.now(pytz.utc)
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    summary = str(component.get('summary', ''))
                    location = str(component.get('location', ''))
                    start_dt = component.get('dtstart').dt
                    end_dt = component.get('dtend').dt if component.get('dtend') else None

                    # Handle all-day events (date objects) vs datetime objects
                    if not isinstance(start_dt, datetime):
                        # Convert date to datetime at midnight
                        start_dt = datetime.combine(start_dt, datetime.min.time())
                        start_dt = pytz.utc.localize(start_dt)
                    elif start_dt.tzinfo is None:
                        # Assume UTC if naive, or maybe better to assume configurable server time
                        # But for now, let's localize to UTC
                        start_dt = pytz.utc.localize(start_dt)
                        
                    if end_dt:
                        if not isinstance(end_dt, datetime):
                             end_dt = datetime.combine(end_dt, datetime.min.time())
                             end_dt = pytz.utc.localize(end_dt)
                        elif end_dt.tzinfo is None:
                             end_dt = pytz.utc.localize(end_dt)
                    else:
                        # Default 1 hour duration if no end time
                        end_dt = start_dt + timedelta(hours=1)

                    # Filter past events? Maybe only keep recent past and future.
                    # Let's keep all for now, or maybe last 30 days + future.
                    # User request: "Detect meetings without assigned rooms". 
                    # Probably implies future meetings.
                    # Let's filter to start > now - 24 hours to be safe/relevant.
                    # Actually, if we want to show "My Calendar", user might want to see history. 
                    # But for "AI Agent", future is more important.
                    # Filter past events: Only keep events that end in the future
                    if end_dt < now:
                        continue
                        
                    # We'll just parse all future/ongoing events.
                    
                    needs_room = False
                    if not location or location.strip() == "":
                        needs_room = True

                    # Calculate attendee count
                    attendee_count = 0
                    attendees = component.get('attendee')
                    if attendees:
                        if isinstance(attendees, list):
                            attendee_count = len(attendees)
                        else:
                            attendee_count = 1

                        
                    existing_event = Event.query.filter_by(uid=str(component.get('uid')), user_id=user.id).first()
                    
                    if existing_event:
                         existing_event.summary = summary
                         existing_event.start_time = start_dt
                         existing_event.end_time = end_dt
                         existing_event.location = location
                         existing_event.attendee_count = attendee_count
                         existing_event.updated_at = datetime.utcnow()
                    else:
                        new_event = Event(
                            uid=str(component.get('uid')),
                            summary=summary,
                            start_time=start_dt,
                            end_time=end_dt,
                            location=location,
                            attendee_count=attendee_count,
                            user_id=user.id
                        )
                        db.session.add(new_event)
                        
            db.session.commit()
            return True

        except Exception as e:
            print(f"Error fetching ICS: {e}")
            return False

    @staticmethod
    def get_stored_events(user):
        """
        Retrieves events from the database for the given user.
        Returns a list of event dictionaries formatted for the frontend.
        """
        # Get current time for determining needs_room logic if needed, 
        # or just return all future events?
        # The previous logic filtered "end_dt < now". 
        # We can do that in DB query or in python.
        
        now = datetime.now(pytz.utc)
        
        # Query events
        # We might want to filter by start time or end time?
        # Logic was: "if end_dt < now: continue"
        # So we want events where end_time >= now
        
        events = Event.query.filter(Event.user_id == user.id, Event.end_time >= now).order_by(Event.start_time).all()
        
        results = []
        for event in events:
            # Replicate 'needs_room' logic
            needs_room = False
            location = event.location
            
            if event.booking:
                 location = event.booking.room.name if event.booking.room else f"Room {event.booking.room_id}"
                 needs_room = False
            elif not location or location.strip() == "":
                needs_room = True
                
            results.append({
                'summary': event.summary,
                'start': event.start_time.isoformat(),
                'end': event.end_time.isoformat(),
                'location': location,
                'needs_room': needs_room,
                'attendee_count': event.attendee_count
            })
            
        return results


    @staticmethod
    def get_next_unbooked_event(user):
        """
        Finds the next upcoming event for the user that does not have a linked booking.
        """
        now = datetime.now(pytz.utc)
        return Event.query.filter(
            Event.user_id == user.id,
            Event.start_time > now,
            Event.booking_id == None
        ).order_by(Event.start_time).first()

    @staticmethod
    def link_event_to_booking(event_id, booking_id):
        """
        Links a calendar event to a booking.
        """
        event = Event.query.get(event_id)
        if event:
            event.booking_id = booking_id
            db.session.commit()
            return True
        return False


