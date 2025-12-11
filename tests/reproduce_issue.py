import unittest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.models import Room, User
from app.config import TestingConfig
from app.services.nlp_service import NLPService
import json
import jwt

class TestChatImprovements(unittest.TestCase):
    def setUp(self):
        self.app = create_app(config_class=TestingConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Test User
        self.user = User(username='testuser', email='test@example.com')
        db.session.add(self.user)
        
        # Create Rooms
        self.room_focus = Room(name='Focus Room', capacity=1, is_active=True, equipment=[])
        self.room_alpha = Room(name='Salle Alpha', capacity=4, is_active=True, equipment=['TV'])
        db.session.add(self.room_focus)
        db.session.add(self.room_alpha)
        db.session.commit()
        
        # Mock finding user (token bypass or mock token_required)
        # Since I can't easily bypass @token_required without a valid token, 
        # I will mock the `token_required` decorator or just the `current_user` in the context if possible.
        # Easier: generate a real token if `User` model supports it.
        # Assuming `User.generate_token()` exists or similar. 
        # Let's check User model? No time.
        # Alternative: Patch `app.api.routes.chat.token_required` to just pass through and inject user.
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def get_headers(self):
        # Generate token
        token = jwt.encode({'user_id': self.user.id}, self.app.config['SECRET_KEY'], algorithm="HS256")
        return {'Authorization': f'Bearer {token}'}

    @patch('app.services.nlp_service.NLPService.generate_response_stream')
    @patch('app.services.nlp_service.NLPService.parse_intent')
    def test_missing_slots_batching(self, mock_parse_intent, mock_generate):
        # Scenario: Missing date, attendees, duration
        mock_parse_intent.return_value = ('BOOK_INTENT', {'room_name': 'Salle Alpha'})
        
        response = self.client.post('/api/chat/message', json={'message': 'Je veux la salle Alpha'}, headers=self.get_headers())
        
        # Verify call
        if not mock_generate.call_args:
            print(f"DEBUG: Response status: {response.status_code}")
            print(f"DEBUG: Response data: {response.get_data(as_text=True)}")
            self.fail("generate_response_stream not called")

        args, _ = mock_generate.call_args
        context_text = args[0]
        print(f"\n[Missing Slots] Context passed to LLM:\n{context_text}")
        
        # Expectation: "missing details: la date/heure, le nombre de personnes, la durée"
        self.assertIn("missing details", context_text)
        self.assertIn("la date/heure", context_text)
        self.assertIn("le nombre de personnes", context_text)
        self.assertIn("la durée", context_text)

    @patch('app.services.nlp_service.NLPService.generate_response_stream')
    @patch('app.services.nlp_service.NLPService.parse_intent')
    def test_logic_flow(self, mock_parse, mock_generate):
        # 1. Test Availability Logic (Capacity Mismatch)
        # Intent: Book Focus Room (cap 1) for 4 people
        mock_parse.return_value = ('BOOK_INTENT', {
            'start_time': '2025-12-17T09:00:00',
            'duration_minutes': 60,
            'attendees': 4,
            'room_name': 'Focus Room'
        })
        
        response = self.client.post('/api/chat/message', json={'message': 'Focus Room pour 4'}, headers=self.get_headers())
        
        if not mock_generate.call_args:
             print(f"DEBUG: Response status: {response.status_code}")
             print(f"DEBUG: Response data: {response.get_data(as_text=True)}")
             self.fail("generate_response_stream not called in Capacity Mismatch")

        args, _ = mock_generate.call_args
        context_text = args[0]
        
        print(f"\n[Capacity Mismatch] Context passed to LLM:\n{context_text}")
        self.assertIn("The requested room 'Focus Room' is too small", context_text)
        self.assertIn("Outcome: The requested room 'Focus Room' is too small", context_text)
        self.assertIn("Alternatives found", context_text)
        self.assertIn("Salle Alpha", context_text)

if __name__ == '__main__':
    unittest.main()
