from datetime import datetime
from sqlalchemy import or_, and_
from app.models import Room, Booking
from app.extensions import db
from app.config import Config

class BookingService:
    
    @staticmethod
    def is_within_working_hours(start_time: datetime, end_time: datetime) -> bool:
        """Check if booking respects working hours."""
        # Config defaults
        wh_start = Config.WORKING_HOURS_START
        wh_end = Config.WORKING_HOURS_END
        
        # Simple check: start and end must be within [start, end] hour of the day
        # Note: This implies single-day bookings for simplicity. Multi-day would need split check.
        if start_time.hour < wh_start or end_time.hour > wh_end:
            return False
        if start_time.hour > end_time.hour: # Invalid range
            return False
        return True

    @staticmethod
    def is_capacity_coherent(capacity: int, attendees: int) -> bool:
        """
        Check if the room capacity is 'coherent' for the number of attendees.
        Rule: Coherent if capacity <= max(attendees * 3, 20).
        This means for 4 people, up to 20 is fine. 50 (Auditorium) is not.
        """
        threshold = max(attendees * 3, 20)
        return capacity <= threshold

    @staticmethod
    def check_availability(room_id, start_time, end_time, exclude_booking_id=None):
        """Check if room is free during interval, optionally excluding a specific booking."""
        query = Booking.query.filter(
            Booking.room_id == room_id,
            Booking.status == 'confirmed',
            Booking.start_time < end_time,
            Booking.end_time > start_time
        )
        
        if exclude_booking_id:
            query = query.filter(Booking.id != exclude_booking_id)
            
        conflict = query.first()
        return conflict is None

    @staticmethod
    def find_potential_rooms(start_time, end_time, attendees: int, required_equipment: list = None, preferred_room_name: str = None, excluded_room_names: list = None):
        """Find all rooms that are free and fit the attendees."""
        # 1. Filter by capacity
        capable_rooms = Room.query.filter(Room.capacity >= attendees, Room.is_active == True).all()
        
        # 2. Filter by Preferred Name (if requested)
        if preferred_room_name:
            # Normalize for comparison
            pref = preferred_room_name.lower().strip()
            # Try exact/partial match
            named_matches = [r for r in capable_rooms if pref in r.name.lower()]
            if named_matches:
                 capable_rooms = named_matches
            # If no match found, we might fall back to all capable rooms or return empty.
            # Decision: if user asks for specific room and it doesn't exist/fit, return empty to let Upper Layer explain.
            else:
                 return []
                 
        # 2.5 Filter Excluded Rooms
        if excluded_room_names:
            excluded = [e.lower().strip() for e in excluded_room_names]
            capable_rooms = [r for r in capable_rooms if not any(ex in r.name.lower() for ex in excluded)]

        # 3. Filter by Equipment (if requested)
        if required_equipment:
            filtered_rooms = []
            for room in capable_rooms:
                if not room.equipment:
                    continue
                    
                room_eq_lower = [e.lower() for e in room.equipment]
                has_all = True
                for req in required_equipment:
                    if req.lower() not in room_eq_lower:
                        has_all = False
                        break
                if has_all:
                    filtered_rooms.append(room)
            capable_rooms = filtered_rooms

        available_rooms = []
        for room in capable_rooms:
            if BookingService.check_availability(room.id, start_time, end_time):
                available_rooms.append(room)
        
        # Sort by capacity ascending (Best fit first)
        available_rooms.sort(key=lambda r: r.capacity)
        
        # 4. Smart Filtering: Hide oversized rooms if "Good Fit" rooms are available.
        # "Good fit" = capacity <= attendees * 3 (arbitrary heuristic, e.g. 4 people fit in 12-person room, but 50-person is too big)
        # Only apply if we have multiple options.
        if len(available_rooms) > 1 and not preferred_room_name:
             good_fits = [r for r in available_rooms if r.capacity <= (attendees * 4)]
             if good_fits:
                 # If we have good fits, only return those.
                 available_rooms = good_fits
        
        return available_rooms

    @staticmethod
    def validate_booking_rules(room: Room, attendees: int, start_time: datetime, end_time: datetime):
        """
        Apply strict business rules.
        Rule: Single-user (or small group) cannot reserve huge room unless no choice.
        """
        threshold = Config.SINGLE_USER_CAPACITY_THRESHOLD
        
        # If request is small but room is huge
        if attendees <= 1 and room.capacity > threshold:
            # Check if there was a "better" room that was available?
            # Actually, the rule says: "unless no other suitable room exists"
            # So we need to check if there are SMALLER rooms available.
            
            # Find all available rooms for this slot
            possible_rooms = BookingService.find_potential_rooms(start_time, end_time, attendees)
            
            # If there is any room in possible_rooms with capacity <= threshold, we should have taken that.
            # If the current 'room' is the only one, then it's allowed.
            
            better_options = [r for r in possible_rooms if r.capacity <= threshold]
            if better_options:
                # If the current room is not in the better options (meaning it's big), reject.
                if room not in better_options:
                     return False, "Optimization Violation: Smaller rooms are available for this request."
        
        return True, "OK"

    @staticmethod
    def create_booking(user, room_id, start_time, end_time, title, attendees=1):
        """
        Main entry point to book a room.
        """
        # 0. Working Hours
        if not BookingService.is_within_working_hours(start_time, end_time):
             raise ValueError("Booking outside of working hours.")

        room = Room.query.get(room_id)
        if not room:
            raise ValueError("Room not found.")

        # 1. Capacity Check
        if room.capacity < attendees:
            raise ValueError(f"Room capacity error: Room holds {room.capacity}, requested {attendees}.")

        # 2. Availability Check (Concurrency note: strict locking needed for high load, using optimistic check for MVP)
        if not BookingService.check_availability(room_id, start_time, end_time):
            raise ValueError("Room is already booked for this interval.")

        # 3. Optimization Rule
        valid, msg = BookingService.validate_booking_rules(room, attendees, start_time, end_time)
        if not valid:
             raise ValueError(msg)

        # 4. Transaction
        booking = Booking(
            user_id=user.id,
            room_id=room.id,
            start_time=start_time,
            end_time=end_time,
            title=title,
            attendees_count=attendees
        )
        db.session.add(booking)
        db.session.commit()
        return booking

    @staticmethod
    def update_booking(booking_id, user_id, start_time=None, end_time=None, attendees=None, room_id=None):
        """
        Modify an existing booking.
        """
        booking = Booking.query.get(booking_id)
        if not booking:
            raise ValueError("Réservation introuvable.")
            
        if booking.user_id != user_id:
            raise ValueError("Non autorisé.")
            
        # Use existing values if not provided
        if not start_time: start_time = booking.start_time
        if not end_time: end_time = booking.end_time
        if not attendees: attendees = booking.attendees_count
        target_room_id = room_id if room_id else booking.room_id
        
        # 0. Working Hours Check
        if not BookingService.is_within_working_hours(start_time, end_time):
             raise ValueError("Les nouveaux horaires sont hors des heures d'ouverture.")

        target_room = Room.query.get(target_room_id)
        if not target_room:
             raise ValueError("Salle introuvable.")
             
        # 1. Capacity Check
        if target_room.capacity < attendees:
             raise ValueError(f"La salle {target_room.name} est trop petite pour {attendees} personnes.")

        # 2. Availability Check (Excluding current booking)
        if not BookingService.check_availability(target_room_id, start_time, end_time, exclude_booking_id=booking_id):
             raise ValueError("La salle est déjà prise sur ce nouveau créneau.")
             
        # 3. Optimization Rule
        valid, msg = BookingService.validate_booking_rules(target_room, attendees, start_time, end_time)
        if not valid:
             raise ValueError(msg)
             
        # Apply updates
        booking.start_time = start_time
        booking.end_time = end_time
        booking.attendees_count = attendees
        booking.room_id = target_room_id
        
        db.session.commit()
        return booking

    @staticmethod
    def get_availabilities(date_str=None, min_capacity=1):
        """
        Return available time slots for all rooms on a specific date (default today).
        """
        from datetime import timedelta # Local import to avoid top-level clutter or circular deps if any
        
        if not date_str:
            target_date = datetime.now().date()
        else:
            try:
                if 'T' in date_str:
                    target_date = datetime.fromisoformat(date_str).date()
                else:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                target_date = datetime.now().date()

        # Define working hours for that day
        start_of_day = datetime.combine(target_date, datetime.min.time()).replace(hour=Config.WORKING_HOURS_START)
        end_of_day = datetime.combine(target_date, datetime.min.time()).replace(hour=Config.WORKING_HOURS_END)
        
        # Get all rooms
        rooms = Room.query.filter(Room.capacity >= min_capacity, Room.is_active == True).all()
        
        results = []
        
        for room in rooms:
            # Get bookings for this room on this day
            bookings = Booking.query.filter(
                Booking.room_id == room.id,
                Booking.status == 'confirmed',
                Booking.start_time >= start_of_day,
                Booking.end_time <= end_of_day
            ).order_by(Booking.start_time).all()
            
            # Calculate free slots (naive approach: find gaps)
            free_slots = []
            current_cursor = start_of_day
            
            # If now is later than start_of_day (and same day), move cursor to now (can't book in past)
            if datetime.now().date() == target_date and datetime.now() > current_cursor:
                 current_cursor = datetime.now()
                 # Round up to next 15 min for cleanliness
                 minute = current_cursor.minute
                 if minute % 15 != 0:
                     add_mins = 15 - (minute % 15)
                     current_cursor += timedelta(minutes=add_mins)
            
            for b in bookings:
                if b.start_time > current_cursor:
                    # Found a gap
                    free_slots.append({
                        "start": current_cursor.strftime("%H:%M"),
                        "end": b.start_time.strftime("%H:%M")
                    })
                current_cursor = max(current_cursor, b.end_time)
            
            # Final gap
            if current_cursor < end_of_day:
                free_slots.append({
                    "start": current_cursor.strftime("%H:%M"),
                    "end": end_of_day.strftime("%H:%M")
                })
            
            if free_slots:
                results.append({
                    "room_name": room.name,
                    "capacity": room.capacity,
                    "slots": free_slots
                })
                
                
        return results

    @staticmethod
    def get_user_bookings(user_id):
        """Get upcoming confirmed bookings for a user and auto-delete expired ones."""
        # 1. Auto-delete expired bookings
        expired_bookings = Booking.query.filter(
            Booking.user_id == user_id,
            Booking.status == 'confirmed',
            Booking.end_time < datetime.now()
        ).all()
        
        if expired_bookings:
            for b in expired_bookings:
                db.session.delete(b)
            db.session.commit()

        # 2. Return valid upcoming bookings
        return Booking.query.filter(
            Booking.user_id == user_id,
            Booking.status == 'confirmed',
            Booking.end_time > datetime.now()
        ).order_by(Booking.start_time).all()

    @staticmethod
    def cancel_booking(booking_id, user_id):
        """Cancel a specific booking if it belongs to user."""
        booking = Booking.query.get(booking_id)
        if not booking:
            return False, "Booking not found."
        
        if booking.user_id != user_id:
            return False, "Unauthorized."
            
        # Update associated events
        for event in booking.event:
            event.booking_id = None
            event.location = ""
            
        booking.status = 'cancelled'
        db.session.commit()
        return True, "Booking cancelled successfully."

    @staticmethod
    def cancel_all_bookings(user_id):
        """Cancel all future confirmed bookings for a user."""
        bookings = Booking.query.filter(
            Booking.user_id == user_id,
            Booking.status == 'confirmed',
            Booking.start_time >= datetime.now()
        ).all()
        
        if not bookings:
            return False, "Aucune réservation à annuler."
            
        count = 0
        for b in bookings:
            # Update associated events
            for event in b.event:
                event.booking_id = None
                event.location = ""
            
            b.status = 'cancelled'
            count += 1
            
        db.session.commit()
        return True, f"{count} réservations annulées."

    @staticmethod
    def get_last_created_booking(user_id):
        """Get the most recently created confirmed booking for a user."""
        return Booking.query.filter(
            Booking.user_id == user_id,
            Booking.status == 'confirmed',
            Booking.end_time > datetime.now()
        ).order_by(Booking.created_at.desc()).first()
