from openai import OpenAI
from datetime import datetime
import json
import os
from app.config import Config

class NLPService:
    @staticmethod
    def get_client():
        return OpenAI(api_key=Config.OPENAI_API_KEY)

    @staticmethod
    def parse_intent(text: str, history: dict = None):
        client = NLPService.get_client()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        weekday = datetime.now().strftime("%A")
        
        history_text = "None"
        if history:
             history_text = json.dumps(history, indent=2)

        system_prompt = f"""
        You are a smart workspace assistant.
        Current Date/Time: {current_time} ({weekday}).
        
        Previous Context (Last Intent/Slots):
        {history_text}
        
        Analyze the user's message and extract the intent and slots in JSON format.
        IMPORTANT: Merge the new information with the Previous Context. 
        - If the user provides new values (e.g. new date, new attendees), OVERWRITE the old ones.
        - If the user only specifies a change (e.g. "nous sommes 5"), KEEP the other slots from context (e.g. start_time).
        - If the intent was BOOK_INTENT and user just updates info, keep BOOK_INTENT.
        - CRITICAL: If the intent CHANGES (e.g. from BOOK_INTENT to CANCEL_INTENT), DO NOT use the old slots (like start_time) unless the user explicitly refers to them (e.g. "annule ça"). Start fresh for the new intent.
        
        Intents: 
        - BOOK_INTENT: user wants to book a room.
        - QUERY_AVAILABILITY: user asks for availability (e.g. "when is it free?", "dispo demain").
        - CANCEL_INTENT: user wants to cancel/delete a booking (e.g. "annuler ma réservation", "supprimer").
        - GREETING: user says hello/hi/bonjour.
        - UNKNOWN: cannot understand.
        
        Rules for Slots:
        - attendees: integer. If implicit (e.g. "meeting", "we"), assume 2. If explicit "me", "alone", 1. Default 1.
        - start_time: ISO 8601 format (YYYY-MM-DDTHH:MM:ss). Calculate relative dates (tomorrow, next monday) based on Current Date.
        - duration_minutes: integer. Return NULL if not specified. Do NOT assume 60.
        - end_time: Calculate based on start_time + duration if not specified.
        - scope: for CANCEL_INTENT. Values: 'ALL' (if "all", "toutes"), 'LAST' (if "last", "dernière", "latest"), 'SINGLE' (default).
        - equipment: list of strings. Extract requested equipment (e.g. ["projector", "whiteboard", "TV"]). Empty list if none.
        
        Return ONLY valid JSON.
        Example JSON:
        {{
            "intent": "BOOK_INTENT",
            "slots": {{
                "attendees": 5,
                "start_time": "2023-10-27T14:00:00",
                "duration_minutes": 30,
                "equipment": ["TV"]
            }}
        }}
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get('intent', 'UNKNOWN'), data.get('slots', {})
        except Exception as e:
            print(f"LLM Error: {e}")
            return "API_ERROR", {"error": str(e)}

    @staticmethod
    def generate_natural_response(situation_context: str):
        """
        Generate a polite, natural language response based on the technical outcome.
        """
        client = NLPService.get_client()
        
        system_prompt = """
        You are WorkspaceSmart, a helpful and professional office assistant.
        Task: Write a short, natural response in French to the user based on the Situation provided.
        - Prepare them for the action if any (like confirming).
        - Be concise but friendly.
        - Do NOT invent information not in the Situation.
        - Do NOT use markdown formatting like bolding * unless necessary for clarity.
        """
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Situation: {situation_context}"}
                ]
            )
            return response.choices[0].message.content.strip()
        except:
            # Fallback if generation fails
            return "D'accord, voici l'information demandée."
