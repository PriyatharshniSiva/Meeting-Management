import time
import json
import threading
from django.utils import timezone
from .models import MeetingMinutes, Meeting, Participant, ActionItem
from django.contrib.auth import get_user_model

User = get_user_model()

def run_ai_transcription(minutes_id):
    import os
    import google.generativeai as genai
    
    try:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        meeting = minutes.meeting
        
        minutes.status = 'PROCESSING'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Audio uploaded successfully. Starting AI processing...'})
        minutes.save()
        
        from dotenv import load_dotenv
        from django.conf import settings
        import os
        
        load_dotenv(os.path.join(settings.BASE_DIR, '.env'), override=True)
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            raise Exception("GEMINI_API_KEY is not configured in .env")
            
        # Log masked key
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        print(f"DEBUG: Loaded GEMINI_API_KEY for audio transcription: {masked_key}")
        genai.configure(api_key=api_key)
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Uploading audio to AI model for transcription and diarization...'})
        minutes.save()
        
        # Determine actual participants to map as speakers
        participants = Participant.objects.filter(meeting=meeting, attendance_status='ATTENDED').select_related('user')
        if participants.count() == 0:
            participants = Participant.objects.filter(meeting=meeting).select_related('user')
            
        participant_names = [p.user.get_full_name() or p.user.username for p in participants]
        if not participant_names:
            participant_names = ['Speaker 1', 'Speaker 2']
            
        # Upload the file
        if not minutes.audio_file:
            raise Exception("No audio file found for this meeting.")
            
        audio_file_path = minutes.audio_file.path
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Loading and splitting audio file...'})
        minutes.save()
        
        from pydub import AudioSegment
        import tempfile
        import os
        
        audio = AudioSegment.from_file(audio_file_path)
        chunk_length_ms = 15 * 60 * 1000 # 15 minutes
        chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        if not chunks:
            raise Exception("Audio file is empty or corrupted.")
            
        transcript_data = []
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        for i, chunk in enumerate(chunks):
            minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': f'Transcribing Part {i+1}/{len(chunks)}...'})
            minutes.save()
            
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                chunk.export(tmp.name, format="mp3")
                tmp_path = tmp.name
                
            uploaded_file = None
            try:
                uploaded_file = genai.upload_file(path=tmp_path)
                
                chunk_start_ms = i * chunk_length_ms
                start_min = (chunk_start_ms // 1000) // 60
                start_sec = (chunk_start_ms // 1000) % 60
                
                prompt = f"""
                You are an expert audio transcriber. Listen to the provided audio file of a meeting and transcribe it.
                Identify the different speakers (e.g. Speaker 1, Speaker 2) or use the following participant names if you can reliably match voices (but defaulting to Speaker 1, Speaker 2 is fine): {participant_names}.
                
                This is Part {i+1} of a longer meeting. The audio in this file starts at {start_min:02d}:{start_sec:02d} in the full meeting.
                Please ensure the timestamps you provide are relative to the BEGINNING of this chunk (starting at 00:00).
                
                Output EXACTLY a valid JSON array of objects with no markdown block formatting (do not wrap in ```json).
                Each object must have:
                - "timestamp": "[MM:SS]" representing the approximate time.
                - "speaker": The name of the speaker.
                - "text": The text they spoke.
                
                Example:
                [
                    {{"timestamp": "[00:00]", "speaker": "Speaker 1", "text": "Hello everyone."}}
                ]
                """
                
                response = model.generate_content([uploaded_file, prompt])
                result_text = response.text.strip()
                
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                if result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                    
                chunk_transcript = json.loads(result_text)
                
                # Adjust timestamps
                for entry in chunk_transcript:
                    ts = entry.get('timestamp', '[00:00]')
                    try:
                        ts = ts.strip('[]')
                        m, s = map(int, ts.split(':'))
                        total_s = (m * 60) + s + (chunk_start_ms // 1000)
                        new_m = total_s // 60
                        new_s = total_s % 60
                        entry['timestamp'] = f"[{new_m:02d}:{new_s:02d}]"
                    except:
                        pass
                    transcript_data.append(entry)
                    
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
                if uploaded_file:
                    try:
                        genai.delete_file(uploaded_file.name)
                    except:
                        pass
                        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Merging Transcript...'})
        minutes.save()
        
        minutes.history = json.dumps(transcript_data)
        
        # Calculate Speaker Metrics
        speaker_counts = {}
        for entry in transcript_data:
            spk = entry.get('speaker', 'Unknown')
            speaker_counts[spk] = speaker_counts.get(spk, 0) + 1
            
        total_entries = sum(speaker_counts.values()) or 1
        metrics = {}
        for spk, count in speaker_counts.items():
            metrics[spk] = {
                'time': '00:00', # Exact duration computation omitted for simplicity
                'count': count,
                'percentage': int((count / total_entries) * 100)
            }
        minutes.speaker_metrics = metrics
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Transcription completed. Generating AI summaries...'})
        minutes.status = 'GENERATING'
        minutes.save()
        
        # 3. Generating AI Summary
        summary_prompt = f"""
        You are an expert executive assistant. Review the following meeting transcript.
        Extract the following structured information and return it EXACTLY as a valid JSON object without markdown formatting blocks (do not wrap in ```json).
        {{
            "Summary": "A concise paragraph summarizing the overall meeting.",
            "Discussion_Points": ["Point 1", "Point 2"],
            "Decisions_Taken": ["Decision 1", "Decision 2"],
            "Action_Items": [
                {{"task": "Task description", "owner": "Assigned Person", "priority": "HIGH"}}
            ]
        }}
        
        Transcript:
        {json.dumps(transcript_data)}
        """
        
        sum_response = model.generate_content(summary_prompt)
        sum_text = sum_response.text.strip()
        
        if sum_text.startswith("```json"):
            sum_text = sum_text[7:]
        if sum_text.startswith("```"):
            sum_text = sum_text[3:]
        if sum_text.endswith("```"):
            sum_text = sum_text[:-3]
            
        parsed_sum = json.loads(sum_text)
        
        summary = parsed_sum.get("Summary", "No summary provided.")
        discussion_pts = parsed_sum.get("Discussion_Points", [])
        if discussion_pts:
            summary += "\n\n### Discussion Points\n- " + "\n- ".join(discussion_pts)
            
        minutes.ai_summary = summary
        minutes.decisions = parsed_sum.get("Decisions_Taken", [])
        minutes.action_items_raw = parsed_sum.get("Action_Items", [])
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'AI Summary and Action Items generated successfully.'})
        minutes.status = 'READY'
        minutes.save()
        
        # Create Action Items in DB
        for item in minutes.action_items_raw:
            assignee = None
            owner_str = item.get('owner', '')
            if owner_str:
                if participants.filter(user__username__icontains=owner_str).exists():
                    assignee = participants.filter(user__username__icontains=owner_str).first().user
                elif participants.filter(user__first_name__icontains=owner_str).exists():
                    assignee = participants.filter(user__first_name__icontains=owner_str).first().user
            
            if not assignee and participants.exists():
                assignee = participants.first().user
            elif not assignee:
                assignee = meeting.created_by
                
            ActionItem.objects.create(
                meeting=meeting,
                task_name=item.get('task', 'Task')[:255],
                description=f"Auto-generated action item from {meeting.title} transcript.",
                assigned_to=assignee,
                priority=item.get('priority', 'MEDIUM'),
                due_date=timezone.now().date() + timezone.timedelta(days=2),
                status='PENDING'
            )
            
    except Exception as e:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        error_msg = str(e)
        
        minutes.status = 'NO_TRANSCRIPT'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': f"Error processing transcription: {error_msg}"})
        minutes.save()

def start_ai_processing(minutes_id):
    thread = threading.Thread(target=run_ai_transcription, args=(minutes_id,))
    thread.daemon = True
    thread.start()

def run_ai_text_processing(minutes_id):
    import os
    import google.generativeai as genai
    
    try:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        meeting = minutes.meeting
        raw_text = minutes.notes # we stored the raw text in notes temporarily
        
        minutes.status = 'PROCESSING'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Processing pasted text transcript...'})
        minutes.save()
        
        from dotenv import load_dotenv
        from django.conf import settings
        import os
        
        load_dotenv(os.path.join(settings.BASE_DIR, '.env'), override=True)
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key == "your_gemini_api_key_here":
            raise Exception("GEMINI_API_KEY is not configured in .env")
            
        # Log masked key
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        print(f"DEBUG: Loaded GEMINI_API_KEY for text processing: {masked_key}")
        
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 1. Structure the raw text
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Structuring text into JSON format...'})
        minutes.save()
        
        structure_prompt = f"""
        You are an expert audio transcriber. Review the following raw meeting transcript.
        Format it EXACTLY as a valid JSON array of objects with no markdown block formatting (do not wrap in ```json).
        Each object must have:
        - "timestamp": "[MM:SS]" representing the approximate time, or just "[00:00]" if unknown.
        - "speaker": The name of the speaker.
        - "text": The text they spoke.
        
        Raw Transcript:
        {raw_text}
        """
        
        response = model.generate_content(structure_prompt)
        result_text = response.text.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        transcript_data = json.loads(result_text)
        minutes.history = json.dumps(transcript_data)
        
        # Calculate Speaker Metrics
        speaker_counts = {}
        for entry in transcript_data:
            spk = entry.get('speaker', 'Unknown')
            speaker_counts[spk] = speaker_counts.get(spk, 0) + 1
            
        total_entries = sum(speaker_counts.values()) or 1
        metrics = {}
        for spk, count in speaker_counts.items():
            metrics[spk] = {
                'time': '00:00',
                'count': count,
                'percentage': int((count / total_entries) * 100)
            }
        minutes.speaker_metrics = metrics
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Text structuring completed. Generating AI summaries...'})
        minutes.status = 'GENERATING'
        minutes.save()
        
        # 2. Generating AI Summary
        participants = Participant.objects.filter(meeting=meeting)
        summary_prompt = f"""
        You are an expert executive assistant. Review the following meeting transcript.
        Extract the following structured information and return it EXACTLY as a valid JSON object without markdown formatting blocks (do not wrap in ```json).
        {{
            "Summary": "A concise paragraph summarizing the overall meeting.",
            "Discussion_Points": ["Point 1", "Point 2"],
            "Decisions_Taken": ["Decision 1", "Decision 2"],
            "Action_Items": [
                {{"task": "Task description", "owner": "Assigned Person", "priority": "HIGH"}}
            ]
        }}
        
        Transcript:
        {json.dumps(transcript_data)}
        """
        
        sum_response = model.generate_content(summary_prompt)
        sum_text = sum_response.text.strip()
        
        if sum_text.startswith("```json"):
            sum_text = sum_text[7:]
        if sum_text.startswith("```"):
            sum_text = sum_text[3:]
        if sum_text.endswith("```"):
            sum_text = sum_text[:-3]
            
        parsed_sum = json.loads(sum_text)
        
        summary = parsed_sum.get("Summary", "No summary provided.")
        discussion_pts = parsed_sum.get("Discussion_Points", [])
        if discussion_pts:
            summary += "\n\n### Discussion Points\n- " + "\n- ".join(discussion_pts)
            
        minutes.ai_summary = summary
        minutes.decisions = parsed_sum.get("Decisions_Taken", [])
        minutes.action_items_raw = parsed_sum.get("Action_Items", [])
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'AI Summary and Action Items generated successfully.'})
        minutes.status = 'READY'
        minutes.save()
        
        # Create Action Items in DB
        for item in minutes.action_items_raw:
            assignee = None
            owner_str = item.get('owner', '')
            if owner_str:
                if participants.filter(user__username__icontains=owner_str).exists():
                    assignee = participants.filter(user__username__icontains=owner_str).first().user
                elif participants.filter(user__first_name__icontains=owner_str).exists():
                    assignee = participants.filter(user__first_name__icontains=owner_str).first().user
            
            if not assignee and participants.exists():
                assignee = participants.first().user
            elif not assignee:
                assignee = meeting.created_by
                
            ActionItem.objects.create(
                meeting=meeting,
                task_name=item.get('task', 'Task')[:255],
                description=f"Auto-generated action item from {meeting.title} transcript.",
                assigned_to=assignee,
                priority=item.get('priority', 'MEDIUM'),
                due_date=timezone.now().date() + timezone.timedelta(days=2),
                status='PENDING'
            )
            
    except Exception as e:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        error_msg = str(e)
        
        minutes.status = 'NO_TRANSCRIPT'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': f'Error processing text: {error_msg}'})
        minutes.save()

def start_ai_text_processing(minutes_id):
    thread = threading.Thread(target=run_ai_text_processing, args=(minutes_id,))
    thread.daemon = True
    thread.start()
