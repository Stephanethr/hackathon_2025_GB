from flask import Blueprint, request, jsonify
from app.services.booking_service import BookingService
from app.utils.decorators import token_required
from app.models import Booking
from datetime import datetime

bookings_bp = Blueprint('bookings', __name__)

@bookings_bp.route('/', methods=['POST'])
@token_required
def create_booking(current_user):
    data = request.get_json()
    try:
        start = datetime.fromisoformat(data['start_time'])
        end = datetime.fromisoformat(data['end_time'])
        
        booking = BookingService.create_booking(
            user=current_user,
            room_id=data['room_id'],
            start_time=start,
            end_time=end,
            title=data.get('title', 'Meeting'),
            attendees=data.get('attendees', 1)
        )
        
        if 'event_id' in data:
            from app.services.calendar_service import CalendarService
            CalendarService.link_event_to_booking(data['event_id'], booking.id)
            
        return jsonify(booking.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Server Error', 'details': str(e)}), 500

@bookings_bp.route('/<int:booking_id>', methods=['PUT'])
@token_required
def update_booking(current_user, booking_id):
    data = request.get_json()
    try:
        start = datetime.fromisoformat(data['start_time'])
        end = datetime.fromisoformat(data['end_time'])
        
        booking = BookingService.update_booking(
            booking_id=booking_id,
            user_id=current_user.id,
            room_id=data.get('room_id'),
            start_time=start,
            end_time=end,
            attendees=data.get('attendees')
        )
        return jsonify(booking.to_dict()), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Server Error', 'details': str(e)}), 500

@bookings_bp.route('/my_bookings', methods=['GET'])
@token_required
def get_my_bookings(current_user):
    bookings = BookingService.get_user_bookings(current_user.id)
    return jsonify([b.to_dict() for b in bookings])

@bookings_bp.route('/<int:booking_id>', methods=['DELETE'])
@token_required
def delete_booking(current_user, booking_id):
    success, message = BookingService.cancel_booking(booking_id, current_user.id)
    if success:
        return jsonify({'message': message}), 200
    else:
        # Determine if 404 or 403 based on message, but simple 400 is fine for MVP
        status_code = 404 if 'not found' in message else 403
        return jsonify({'error': message}), status_code

@bookings_bp.route('/batch', methods=['DELETE'])
@token_required
def delete_all_bookings(current_user):
    success, message = BookingService.cancel_all_bookings(current_user.id)
    if success:
         return jsonify({'message': message}), 200
    else:
         return jsonify({'error': message}), 400
