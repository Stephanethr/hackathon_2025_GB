from flask import Blueprint, request, jsonify, current_app
from app.utils.decorators import token_required, admin_required
from app.models import User, Room
from app.extensions import db
from werkzeug.security import generate_password_hash
import traceback

admin_bp = Blueprint('admin', __name__)

# --- USERS MANAGEMENT ---

@admin_bp.route('/users', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    users = User.query.all()
    return jsonify([u.to_dict() for u in users]), 200

@admin_bp.route('/users', methods=['POST'])
@token_required
@admin_required
def create_user(current_user):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No input data provided'}), 400
            
        if User.query.filter_by(username=data.get('username')).first():
            return jsonify({'message': 'Username already exists'}), 400
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'message': 'Email already exists'}), 400
        
        if not data.get('password'):
            return jsonify({'message': 'Password is required'}), 400
            
        hashed_password = generate_password_hash(data.get('password'))
        new_user = User(
            username=data.get('username'),
            email=data.get('email'),
            password_hash=hashed_password,
            role=data.get('role', 'user')
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully', 'user': new_user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating user: {e}\n{traceback.format_exc()}")
        return jsonify({'message': 'Internal Server Error', 'error': str(e), 'trace': traceback.format_exc()}), 500

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
        
    data = request.get_json()
    if 'username' in data:
        user.username = data['username']
    if 'email' in data:
        user.email = data['email']
    if 'role' in data:
        user.role = data['role']
    if 'password' in data and data['password']:
        user.password_hash = generate_password_hash(data['password'])
        
    db.session.commit()
    return jsonify({'message': 'User updated', 'user': user.to_dict()}), 200

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    # Prevent deleting yourself
    if user.id == current_user.id:
        return jsonify({'message': 'Cannot delete yourself'}), 400
        
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted'}), 200


# --- ROOMS MANAGEMENT ---

@admin_bp.route('/rooms', methods=['GET'])
@token_required
@admin_required
def get_rooms(current_user):
    rooms = Room.query.all()
    return jsonify([r.to_dict() for r in rooms]), 200

@admin_bp.route('/rooms', methods=['POST'])
@token_required
@admin_required
def create_room(current_user):
    data = request.get_json()
    if Room.query.filter_by(name=data.get('name')).first():
        return jsonify({'message': 'Room name already exists'}), 400
        
    new_room = Room(
        name=data.get('name'),
        capacity=data.get('capacity'),
        equipment=data.get('equipment', []),
        is_active=data.get('is_active', True)
    )
    db.session.add(new_room)
    db.session.commit()
    return jsonify({'message': 'Room created', 'room': new_room.to_dict()}), 201

@admin_bp.route('/rooms/<int:room_id>', methods=['PUT'])
@token_required
@admin_required
def update_room(current_user, room_id):
    room = Room.query.get(room_id)
    if not room:
        return jsonify({'message': 'Room not found'}), 404
        
    data = request.get_json()
    if 'name' in data:
        room.name = data['name']
    if 'capacity' in data:
        room.capacity = data['capacity']
    if 'equipment' in data:
        room.equipment = data['equipment']
    if 'is_active' in data:
        room.is_active = data['is_active']
        
    db.session.commit()
    return jsonify({'message': 'Room updated', 'room': room.to_dict()}), 200

@admin_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_room(current_user, room_id):
    room = Room.query.get(room_id)
    if not room:
        return jsonify({'message': 'Room not found'}), 404
        
    # Hard delete or Soft delete? Requirement says "supprimer".
    # If there are bookings, foreign key might fail. 
    # For MVP, try delete. if error, maybe warn.
    try:
        db.session.delete(room)
        db.session.commit()
        return jsonify({'message': 'Room deleted'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Cannot delete room (likely has bookings)', 'error': str(e)}), 400
