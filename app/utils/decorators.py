from functools import wraps
from flask import request, jsonify, current_app
import jwt
from app.models.user import User

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            # Bearer <token>
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                 raise Exception("User not found")
        except Exception as e:
            return jsonify({'message': 'Token is invalid!', 'error': str(e)}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # reuse logic or stack decorators. 
        # For simplicity, assuming token_required is used before or logic duplicated (cleaner to stack)
        # But `token_required` passes `current_user` to the view.
        # So this must be used like: @token_required \n @admin_required
        
        # Actually standard flask pattern:
        # def view(current_user): ...
        # admin check relies on current_user passed by token_required
        
        current_user = args[0] # Assumes token_required passing it as first arg
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin privilege required'}), 403
        return f(*args, **kwargs)
    return decorated
