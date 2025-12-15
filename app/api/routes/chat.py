from flask import Blueprint, request, jsonify, Response, stream_with_context
from app.services.nlp_service import NLPService
from app.services.booking_service import BookingService
from app.services.calendar_service import CalendarService
from app.utils.decorators import token_required
from datetime import datetime, timedelta
import json
from app.models import Booking, Room
from app.config import Config
import unicodedata

chat_bp = Blueprint('chat', __name__)

# Simple in-memory context store: { user_id: { 'intent': '...', 'slots': {...} } }
CHAT_CONTEXT = {}

@chat_bp.route('/message', methods=['POST'])
@token_required
def chat(current_user):
    data = request.get_json()
    message = data.get('message', '')
    
    # Retrieve previous context
    if current_user.id not in CHAT_CONTEXT:
        CHAT_CONTEXT[current_user.id] = {'messages': [], 'slots': {}, 'intent': None}
    
    user_context = CHAT_CONTEXT[current_user.id]

    # Ensure context structure integrity
    if 'messages' not in user_context:
        user_context['messages'] = []
    if 'slots' not in user_context:
        user_context['slots'] = {}
        
    history = user_context.get('messages', [])
    
    # New NLP Service call (ChatGPT) with history
    # Note: We pass the history of PREVIOUS messages. The current message is added inside parse_intent temporarily for the call,
    # but we must persist it to history manually after.
    intent, slots = NLPService.parse_intent(message, history=history)
    
    # Persist User Message + Assistant NLU State
    user_context['messages'].append({"role": "user", "content": message})
    user_context['messages'].append({"role": "assistant", "content": json.dumps({"intent": intent, "slots": slots})})
    
    # Update Slots State
    if intent not in ['UNKNOWN', 'API_ERROR', 'GREETING']:
        user_context['intent'] = intent
        # Merge slots? The NLU now returns FULL STATE usually.
        # But if it returns partial, we might lose data. 
        # The prompt says "Merge new info... Return the FULL STATE". 
        # So we can overwrite.
        user_context['slots'] = slots

    # Helper to save verbal response
    def save_verbal_response(text):
        user_context['messages'].append({"role": "assistant", "content": text})
    
    # Common args via partial? No, just pass lambda.
    stream_args = {'on_complete': save_verbal_response}

    def respond(context_text, payload_data=None):
        return Response(NLPService.generate_response_stream(context_text, payload_data, **stream_args), mimetype='application/x-ndjson')

    if intent == 'BOOK_INTENT':
        start_time_str = slots.get('start_time')
        duration = slots.get('duration_minutes')
        attendees = slots.get('attendees') # Can be None now
        equipment = slots.get('equipment', [])
        room_name = slots.get('room_name')
        excluded_rooms = slots.get('excluded_rooms', [])
        
        # 1. Check Mandatory Slots
        missing_fields = []
        if not start_time_str:
            missing_fields.append("la date/heure")
        if not attendees:
            missing_fields.append("le nombre de personnes")
        if not duration:
            missing_fields.append("la durée")

        if missing_fields:
            # Check for unbooked event
            next_event = None
            target_dt = None
            
            if start_time_str:
                 # User specified a date/time. Let's see if there is an unbooked event ON THAT DATE.
                 try:
                     target_dt = datetime.fromisoformat(start_time_str)
                     next_event = CalendarService.get_next_unbooked_event(current_user, date_filter=target_dt)
                 except ValueError:
                     pass
            else:
                 # User didn't specify a date, so we proactively look for the NEXT unbooked event in general.
                 next_event = CalendarService.get_next_unbooked_event(current_user)
            
            if next_event:
                 # Check strict time matching if specific time provided (not midnight default)
                 # target_dt is the user requested time (e.g. 17:00)
                 if target_dt and (target_dt.hour != 0 or target_dt.minute != 0):
                     # Convert event to local naive for comparison
                     ev_local = next_event.start_time
                     if ev_local.tzinfo:
                         ev_local = ev_local.astimezone(None)
                     ev_local = ev_local.replace(tzinfo=None)
                     
                     # Tolerance: 2.5 hours (9000s). 
                     # If I ask 17h and event is 9h -> Diff 8h -> Ignore.
                     # If I ask 17h and event is 17h30 -> Diff 30m -> Keep.
                     if abs((ev_local - target_dt).total_seconds()) > 9000:
                         next_event = None

            if next_event:
                 # Determine effective attendees
                 # If user provided attendees (in slots), use it caused it valid. Otherwise use event default.
                 effective_attendees = slots.get('attendees') or next_event.attendee_count
                 if not effective_attendees: effective_attendees = 1

                 # Proactive Proposal
                 candidates = BookingService.find_potential_rooms(next_event.start_time, next_event.end_time, effective_attendees)
                 if candidates:
                     room = candidates[0]
                     
                     # Determine proposal times
                     # If user requested a specific time (target_dt is set and not 00:00), use it.
                     # Otherwise, fallback to event time.
                     proposal_start = next_event.start_time
                     if target_dt and (target_dt.hour != 0 or target_dt.minute != 0):
                         proposal_start = target_dt
                     
                     # Determine duration
                     # If user specified duration, use it. Else use event duration.
                     event_duration = next_event.end_time - next_event.start_time
                     proposal_end = proposal_start + event_duration
                     
                     if slots.get('duration_minutes'):
                         proposal_end = proposal_start + timedelta(minutes=slots.get('duration_minutes'))

                     msg = f"Je vois que vous avez un événement '{next_event.summary}' le {next_event.start_time.strftime('%d/%m à %H:%M')}."
                     
                     # Add clarification if we are proposing a DIFFERENT time than the event
                     if proposal_start != next_event.start_time:
                         msg += f" (Je réserve pour {proposal_start.strftime('%H:%M')} comme demandé)."
                         
                     if slots.get('attendees'):
                         msg += f" Pour {effective_attendees} personnes (selon votre demande)."
                     else:
                         msg += f" ({effective_attendees} pers. prévues)."
                     
                     msg += f" La salle **{room.name}** est disponible. Voulez-vous la réserver ?"
                     
                     payload = {
                        "action_required": "confirm_booking",
                        "payload": {
                            "room_id": room.id,
                            "start_time": proposal_start.isoformat(),
                            "end_time": proposal_end.isoformat(),
                            "attendees": effective_attendees,
                            "title": next_event.summary,
                            "event_id": next_event.id
                        }
                     }
                     return respond(msg, payload)

            if len(missing_fields) == 1:
                return respond(f"User wants to book but didn't specify {missing_fields[0]}. Ask for it.")
            else:
                fields_str = ", ".join(missing_fields)
                return respond(f"User wants to book but is missing details: {fields_str}. Ask for all of them.")
            
        try:
            start_time = datetime.fromisoformat(start_time_str)
            
            # Check for generic working hours or midnight default
            # Use strict comparison for start hour
            if start_time.hour < Config.WORKING_HOURS_START or start_time.hour >= Config.WORKING_HOURS_END:
                # If specific case 00:00, it's likely missing time
                if start_time.hour == 0 and start_time.minute == 0:
                     return respond(f"User specified date but likely not time. Ask for time between {Config.WORKING_HOURS_START}h and {Config.WORKING_HOURS_END}h.")
                else:
                     return respond(f"Requested time {start_time.strftime('%H:%M')} is outside working hours ({Config.WORKING_HOURS_START}h-{Config.WORKING_HOURS_END}h). Ask user to pick a valid time.")

            end_time = start_time + timedelta(minutes=duration)
        except ValueError:
             return respond("Date format error. Ask user to repeat date.")

        # Booking Logic
        rooms = BookingService.find_potential_rooms(
            start_time, 
            end_time, 
            attendees, 
            required_equipment=equipment, 
            preferred_room_name=room_name,
            excluded_room_names=excluded_rooms
        )
        
        if not rooms:
            # Proactive suggestions & Diagnosis
            alternatives = BookingService.get_availabilities(start_time.strftime("%Y-%m-%d"), min_capacity=attendees)
            
            ctx = f"User wanted to book for {attendees} people on {start_time.strftime('%d/%m at %H:%M')}.\n"
            if equipment:
                ctx += f"Equipment required: {', '.join(equipment)}.\n"
            
            # --- DIAGNOSIS FOR SPECIFIC ROOM REQUEST ---
            diagnosis_msg = ""
            if room_name:
                # User asked for a specific room, but it wasn't returned using find_potential_rooms.
                # Let's find out why.
                # 1. Find the room by loosely matching name again (manual or simple query)
                all_rooms = Room.query.all()
                target_room = next((r for r in all_rooms if room_name.lower() in r.name.lower()), None)
                
                if not target_room:
                     diagnosis_msg = f"The requested room '{room_name}' does not exist.\n"
                else:
                    # Check Capacity
                    if target_room.capacity < attendees:
                        diagnosis_msg = f"The requested room '{target_room.name}' is too small (Capacity {target_room.capacity} vs Requested {attendees}).\n"
                    # Check Availability
                    elif not BookingService.check_availability(target_room.id, start_time, end_time):
                        diagnosis_msg = f"The requested room '{target_room.name}' is already booked during this time.\n"
                    # Check Equipment?
                    elif equipment:
                         diagnosis_msg = f"The requested room '{target_room.name}' does not have the required equipment.\n"
                    else:
                         diagnosis_msg = f"The requested room '{target_room.name}' is unavailable for an unknown reason.\n"

            if diagnosis_msg:
                 ctx += f"Outcome: {diagnosis_msg}"
            else:
                 ctx += "Outcome: No exact match found.\n"
            
            if alternatives:
                ctx += "Alternatives found for the same day (Present these clearly):\n"
                for item in alternatives:
                    slots_text = ", ".join([f"{s['start']}-{s['end']}" for s in item['slots']])
                    ctx += f"- {item['room_name']} ({item['capacity']}p): {slots_text}\n"
            else:
                ctx += "No other availabilities found for this day."
            
            return respond(ctx)
            
        best_room = rooms[0]

        # COHERENCE CHECK
        if not BookingService.is_capacity_coherent(best_room.capacity, attendees) and not room_name:
            alternatives = BookingService.get_availabilities(start_time.strftime("%Y-%m-%d"), min_capacity=attendees)
            coherent_alts = [alt for alt in alternatives if BookingService.is_capacity_coherent(alt['capacity'], attendees)]
             
            if coherent_alts:
                ctx = f"User wanted to book for {attendees} people at {start_time.strftime('%H:%M')}.\n"
                ctx += f"Only available room at that time is {best_room.name} ({best_room.capacity}p) which is too large (incoherent).\n"
                ctx += "Better alternatives found for the day (Suggest these):\n"
                for item in coherent_alts:
                    slots_text = ", ".join([f"{s['start']}-{s['end']}" for s in item['slots']])
                    ctx += f"- {item['room_name']} ({item['capacity']}p): {slots_text}\n"
                
                return respond(ctx)

        # Format equipment string
        eq_str = ""
        if best_room.equipment:
            eq_list = ", ".join(best_room.equipment)
            eq_str = f" (Equipement: {eq_list})"
        
        ctx = f"Found room {best_room.name} (cap {best_room.capacity}){eq_str} for {start_time.strftime('%d/%m at %H:%M')}. Ask user to confirm."
        
        payload = {
            "action_required": "confirm_booking",
            "payload": {
                "room_id": best_room.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendees": attendees
            }
        }
        return respond(ctx, payload)

    elif intent == 'QUERY_AVAILABILITY':
        start_time_str = slots.get('start_time')
        attendees = slots.get('attendees') or 1
        
        availabilities = BookingService.get_availabilities(start_time_str, min_capacity=attendees)
        
        ctx = f"User asked for availability (Attendees: {attendees}).\n"
        if not availabilities:
             ctx += "Outcome: No availability found for this day."
        else:
             ctx += f"Found {len(availabilities)} available rooms. List:\n"
             for item in availabilities:
                slots_text = ", ".join([f"{s['start']}-{s['end']}" for s in item['slots']])
                ctx += f"- {item['room_name']} ({item['capacity']}p): {slots_text}\n"

        return respond(ctx)

    elif intent == 'ROOM_INFO':
        room_name = slots.get('room_name')
        
        if room_name:
            # Search for specific room with normalization
            all_rooms = Room.query.all()
            
            def normalize(t):
                 return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').lower()
            
            target_room = next((r for r in all_rooms if normalize(room_name) in normalize(r.name)), None)
            
            if target_room:
                 eq_list = ", ".join(target_room.equipment) if target_room.equipment else "Aucun"
                 return respond(f"La salle **{target_room.name}** a une capacité de {target_room.capacity} personnes. Équipements : {eq_list}.")
            else:
                 # Try to list close matches?
                 return respond(f"Je ne trouve pas la salle '{room_name}'.")
        else:
            # List all rooms
            rooms = Room.query.filter_by(is_active=True).all()
            info = "Voici les salles disponibles :\n"
            for r in rooms:
                 eq_list = ", ".join(r.equipment) if r.equipment else "Standard"
                 info += f"- **{r.name}** : {r.capacity} pers. ({eq_list})\n"
            return respond(info)

    elif intent == 'GREETING':
        return respond("User says hello. Greeting checking capabilities (booking, availability).")
    
    elif intent == 'CANCEL_INTENT':
        start_time_str = slots.get('start_time')
        scope = slots.get('scope', 'SINGLE')
        bookings = BookingService.get_user_bookings(current_user.id)
        
        if not bookings:
            return respond("User wants to cancel, but has no upcoming bookings.")

        if scope == 'ALL':
             payload = {"action_required": "confirm_cancel_all", "payload": {}}
             return respond(f"User wants to cancel ALL {len(bookings)} bookings. Ask specifically for confirmation.", payload)
        
        if scope == 'LAST':
             last_booking = BookingService.get_last_created_booking(current_user.id)
             if not last_booking:
                 return respond("User wants to cancel last booking, but none found.")
             
             start_fmt = last_booking.start_time.strftime('%d/%m à %H:%M')
             ctx = f"Found the last booking: Room {last_booking.room.name} on {start_fmt}. Ask user to confirm cancellation."
             payload = {"action_required": "confirm_cancel", "payload": { "booking_id": last_booking.id }}
             return respond(ctx, payload)
        
        candidates = bookings
        if start_time_str:
            try:
                target_date = datetime.fromisoformat(start_time_str).date()
                candidates = [b for b in bookings if b.start_time.date() == target_date]
            except ValueError:
                pass
        
        if len(candidates) == 0:
             return respond("User asked to cancel a booking on this date, but no bookings were found.")
             
        if len(candidates) == 1:
            b = candidates[0]
            start_fmt = b.start_time.strftime('%d/%m à %H:%M')
            ctx = f"Found one booking to cancel: Room {b.room.name} on {start_fmt}. Ask user to confirm cancellation."
            payload = {"action_required": "confirm_cancel", "payload": { "booking_id": b.id }}
            return respond(ctx, payload)
            
        else:
            ctx = f"Found multiple bookings to cancel. Ask user to specify which one.\nList:\n"
            for b in candidates:
                start_fmt = b.start_time.strftime('%d/%m à %H:%M')
                ctx += f"- ID {b.id}: Salle {b.room.name} le {start_fmt}\n"
            
            return respond(ctx)

    elif intent == 'MODIFY_INTENT':
        # Retrieve target booking
        # 1. Check if specific booking ID is in slots (unlikely for NLP to get ID unless user says it, but maybe via context?)
        # 2. Check context for 'last_confirmed_booking_id'
        target_booking_id = user_context.get('last_confirmed_booking_id') if user_context else None
        
        # 3. Fallback to actual last booking in DB if allowed
        if not target_booking_id:
            last_booking = BookingService.get_last_created_booking(current_user.id)
            if last_booking:
                target_booking_id = last_booking.id
        
        if not target_booking_id:
             return respond("User wants to modify a booking but I can't find any recent booking to modify.")

        # Get the current booking details
        booking = Booking.query.get(target_booking_id)
        if not booking:
            return respond("Booking not found.")

        # Merge slots: New slots OVERWRITE existing booking details for the check
        new_start_time = booking.start_time
        new_end_time = booking.end_time
        new_attendees = booking.attendees_count
        new_room_id = booking.room_id # We might change room if needed
        
        # Updates from Slots
        updated_something = False
        
        if slots.get('start_time'):
            try:
                new_start_time = datetime.fromisoformat(slots.get('start_time'))
                # Re-calculate end time if duration is not specified but start time changed? 
                # If duration is in slots, use it. If not, preserve DURATION or preserve END TIME?
                # Usually preserve duration.
                current_duration = booking.end_time - booking.start_time
                if slots.get('duration_minutes'):
                     new_end_time = new_start_time + timedelta(minutes=slots.get('duration_minutes'))
                else:
                     new_end_time = new_start_time + current_duration
                updated_something = True
            except:
                pass

        if slots.get('attendees'):
            new_attendees = slots.get('attendees')
            updated_something = True
            
        if slots.get('duration_minutes') and not slots.get('start_time'):
             # Just duration change
             new_end_time = new_start_time + timedelta(minutes=slots.get('duration_minutes'))
             updated_something = True

        # Check for room suitability if attendees changed or room_name requested
        preferred_room_name = slots.get('room_name')
        
        if updated_something or preferred_room_name:
             # Reprocess finding a room logic similar to BOOK_INTENT but specifically for this update
             # We want to see if 'new_room_id' (current room) is still valid, OR if we need to switch.
             
             # If user specifically requested a new room name:
             if preferred_room_name:
                  candidates = BookingService.find_potential_rooms(new_start_time, new_end_time, new_attendees, preferred_room_name=preferred_room_name, exclude_booking_id=target_booking_id)
                  if candidates:
                       new_room_id = candidates[0].id
                  else:
                       return respond(f"Modification impossible: la salle '{preferred_room_name}' n'est pas disponible.")
             else:
                  # Check if current room still fits capacity
                  current_room = Room.query.get(new_room_id)
                  if current_room.capacity < new_attendees:
                       # Need to find a new room
                       candidates = BookingService.find_potential_rooms(new_start_time, new_end_time, new_attendees, exclude_booking_id=target_booking_id)
                       if candidates:
                            new_room_id = candidates[0].id
                       else:
                             return respond("Modification impossible: aucune salle assez grande disponible.")
                  
                  # Check availability of the (potentially same) room
                  if not BookingService.check_availability(new_room_id, new_start_time, new_end_time, exclude_booking_id=target_booking_id):
                       # Conflict. Try find another room?
                       candidates = BookingService.find_potential_rooms(new_start_time, new_end_time, new_attendees, exclude_booking_id=target_booking_id)
                       if candidates:
                            new_room_id = candidates[0].id
                       else:
                              return respond("Modification impossible: le créneau n'est plus disponible.")

             # Generate Confirmation Request
             room = Room.query.get(new_room_id)
             ctx = f"Propose modification of booking {target_booking_id}. New details: Room {room.name}, {new_start_time.strftime('%d/%m %H:%M')}, {new_attendees} pax. Ask confirm."
             
             # Payload for update
             payload = {
                 "action_required": "confirm_modification",
                 "payload": {
                     "booking_id": target_booking_id,
                     "room_id": new_room_id,
                     "start_time": new_start_time.isoformat(),
                     "end_time": new_end_time.isoformat(),
                     "attendees": new_attendees
                 }
             }
             return respond(ctx, payload)

        else:
             return respond("User wants to modify, but didn't specify what to change.")


    elif intent == 'API_ERROR':
        error_msg = slots.get('error', 'Erreur inconnue')
        return respond(f"Technichal Error: {error_msg}")

    else:
        # UNKNOWN Fallback
        # Ask AI to generate a polite "I didn't understand" message
        return respond("User said something unclear. Ask to rephrase.")

