import uuid
import random

class ZoomAPI:
    """
    Mock Zoom API Client since OAuth credentials were not provided.
    This simulates creating Zoom meetings and generating automated transcripts.
    """
    
    @staticmethod
    def create_meeting(topic, duration, start_time):
        """
        Simulates POST /v2/users/me/meetings
        Creates a Zoom meeting with auto_recording='cloud'
        """
        meeting_id = str(random.randint(80000000000, 99999999999))
        join_url = f"https://zoom.us/j/{meeting_id}?pwd={uuid.uuid4().hex[:8]}"
        
        return {
            "id": meeting_id,
            "topic": topic,
            "start_time": start_time,
            "duration": duration,
            "join_url": join_url,
            "settings": {
                "auto_recording": "cloud"
            }
        }

    @staticmethod
    def get_mock_transcript(topic):
        """
        Simulates the parsed output from a Zoom VTT transcript file.
        """
        return [
            {"speaker": "System", "text": f"Welcome to {topic}. This meeting is being recorded to the cloud."},
            {"speaker": "Host", "text": "Alright everyone, let's get started with the weekly sync."},
            {"speaker": "Host", "text": "We need to finalize the Q3 marketing budget today."},
            {"speaker": "Participant", "text": "I reviewed the numbers. We should allocate 20% more to social media ads."},
            {"speaker": "Host", "text": "Good idea. I will approve that 20% increase."},
            {"speaker": "Participant", "text": "I will update the Excel spreadsheet by tomorrow EOD."},
            {"speaker": "Host", "text": "Perfect. This meeting is now adjourned."}
        ]
