from flask import Blueprint, request, jsonify
from app.services.nlp_service import NLPService
from app.services.booking_service import BookingService
from app.utils.decorators import token_required
from datetime import datetime, timedelta

chat_bp = Blueprint('chat', __name__)

# Simple in-memory context store: { user_id: { 'intent': '...', 'slots': {...} } }
CHAT_CONTEXT = {}

@chat_bp.route('/message', methods=['POST'])
@token_required
def chat(current_user):
    data = request.get_json()
    message = data.get('message', '')
    
    # Retrieve previous context
    user_context = CHAT_CONTEXT.get(current_user.id)
    
    # New NLP Service call (ChatGPT) with context
    intent, slots = NLPService.parse_intent(message, history=user_context)
    
    # Update Context if intent is valid (not UNKNOWN/API_ERROR)
    if intent not in ['UNKNOWN', 'API_ERROR', 'GREETING']:
        CHAT_CONTEXT[current_user.id] = {
            'intent': intent,
            'slots': slots
        }
    
    if intent == 'BOOK_INTENT':
        start_time_str = slots.get('start_time')
        duration = slots.get('duration_minutes')
        attendees = slots.get('attendees', 1)
        equipment = slots.get('equipment', [])
        
        if not start_time_str:
            return jsonify({"response": NLPService.generate_natural_response("Asking for date and time of the booking.")})

        if not duration:
            return jsonify({"response": NLPService.generate_natural_response("Asking for duration of the meeting.")})
            
        try:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = start_time + timedelta(minutes=duration)
        except ValueError:
             return jsonify({"response": NLPService.generate_natural_response("Invalid date format.")})

        # Booking Logic
        rooms = BookingService.find_potential_rooms(start_time, end_time, attendees, required_equipment=equipment)
        
        if not rooms:
            if equipment:
                 ctx = f"No room available for {attendees} people on {start_time.strftime('%d/%m at %H:%M')} with equipment {equipment}."
            else:
                 ctx = f"No room available for {attendees} people on {start_time.strftime('%d/%m at %H:%M')}."
            return jsonify({
                "response": NLPService.generate_natural_response(ctx)
            })
            
        best_room = rooms[0]
        
        # Format equipment string
        eq_str = ""
        if best_room.equipment:
            eq_list = ", ".join(best_room.equipment)
            eq_str = f" (Equipement: {eq_list})"
        
        ctx = f"Found room {best_room.name} (cap {best_room.capacity}){eq_str} for {start_time.strftime('%d/%m at %H:%M')}. Ask user to confirm."
        ai_text = NLPService.generate_natural_response(ctx)
        
        return jsonify({
            "response": ai_text,
            "action_required": "confirm_booking",
            "payload": {
                "room_id": best_room.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendees": attendees
            }
        })

    elif intent == 'QUERY_AVAILABILITY':
        # New Feature: Availability
        start_time_str = slots.get('start_time') # Can be just date
        attendees = slots.get('attendees', 1)
        
        availabilities = BookingService.get_availabilities(start_time_str, min_capacity=attendees)
        
        if not availabilities:
             return jsonify({"response": NLPService.generate_natural_response("No availability found for this day.")})
        
        # Format response text
        # Since the list can be long, we let AI summarize but we output the list below.
        ctx = f"Found {len(availabilities)} available rooms. Present the list to the user."
        ai_text = NLPService.generate_natural_response(ctx)
        
        lines = [ai_text]
        for item in availabilities:
            slots_text = ", ".join([f"{s['start']}-{s['end']}" for s in item['slots']])
            lines.append(f"- **{item['room_name']}** ({item['capacity']}p) : {slots_text}")
            
        return jsonify({"response": "\n".join(lines)})

    elif intent == 'GREETING':
        return jsonify({"response": NLPService.generate_natural_response("User says hello. Greeting checking capabilities (booking, availability).")})
    
    elif intent == 'CANCEL_INTENT':
        start_time_str = slots.get('start_time')
        scope = slots.get('scope', 'SINGLE')
        
        # Get all bookings
        bookings = BookingService.get_user_bookings(current_user.id)
        
        if not bookings:
            return jsonify({"response": "Vous n'avez aucune réservation à venir."})

        # Check for Mass Cancellation
        if scope == 'ALL':
             return jsonify({
                "response": f"Voulez-vous vraiment annuler TOUTES vos {len(bookings)} réservations ?",
                "action_required": "confirm_cancel_all",
                "payload": {}
            })
        
        if scope == 'LAST':
             last_booking = BookingService.get_last_created_booking(current_user.id)
             if not last_booking:
                 return jsonify({"response": NLPService.generate_natural_response("You have no bookings to cancel.")})
             
             start_fmt = last_booking.start_time.strftime('%d/%m à %H:%M')
             ctx = f"Found the last booking: Room {last_booking.room_id} on {start_fmt}. Ask user to confirm cancellation."
             ai_text = NLPService.generate_natural_response(ctx)
             
             return jsonify({
                 "response": ai_text,
                 "action_required": "confirm_cancel",
                 "payload": { "booking_id": last_booking.id }
             })
        
        # Filter if date provided
        candidates = bookings
        if start_time_str:
            try:
                target_date = datetime.fromisoformat(start_time_str).date()
                candidates = [b for b in bookings if b.start_time.date() == target_date]
            except ValueError:
                pass # Ignore invalid date filter
        
        if len(candidates) == 0:
             return jsonify({"response": NLPService.generate_natural_response("User asked to cancel a booking on this date, but no bookings were found.")})
             
        if len(candidates) == 1:
            b = candidates[0]
            start_fmt = b.start_time.strftime('%d/%m à %H:%M')
            # Generate Text
            ctx = f"Found one booking to cancel: Room {b.room_id} on {start_fmt}. Ask user to confirm cancellation."
            ai_text = NLPService.generate_natural_response(ctx)
            
            return jsonify({
                "response": ai_text,
                "action_required": "confirm_cancel",
                "payload": { "booking_id": b.id }
            })
            
        else:
            # Multiple candidates
            lines = []
            for b in candidates:
                start_fmt = b.start_time.strftime('%d/%m à %H:%M')
                lines.append(f"- Salle {b.room_id} le {start_fmt} (ID: {b.id})")
            
            list_str = "\n".join(lines)
            ctx = f"Found multiple bookings: \n{list_str}\n. Ask user to specify which one to cancel or if they want to cancel all (toutes)."
            ai_text = NLPService.generate_natural_response(ctx)
            
            # Append the technical list to the AI text so it's accurate and visible
            final_response = f"{ai_text}\n\n{list_str}"
            
            return jsonify({"response": final_response})

    elif intent == 'API_ERROR':
        error_msg = slots.get('error', 'Erreur inconnue')
        return jsonify({"response": f"⚠️ Une erreur technique est survenue avec l'IA : {error_msg}. Veuillez réessayer plus tard."})

    else:
        # UNKNOWN Fallback
        # Ask AI to generate a polite "I didn't understand" message
        ai_text = NLPService.generate_natural_response("User said something I didn't understand. Ask them to rephrase request (booking or cancellation).")
        return jsonify({"response": ai_text})

@chat_bp.route('/context', methods=['DELETE'])
@token_required
def clear_context(current_user):
    if current_user.id in CHAT_CONTEXT:
        del CHAT_CONTEXT[current_user.id]
    return jsonify({"message": "Context cleared"}), 200
