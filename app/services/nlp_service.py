import google.generativeai as genai
from datetime import datetime
import json
import os
from app.config import Config

class NLPService:
    @staticmethod
    def configure():
        genai.configure(api_key=Config.GOOGLE_API_KEY)

    @staticmethod
    def parse_intent(text: str, history: dict = None):
        NLPService.configure()
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        weekday = datetime.now().strftime("%A")
        
        history_text = "None"
        if history:
             history_text = json.dumps(history, indent=2)

        prompt = f"""
        You are a smart workspace assistant.
        Current Date/Time: {current_time} ({weekday}).
        
        Previous Context (Last Intent/Slots):
        {history_text}
        
        Analyze the user's message and extract the intent and slots in JSON format.
        IMPORTANT: Merge the new information with the Previous Context. 
        - If the user provides new values (e.g. new date, new attendees), OVERWRITE the old ones.
        - If the user only specifies a change (e.g. "nous sommes 5"), KEEP the other slots from context (e.g. start_time).
        - If the intent was BOOK_INTENT and user just updates info, keep BOOK_INTENT.
        
        Intents: 
        - BOOK_INTENT: user wants to book a room.
        - QUERY_AVAILABILITY: user asks for availability (e.g. "when is it free?", "dispo demain").
        - CANCEL_INTENT: user wants to cancel/delete a booking (e.g. "annuler ma réservation", "supprimer").
        - GREETING: user says hello/hi/bonjour.
        - UNKNOWN: cannot understand.
        
        Rules for Slots:
        - attendees: integer. If implicit (e.g. "meeting", "we"), assume 2. If explicit "me", "alone", 1. Default 1.
        - start_time: ISO 8601 format (YYYY-MM-DDTHH:MM:ss). Calculate relative dates (tomorrow, next monday) based on Current Date.
        - duration_minutes: integer. "fast meeting" or "meeting rapide" = 30. "one hour" = 60. Default 60.
        - end_time: Calculate based on start_time + duration if not specified.
        - scope: for CANCEL_INTENT only. 'ALL' if user says "all", "toutes", "tout". 'SINGLE' default.
        
        User Message: "{text}"
        
        Return ONLY valid JSON.
        Example JSON:
        {{
            "intent": "BOOK_INTENT",
            "slots": {{
                "attendees": 5,
                "start_time": "2023-10-27T14:00:00",
                "duration_minutes": 60 
            }}
        }}
        """
        
        try:
            response = model.generate_content(prompt)
            # Cleanup markdown code blocks if any
            content = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(content)
            return data.get('intent', 'UNKNOWN'), data.get('slots', {})
        except Exception as e:
            print(f"LLM Error: {e}")
            # Identify if it's a quota error
            if "429" in str(e):
                return "API_ERROR", {"error": "Quota Exceeded (429)"}
            return "API_ERROR", {"error": str(e)}

    @staticmethod
    def generate_natural_response(situation_context: str):
        """
        Generate a polite, natural language response based on the technical outcome.
        """
        NLPService.configure()
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = f"""
        You are WorkspaceSmart, a helpful and professional office assistant.
        
        Situation: {situation_context}
        
        Task: Write a short, natural response in French to the user. 
        - Prepare them for the action if any (like confirming).
        - Be concise but friendly.
        - Do NOT invent information not in the Situation.
        - Do NOT use markdown formatting like bolding * unless necessary for clarity.
        
        Response:
        """
        
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except:
            # Fallback if generation fails
            return "D'accord, voici l'information demandée."
