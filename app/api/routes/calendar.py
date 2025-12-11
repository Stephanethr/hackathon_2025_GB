from flask import Blueprint, request, jsonify, current_app
from app.models import User
from app.extensions import db
from app.services.calendar_service import CalendarService
import jwt

calendar_bp = Blueprint('calendar', __name__)

def get_auth_user():
    token = None
    if 'Authorization' in request.headers:
        token = request.headers['Authorization'].split(" ")[1]
    
    if not token:
        return None
        
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
        return User.query.get(data['user_id'])
    except:
        return None

@calendar_bp.route('/events', methods=['GET'])
def get_events():
    user = get_auth_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401
        
    events = CalendarService.fetch_user_events(user)
    return jsonify(events)

@calendar_bp.route('/settings', methods=['POST'])
def update_settings():
    user = get_auth_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    ics_url = data.get('ics_url')
    
    # Simple validation
    if ics_url and not ics_url.startswith('http'):
         return jsonify({'message': 'Invalid URL'}), 400
         
    user.ics_url = ics_url
    db.session.commit()
    
    return jsonify({'message': 'Settings updated', 'ics_url': user.ics_url})

@calendar_bp.route('/settings', methods=['GET'])
def get_settings():
    user = get_auth_user()
    if not user:
        return jsonify({'message': 'Unauthorized'}), 401
        
    return jsonify({'ics_url': user.ics_url})
