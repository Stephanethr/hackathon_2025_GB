import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import pytz

class CalendarService:
    @staticmethod
    def fetch_user_events(user):
        """
        Fetches and parses events from the user's ICS URL.
        Returns a list of event dictionaries.
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
                        
                    events.append({
                        'summary': summary,
                        'start': start_dt.isoformat(),
                        'end': end_dt.isoformat(),
                        'location': location,
                        'needs_room': needs_room
                    })
            
            # Sort by start time
            events.sort(key=lambda x: x['start'])
            return events

        except Exception as e:
            print(f"Error fetching ICS: {e}")
            return []
