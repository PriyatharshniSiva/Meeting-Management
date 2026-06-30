import time
import json
import threading
from django.utils import timezone
from .models import MeetingMinutes, Meeting, Participant, ActionItem
from django.contrib.auth import get_user_model

User = get_user_model()

def run_ai_transcription(minutes_id):
    import os
    import json
    import time
    from pydub import AudioSegment
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    from dotenv import load_dotenv
    from django.conf import settings
    
    try:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        meeting = minutes.meeting
        
        minutes.status = 'PROCESSING'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Audio uploaded successfully. Starting AI processing...'})
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        load_dotenv(os.path.join(settings.BASE_DIR, '.env'), override=True)
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        if not api_key:
            raise Exception("API_KEY_MISSING")
            
        print(f"Loaded API key for transcription. Starts with: {api_key[:3]}...", flush=True)
        genai.configure(api_key=api_key)
        
        # Determine participants
        participants = Participant.objects.filter(meeting=meeting, attendance_status='ATTENDED').select_related('user')
        if participants.count() == 0:
            participants = Participant.objects.filter(meeting=meeting).select_related('user')
            
        participant_names = ", ".join([p.user.get_full_name() or p.user.username for p in participants])
        
        if not minutes.audio_file:
            raise Exception("No audio file found for this meeting.")
            
        audio_file_path = minutes.audio_file.path
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Loading and splitting audio file...'})
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        # Load and chunk audio
        audio = AudioSegment.from_file(audio_file_path)
        chunk_length_ms = 15 * 60 * 1000 # 15 minutes
        chunks = [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        print("Initializing Gemini API...", flush=True)
        transcription_model = genai.GenerativeModel('gemini-2.5-flash')
        all_transcript_data = []
        uploaded_files = []
        known_speakers_so_far = set()
        
        for idx, chunk in enumerate(chunks):
            minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': f'Transcribing Part {idx+1}/{len(chunks)}...'})
            minutes.processing_logs = list(minutes.processing_logs)
            minutes.save()
            
            chunk_file_path = f"{audio_file_path}_chunk_{idx}.mp3"
            chunk.export(chunk_file_path, format="mp3")
            
            uploaded_file = genai.upload_file(path=chunk_file_path)
            uploaded_files.append(uploaded_file)
            
            # Wait for file processing
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(5)
                uploaded_file = genai.get_file(uploaded_file.name)
                
            if uploaded_file.state.name == "FAILED":
                raise Exception("Audio file processing failed on Gemini servers.")
                
            known_speakers_str = ", ".join(known_speakers_so_far) if known_speakers_so_far else "None yet"
                
            prompt = f"""
            You are an expert audio transcriber. Listen to this audio and provide a complete, verbatim transcript with strict speaker diarization.
            Format the transcript EXACTLY as a valid JSON array of objects with no markdown block formatting (do not wrap in ```json).
            
            CRITICAL RULES FOR SPEAKERS:
            1. You MUST distinctly separate when different people are talking. 
            2. You MUST recognize voices consistently. If Speaker 1 speaks, then Speaker 2 speaks, and then the first person speaks again, you MUST label it "Speaker 1". Do not invent a new speaker if it's the same voice.
            3. Group continuous speech by the same speaker into a single JSON object.
            4. Do NOT deduce or use actual names or random names. You MUST ALWAYS strictly use generic numeric labels exactly as: "Speaker 1", "Speaker 2", "Speaker 3", etc.
            5. Speakers identified in previous parts of this recording: {known_speakers_str}. You MUST reuse these exact numeric labels if the voices match previously identified speakers.
            
            Each object must have:
            - "timestamp": "[MM:SS]" representing the approximate time of the speech relative to this chunk.
            - "speaker": The consistent name of the speaker.
            - "text": The exact words spoken.
            
            Ensure the JSON is perfectly valid. Do not omit any spoken words.
            """
            
            response = transcription_model.generate_content([uploaded_file, prompt])
            result_text = response.text.strip()
            
            if result_text.startswith("```json"): result_text = result_text[7:]
            if result_text.startswith("```"): result_text = result_text[3:]
            if result_text.endswith("```"): result_text = result_text[:-3]
                
            chunk_data = json.loads(result_text)
            
            # Adjust timestamps for subsequent chunks
            if idx > 0:
                offset_seconds = idx * 15 * 60
                for entry in chunk_data:
                    ts = entry.get('timestamp', '[00:00]')
                    try:
                        m, s = map(int, ts.strip('[]').split(':'))
                        total_s = m * 60 + s + offset_seconds
                        new_m = total_s // 60
                        new_s = total_s % 60
                        entry['timestamp'] = f"[{new_m:02d}:{new_s:02d}]"
                    except:
                        pass
                        
            all_transcript_data.extend(chunk_data)
            
            # Update known speakers for next chunks
            for entry in chunk_data:
                spk = entry.get('speaker', '').strip()
                if spk and spk.lower() != 'unknown':
                    known_speakers_so_far.add(spk)
            
            # Clean up local chunk file
            if os.path.exists(chunk_file_path):
                os.remove(chunk_file_path)
                
        # Clean up uploaded files
        for f in uploaded_files:
            try:
                genai.delete_file(f.name)
            except:
                pass
                
        minutes.history = json.dumps(all_transcript_data)
        
        # Calculate Speaker Metrics
        speaker_counts = {}
        for entry in all_transcript_data:
            spk = entry.get('speaker', 'Unknown')
            speaker_counts[spk] = speaker_counts.get(spk, 0) + 1
            
        total_entries = sum(speaker_counts.values()) or 1
        metrics = {}
        for spk, count in speaker_counts.items():
            metrics[spk] = {
                'time': '00:00', # To be improved with actual duration
                'count': count,
                'percentage': int((count / total_entries) * 100)
            }
        minutes.speaker_metrics = metrics
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Merging Transcript...'})
        minutes.status = 'GENERATING'
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        # Generate AI Summary
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
        {json.dumps(all_transcript_data)}
        """
        
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Generating AI Summary...'})
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        sum_response = transcription_model.generate_content(summary_prompt)
        sum_text = sum_response.text.strip()
        
        if sum_text.startswith("```json"): sum_text = sum_text[7:]
        if sum_text.startswith("```"): sum_text = sum_text[3:]
        if sum_text.endswith("```"): sum_text = sum_text[:-3]
            
        parsed_sum = json.loads(sum_text)
        
        summary = parsed_sum.get("Summary", "No summary provided.")
        discussion_pts = parsed_sum.get("Discussion_Points", [])
        if discussion_pts:
            summary += "\n\n### Discussion Points\n- " + "\n- ".join(discussion_pts)
            
        minutes.ai_summary = summary
        minutes.decisions = parsed_sum.get("Decisions_Taken", [])
        minutes.action_items_raw = parsed_sum.get("Action_Items", [])
        
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
            
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Completed'})
        minutes.status = 'READY'
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
            
    except google_exceptions.GoogleAPIError as api_err:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        # Log real error securely in backend
        print(f"[BACKEND ERROR] Gemini API Error during transcription: {str(api_err)}", flush=True)
        minutes.status = 'FAILED'
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.processing_logs.append({
            'timestamp': timezone.now().isoformat(), 
            'message': f'API Error: {str(api_err)}'
        })
        minutes.save()
    except Exception as e:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        # Catch API_KEY_MISSING and others
        print(f"[BACKEND ERROR] Exception during transcription: {str(e)}", flush=True)
        minutes.status = 'FAILED'
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.processing_logs.append({
            'timestamp': timezone.now().isoformat(), 
            'message': f'Error: {str(e)}'
        })
        minutes.save()

def start_ai_processing(minutes_id):
    thread = threading.Thread(target=run_ai_transcription, args=(minutes_id,))
    thread.daemon = True
    thread.start()

def run_ai_text_processing(minutes_id):
    import os
    import json
    
    try:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        meeting = minutes.meeting
        raw_text = minutes.notes # we stored the raw text in notes temporarily
        
        minutes.status = 'PROCESSING'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Processing pasted text transcript...'})
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        from dotenv import load_dotenv
        from django.conf import settings
        
        load_dotenv(os.path.join(settings.BASE_DIR, '.env'), override=True)
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        # Determine if we can use Gemini
        can_use_gemini = bool(api_key)
        
        if can_use_gemini:
            import google.generativeai as genai
            print(f"Loaded API key for text processing. Starts with: {api_key[:3]}...", flush=True)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # 1. Structure the raw text
            minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Structuring text into JSON format using AI...'})
            minutes.processing_logs = list(minutes.processing_logs)
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
            
            try:
                response = model.generate_content(structure_prompt)
                result_text = response.text.strip()
                
                if result_text.startswith("```json"): result_text = result_text[7:]
                if result_text.startswith("```"): result_text = result_text[3:]
                if result_text.endswith("```"): result_text = result_text[:-3]
                    
                transcript_data = json.loads(result_text)
            except:
                can_use_gemini = False
        
        if not can_use_gemini:
            minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'API Key invalid/missing. Using raw text format...'})
            minutes.processing_logs = list(minutes.processing_logs)
            minutes.save()
            transcript_data = [{"timestamp": "[00:00]", "speaker": "Speaker", "text": raw_text}]
            
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
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
        
        # 2. Generating AI Summary
        if can_use_gemini:
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
            
            try:
                sum_response = model.generate_content(summary_prompt)
                sum_text = sum_response.text.strip()
                
                if sum_text.startswith("```json"): sum_text = sum_text[7:]
                if sum_text.startswith("```"): sum_text = sum_text[3:]
                if sum_text.endswith("```"): sum_text = sum_text[:-3]
                    
                parsed_sum = json.loads(sum_text)
                
                summary = parsed_sum.get("Summary", "No summary provided.")
                discussion_pts = parsed_sum.get("Discussion_Points", [])
                if discussion_pts:
                    summary += "\n\n### Discussion Points\n- " + "\n- ".join(discussion_pts)
                    
                minutes.ai_summary = summary
                minutes.decisions = parsed_sum.get("Decisions_Taken", [])
                minutes.action_items_raw = parsed_sum.get("Action_Items", [])
                
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
                minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'AI Summary and Action Items generated successfully.'})
            except Exception as e:
                minutes.ai_summary = f"Summary skipped: API error ({str(e)})."
                minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Failed to generate AI Summary via API.'})
        else:
            minutes.ai_summary = "Offline Mode: AI Summary skipped due to missing/invalid API key."
            minutes.decisions = []
            minutes.action_items_raw = []
            minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': 'Skipped AI Summary due to missing/invalid API key.'})
            
        minutes.status = 'READY'
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()
            
    except Exception as e:
        minutes = MeetingMinutes.objects.get(id=minutes_id)
        error_msg = str(e)
        
        minutes.status = 'NO_TRANSCRIPT'
        minutes.processing_logs.append({'timestamp': timezone.now().isoformat(), 'message': f'Error processing text: {error_msg}'})
        minutes.processing_logs = list(minutes.processing_logs)
        minutes.save()

def start_ai_text_processing(minutes_id):
    thread = threading.Thread(target=run_ai_text_processing, args=(minutes_id,))
    thread.daemon = True
    thread.start()