@chat_bp.route('/context', methods=['DELETE'])
@token_required
def clear_context(current_user):
    if current_user.id in CHAT_CONTEXT:
        del CHAT_CONTEXT[current_user.id]
    return jsonify({"message": "Context cleared"}), 200

@chat_bp.route('/context/last_booking', methods=['POST'])
@token_required
def update_context_last_booking(current_user):
    data = request.get_json()
    booking_id = data.get('booking_id')
    
    if current_user.id not in CHAT_CONTEXT:
        CHAT_CONTEXT[current_user.id] = {'messages': [], 'slots': {}, 'intent': None}
        
    CHAT_CONTEXT[current_user.id]['last_confirmed_booking_id'] = booking_id
    # Reset intent but keep last booking reference
    CHAT_CONTEXT[current_user.id]['intent'] = None
    CHAT_CONTEXT[current_user.id]['slots'] = {}
    
    return jsonify({"message": "Context updated with last booking"}), 200

@chat_bp.route('/greeting', methods=['GET'])
@token_required
def get_greeting(current_user):
    # Proactive check for unbooked next meeting
    next_event = CalendarService.get_next_unbooked_event(current_user)
    
    if next_event:
        # Check if we have rooms available for this event
        candidates = BookingService.find_potential_rooms(next_event.start_time, next_event.end_time, next_event.attendee_count or 1)
        if candidates:
            # We have a suggestion!
            # Format friendly message
            room = candidates[0]
            start_str = next_event.start_time.strftime('%H:%M')
            if next_event.start_time.date() != datetime.now().date():
                start_str = next_event.start_time.strftime('%d/%m à %H:%M')
                
            msg = f"Bonjour ! Je vois que vous avez une réunion '{next_event.summary}' prévue à {start_str} sans salle réservée. La salle **{room.name}** est disponible. Souhaitez-vous que je la réserve ?"
            
            # We can also attach a payload for quick action if we wanted, 
            # but for the greeting we usually just return text first, OR we return a rich object.
            # The frontend expects just text or maybe we can return the same structure as chat?
            # Let's return a JSON structure that the frontend can parse.
            
            payload = {
                "action_required": "confirm_booking",
                "payload": {
                    "room_id": room.id,
                    "start_time": next_event.start_time.isoformat(),
                    "end_time": next_event.end_time.isoformat(),
                    "attendees": next_event.attendee_count or 1,
                    "title": next_event.summary,
                    "event_id": next_event.id
                }
            }
            
            return jsonify({
                "message": msg,
                "type": "suggestion", 
                "data": payload
            })

    # Default greeting
    return jsonify({
        "message": "Bonjour ! Comment puis-je vous aider ?",
        "type": "greeting",
        "data": None
    })
