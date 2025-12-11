from flask import Blueprint, request, jsonify, current_app
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)



@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    
    if not user or not check_password_hash(user.password_hash, data.get('password')):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, current_app.config['SECRET_KEY'], algorithm="HS256")
    
    return jsonify({'token': token, 'username': user.username, 'role': user.role})
