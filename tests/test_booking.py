import pytest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Room, Booking
from app.services.booking_service import BookingService
from app.config import TestingConfig

@pytest.fixture
def app():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def init_data(app):
    user = User(username='test', email='test@test.com', role='user')
    room_small = Room(name='Small', capacity=4)
    room_large = Room(name='Large', capacity=20)
    db.session.add_all([user, room_small, room_large])
    db.session.commit()
    return user, room_small, room_large

def test_booking_happy_path(app, init_data):
    user, room_small, _ = init_data
    start = datetime.now().replace(hour=10, minute=0)
    end = start + timedelta(hours=1)
    
    booking = BookingService.create_booking(user, room_small.id, start, end, "Meeting", 2)
    assert booking.id is not None
    assert booking.status == 'confirmed'

def test_booking_conflict(app, init_data):
    user, room_small, _ = init_data
    start = datetime.now().replace(hour=10, minute=0)
    end = start + timedelta(hours=1)
    
    BookingService.create_booking(user, room_small.id, start, end, "Meeting 1", 2)
    
    with pytest.raises(ValueError, match="already booked"):
        BookingService.create_booking(user, room_small.id, start, end, "Meeting 2", 2)

def test_optimization_rule_violation(app, init_data):
    """Test that a single user cannot book a large room if a small one is available."""
    user, room_small, room_large = init_data
    start = datetime.now().replace(hour=14, minute=0)
    end = start + timedelta(hours=1)
    
    # Try to book Large room for 1 person, while Small is free
    # Should fail because Small (4 cap) is better than Large (20 cap) for 1 person (Threshold default 6)
    
    with pytest.raises(ValueError, match="Optimization Violation"):
         BookingService.create_booking(user, room_large.id, start, end, "Solo Work", 1)

def test_optimization_rule_allowed_if_no_choice(app, init_data):
    """Test that a single user CAN book a large room if the small one is taken."""
    user, room_small, room_large = init_data
    start = datetime.now().replace(hour=14, minute=0)
    end = start + timedelta(hours=1)
    
    # 1. Book the small room first
    BookingService.create_booking(user, room_small.id, start, end, "Other Meeting", 3)
    
    # 2. Now try to book Large for 1 person
    # Small is taken, so Large is the only choice. Should be allowed.
    booking = BookingService.create_booking(user, room_large.id, start, end, "Solo Work", 1)
    assert booking.id is not None
