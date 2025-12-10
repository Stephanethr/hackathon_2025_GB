from app import create_app, db
from app.models import User, Room
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    db.create_all()
    
    # Create Admin
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@workspace.com',
            password_hash=generate_password_hash('password', method='pbkdf2:sha256'),
            role='admin'
        )
        db.session.add(admin)
        print("Admin created (admin/password)")

    # Create Rooms
    rooms_data = [
        {"name": "Salle Alpha", "capacity": 4, "equipment": ["tv"]},
        {"name": "Salle Beta", "capacity": 10, "equipment": ["projector", "whiteboard"]},
        {"name": "Auditorium", "capacity": 50, "equipment": ["sound_system", "stage"]},
        {"name": "Focus Room 1", "capacity": 1, "equipment": ["desk"]}
    ]
    
    for r_data in rooms_data:
        if not Room.query.filter_by(name=r_data['name']).first():
            room = Room(name=r_data['name'], capacity=r_data['capacity'], equipment=r_data['equipment'])
            db.session.add(room)
            print(f"Room {room.name} created.")
            
    db.session.commit()
    print("Database seeded successfully.")
