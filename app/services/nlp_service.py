from openai import OpenAI
from datetime import datetime, timedelta
import json
import os
from app.config import Config

class NLPService:
    @staticmethod
    def get_client():
        return OpenAI(api_key=Config.OPENAI_API_KEY)

    @staticmethod
    def parse_intent(text: str, history: list = None):
        client = NLPService.get_client()
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        weekday = datetime.now().strftime("%A")

        # Generate reference calendar for the next 7 days to help LLM with dates
        reference_calendar = "Reference Calendar (Next 7 days):\n"
        today_date = datetime.now()
        for i in range(8):
            day = today_date + timedelta(days=i)
            # Use English weekday names as system prompt is in English, 
            # but maybe user input is French. LLM should map it.
            # Using %A gives day name in locale, which might be mixed if locale is not set.
            # Let's force English or just rely on ISO date.
            # Actually, let's just use the iso format and a simple day name if possible.
            # safe assumption: LLM understands dates.
            reference_calendar += f"- {day.strftime('%A')} {day.strftime('%Y-%m-%d')}\n"

        system_prompt = f"""
        You are a smart workspace assistant.
        Current Date/Time: {current_time} ({weekday}).
        
        {reference_calendar}
        
        Analyze the conversation history and extract the intent and slots in JSON format.
        
        Intents: 
        - BOOK_INTENT: user wants to book a room.
        - MODIFY_INTENT: user wants to change/modify an existing booking (e.g. "change l'heure", "finalement à 18h", "modifie ma réservation").
        - QUERY_AVAILABILITY: user asks for availability (e.g. "when is it free?", "dispo demain").
        - CANCEL_INTENT: user wants to cancel/delete a booking (e.g. "annuler ma réservation", "supprimer").
        - GREETING: user says hello/hi/bonjour.
        - UNKNOWN: cannot understand.
        
        Rules for Slots:
        - attendees: integer. Return NULL if not specified. Do NOT assume a default (e.g. do not assume 1 or 2).
        - start_time: ISO 8601 format (YYYY-MM-DDTHH:MM:ss). Calculate relative dates (tomorrow, next monday) based on Current Date.
        - duration_minutes: integer. Return NULL if not specified. Do NOT assume 60.
        - end_time: Calculate based on start_time + duration if not specified.
        - scope: for CANCEL_INTENT. Values: 'ALL' (if "all", "toutes"), 'LAST' (if "last", "dernière", "latest"), 'SINGLE' (default).
        - equipment: list of strings. Extract requested equipment (e.g. ["projector", "whiteboard", "TV"]). Empty list if none.
        - room_name: string. Identify if user requests a specific room (e.g. "Salle Alpha", "Room 1", "l'auditorium"). Return NULL if not specified. match reasonably.
        
        Instructions:
        - Look at the WHOLE conversation history to determine the current Intention and Slots.
        - If the user is answering a question (e.g. "how many?", "5"), look at the previous message to understand context.
        - Merge new info with previous info implicitly found in history. 
        - Return the FULL STATE of known slots.
        
        Return ONLY valid JSON.
        Example JSON:
        {{
            "intent": "BOOK_INTENT",
            "slots": {{
                "attendees": 5,
                "start_time": "2023-10-27T14:00:00",
                "duration_minutes": 30,
                "equipment": ["TV"],
                "room_name": "Salle Alpha"
            }}
        }}
        """
        
        # Prepare messages
        messages = [{"role": "system", "content": system_prompt}]
        
        if history and isinstance(history, list):
            # history is now a list of messages [{"role": "user", "content": ...}, ...]
            messages.extend(history)
        
        # Add current message
        messages.append({"role": "user", "content": text})

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            return data.get('intent', 'UNKNOWN'), data.get('slots', {})
        except Exception as e:
            print(f"LLM Error: {e}")
            return "API_ERROR", {"error": str(e)}

    @staticmethod
    def generate_response_stream(situation_context: str, action_data: dict = None, on_complete=None):
        """
        Generate a streaming response (generator) yielding JSON chunks.
        Protocol:
        - {"type": "delta", "content": "..."}  (Text chunks)
        - {"type": "action", "data": {...}}    (Action payload at the end)
        """
        client = NLPService.get_client()
        
        system_prompt = """
        You are WorkspaceSmart, a helpful and professional office assistant.
        Task: Write a natural response in French based on the Situation.
        
        Guidelines:
        - Be concise, direct, and helpful.
        - NO email format (no "Objet:", no "Cordialement", no "Chère équipe").
        - Adopt a conversational chat style.
        - If data (like a list of rooms) is provided, present it clearly using Markdown.
        - Use bold (**Name**) for room names or important data.
        - Use bullet points for lists.
        - Do NOT invent information.
        - If the situation mentions no rooms available, suggest the alternatives provided in the context.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Situation Details:\n{situation_context}"}
        ]

        full_response = ""
        try:
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    content = chunk.choices[0].delta.content
                    full_response += content
                    yield json.dumps({"type": "delta", "content": content}) + "\n"
            
            if on_complete:
                on_complete(full_response)
            
            # If there's an action, send it as the final chunk
            if action_data:
                yield json.dumps({"type": "action", "data": action_data}) + "\n"

        except Exception as e:
            print(f"Stream Error: {e}")
            yield json.dumps({"type": "error", "content": "Erreur de génération IA."}) + "\n"
