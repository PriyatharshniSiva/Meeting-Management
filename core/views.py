from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from .models import Meeting, ActionItem

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
            
    return render(request, 'login.html')

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        e = request.POST.get('email')
        p = request.POST.get('password')
        r = request.POST.get('role', 'EMPLOYEE')
        
        # Simple validation
        if not u or not p:
            return render(request, 'signup.html', {'error': 'Username and Password required'})
            
        from core.models import CustomUser
        if CustomUser.objects.filter(username=u).exists():
            return render(request, 'signup.html', {'error': 'Username already exists'})
            
        user = CustomUser.objects.create_user(username=u, email=e, password=p, role=r)
        auth_login(request, user)
        return redirect('dashboard')
        
    return render(request, 'signup.html')

def logout_view(request):
    auth_logout(request)
    return redirect('login')

@login_required
def dashboard_view(request):
    total_meetings = Meeting.objects.count()
    upcoming_meetings = Meeting.objects.count() # placeholder for now
    completed_meetings = Meeting.objects.count() # placeholder
    
    pending_tasks = ActionItem.objects.filter(status='PENDING').count()
    overdue_tasks = 0 # placeholder
    
    from core.models import Participant, MeetingMinutes
    total_invites = Participant.objects.count()
    accepted_invites = Participant.objects.filter(rsvp_status='ACCEPTED').count()
    declined_invites = Participant.objects.filter(rsvp_status='DECLINED').count()
    attended_count = Participant.objects.filter(attendance_status='ATTENDED').count()
    
    total_transcriptions = MeetingMinutes.objects.exclude(history__isnull=True).exclude(history__exact='').count()
    ai_summaries = MeetingMinutes.objects.exclude(ai_summary__isnull=True).exclude(ai_summary__exact='').count()
    
    context = {
        'total_meetings': total_meetings,
        'upcoming_meetings': upcoming_meetings,
        'completed_meetings': completed_meetings,
        'pending_tasks': pending_tasks,
        'overdue_tasks': overdue_tasks,
        'total_invites': total_invites,
        'accepted_invites': accepted_invites,
        'declined_invites': declined_invites,
        'attended_count': attended_count,
        'total_transcriptions': total_transcriptions,
        'ai_summaries': ai_summaries,
    }
    return render(request, 'dashboard.html', context)

@login_required
def meetings_view(request):
    if request.method == 'POST':
        if request.user.role != 'ADMIN':
            from django.contrib import messages
            messages.error(request, "Only Admin users can create meetings.")
            return redirect('meetings')
            
        # Simple handler for creating a meeting
        title = request.POST.get('title')
        date = request.POST.get('date')
        time = request.POST.get('time')
        duration = request.POST.get('duration')
        m_type = request.POST.get('meeting_type')
        location = request.POST.get('location', '')
        meeting_link = request.POST.get('meeting_link', '')
        desc = request.POST.get('description')
        target_roles = request.POST.getlist('roles')
        
        if not date or not time:
            from django.contrib import messages
            messages.error(request, "Please provide a valid Date and Time format.")
            return redirect('meetings')
            
        meeting = Meeting.objects.create(
            title=title, date=date, time=time, 
            duration=duration, meeting_type=m_type, 
            location=location,
            meeting_link=meeting_link,
            description=desc, created_by=request.user,
            target_roles=target_roles
        )
        
        # Refresh to convert string date/time to python objects
        meeting.refresh_from_db()
        
        from core.models import CustomUser, Participant, InAppNotification
        users_to_invite = CustomUser.objects.filter(role__in=target_roles)
        
        participants = []
        notifications = []
        for u in users_to_invite:
            participants.append(Participant(meeting=meeting, user=u, rsvp_status='PENDING', attendance_status='PENDING'))
            notifications.append(InAppNotification(
                user=u, message=f"You have been invited to a new meeting: {title} on {date} at {time}",
                notification_type='INVITE', related_meeting=meeting
            ))
        Participant.objects.bulk_create(participants)
        InAppNotification.objects.bulk_create(notifications)
        
        from core.utils import send_meeting_invites
        from django.contrib import messages
        try:
            send_meeting_invites(meeting, users_to_invite)
            messages.success(request, f"Meeting created successfully! Invitations sent to {len(users_to_invite)} participants.")
        except Exception as e:
            messages.error(request, f"Meeting created, but there was an error sending emails: {e}")
        
        # Broadcast notification via WebSocket
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'meeting_notifications',
            {
                'type': 'meeting_message',
                'message': f"New meeting created: {title} on {date} at {time}"
            }
        )
        
        # Check if meeting is happening right now (within next 5 minutes or already started today)
        from django.utils import timezone
        import datetime
        try:
            meeting_datetime = timezone.make_aware(datetime.datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M"))
            now = timezone.now()
            # If the meeting is within 15 minutes of now (past or future), consider it "current time"
            if abs((meeting_datetime - now).total_seconds()) <= 15 * 60:
                if meeting_link:
                    return redirect(meeting_link)
        except Exception as e:
            pass
            
        return redirect('meetings')
        
    all_meetings = Meeting.objects.all().order_by('date', 'time')
    
    from django.utils import timezone
    import datetime
    now = timezone.now()
    
    meetings_list = []
    for m in all_meetings:
        try:
            m_dt_naive = datetime.datetime.combine(m.date, m.time)
            m_dt = timezone.make_aware(m_dt_naive)
            
            # Delete instantly when start time is reached
            if m_dt > now:
                meetings_list.append(m)
            else:
                # The user explicitly wants it removed from the system
                m.delete()
        except Exception as e:
            print(f"Error calculating end_time for meeting {m.id}: {e}")
            # Fallback if datetime combine fails for any reason
            meetings_list.append(m)

    from core.models import CustomUser
    registered_users = CustomUser.objects.all().order_by('-date_joined')
    return render(request, 'meetings.html', {'meetings': meetings_list, 'users': registered_users})

@login_required
def invite_user_view(request, user_id):
    if request.user.role != 'ADMIN':
        from django.contrib import messages
        messages.error(request, "Only Admin users can invite users.")
        return redirect('meetings')
        
    from core.models import CustomUser
    from django.core.mail import send_mail
    from django.conf import settings
    from django.contrib import messages
    
    try:
        user_to_invite = CustomUser.objects.get(id=user_id)
        
        subject = "You've been invited to a Meeting!"
        message = f"Hello {user_to_invite.username},\n\nYou have been invited to join a meeting on MeetingMind. Please log in to view your meetings.\n\nBest,\nMeetingMind Team"
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_to_invite.email],
            fail_silently=False,
        )
        messages.success(request, f"Invite successfully sent to {user_to_invite.email}!")
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
    except Exception as e:
        messages.error(request, f"Failed to send email to {user_to_invite.email}.")
        
    return redirect('meetings')

@login_required
def delete_user_view(request, user_id):
    if request.user.role != 'ADMIN':
        from django.contrib import messages
        messages.error(request, "Only Admin users can delete users.")
        return redirect('meetings')
        
    from core.models import CustomUser
    from django.contrib import messages
    try:
        user_to_delete = CustomUser.objects.get(id=user_id)
        if user_to_delete != request.user:
            user_to_delete.delete()
            messages.success(request, f"User {user_to_delete.username} deleted successfully.")
        else:
            messages.error(request, "You cannot delete yourself.")
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        
    return redirect('meetings')

@login_required
def delete_meeting_view(request, meeting_id):
    if request.user.role != 'ADMIN':
        from django.contrib import messages
        messages.error(request, "Only Admin users can delete meetings.")
        return redirect('meetings')
        
    from core.models import Meeting
    from django.contrib import messages
    try:
        meeting = Meeting.objects.get(id=meeting_id)
        meeting.delete()
        messages.success(request, f"Meeting '{meeting.title}' deleted successfully.")
    except Meeting.DoesNotExist:
        messages.error(request, "Meeting not found.")
        
    return redirect('meetings')

@login_required
def calendar_view(request):
    return render(request, 'calendar.html')

@login_required
def attendance_view(request):
    from core.models import Participant
    if request.user.role == 'ADMIN':
        participants = Participant.objects.all().order_by('-meeting__date', '-meeting__time')
    else:
        participants = Participant.objects.filter(user=request.user).order_by('-meeting__date', '-meeting__time')
        
    total = participants.count()
    present = participants.filter(attendance_status='ATTENDED').count()
    absent = participants.filter(attendance_status='ABSENT').count()
    late = participants.filter(attendance_status='LATE').count()
    
    return render(request, 'attendance.html', {
        'participants': participants,
        'total': total,
        'present': present,
        'absent': absent,
        'late': late,
    })

@login_required
def update_attendance(request, participant_id):
    if request.method == 'POST' and request.user.role == 'ADMIN':
        from core.models import Participant
        from django.contrib import messages
        try:
            p = Participant.objects.get(id=participant_id)
            new_status = request.POST.get('status')
            if new_status in dict(Participant._meta.get_field('attendance_status').choices):
                p.attendance_status = new_status
                p.save()
                messages.success(request, f"Updated attendance for {p.user.username}.")
        except Participant.DoesNotExist:
            messages.error(request, "Participant not found.")
    return redirect('attendance')

@login_required
def mom_view(request, meeting_id=None):
    from core.models import Meeting, MeetingMinutes
    import json
    
    if request.user.role == 'ADMIN':
        meetings = Meeting.objects.all().order_by('-date', '-time')
    else:
        meetings = Meeting.objects.filter(participants__user=request.user).order_by('-date', '-time')
        
    print(f"MOM VIEW Debug: User={request.user.username}, Role={request.user.role}, MeetingsCount={meetings.count()}")
        
    selected_meeting = None
    transcript_lines = []
    is_ongoing = False
    
    from django.utils import timezone
    import datetime
    
    if not meeting_id:
        now = timezone.localtime(timezone.now())
        print(f"MOM VIEW: NOW IS {now}")
        for m in meetings:
            start_dt = datetime.datetime.combine(m.date, m.time)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt, timezone.get_default_timezone())
            try:
                duration = int(m.duration)
            except:
                duration = 60
            end_dt = start_dt + datetime.timedelta(minutes=duration)
            print(f"MOM VIEW Checking Meeting ID {m.id} | {m.title} | start: {start_dt} | end: {end_dt} | now: {now} | is_ongoing: {start_dt <= now <= end_dt}")
            if start_dt <= now <= end_dt:
                from django.shortcuts import redirect
                return redirect('mom_detail', meeting_id=m.id)
    
    if meeting_id:
        from django.shortcuts import get_object_or_404
        selected_meeting = get_object_or_404(Meeting, id=meeting_id)
        
        minutes, _ = MeetingMinutes.objects.get_or_create(meeting=selected_meeting)
                
        # Calculate if currently ongoing
        start_dt = datetime.datetime.combine(selected_meeting.date, selected_meeting.time)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_default_timezone())
        try:
            duration = int(selected_meeting.duration)
        except:
            duration = 60
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        now = timezone.localtime(timezone.now())
        if start_dt <= now <= end_dt:
            is_ongoing = True
            
        # Try to load existing parsed transcript
        if minutes.history:
            try:
                transcript_lines = json.loads(minutes.history)
            except:
                transcript_lines = []
        else:
            # If the meeting ended and no transcript was recorded
            if not is_ongoing and minutes.status == 'PENDING':
                minutes.status = 'NO_TRANSCRIPT'
                minutes.save()

    return render(request, 'mom.html', {
        'meetings': meetings,
        'selected_meeting': selected_meeting,
        'transcript_lines': transcript_lines,
        'is_ongoing': is_ongoing,
        'minutes': selected_meeting.minutes if selected_meeting and hasattr(selected_meeting, 'minutes') else None
    })

@login_required
def tasks_view(request):
    tasks = ActionItem.objects.all()
    return render(request, 'tasks.html', {'tasks': tasks})

@login_required
def reports_view(request):
    return render(request, 'reports.html')

@login_required
def ai_features_view(request):
    return render(request, 'ai_features.html')

@login_required
def notifications_view(request):
    from core.models import InAppNotification
    notifications = request.user.notifications.all().order_by('-created_at')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'mark_all_read':
            notifications.update(is_read=True)
            return redirect('notifications')
            
    return render(request, 'notifications.html', {'notifications': notifications})

@login_required
def rsvp_view(request, meeting_id):
    if request.method == 'POST':
        from core.models import Participant
        from django.contrib import messages
        status = request.POST.get('status') # ACCEPTED, DECLINED, TENTATIVE
        try:
            participant = Participant.objects.get(meeting_id=meeting_id, user=request.user)
            if status in ['ACCEPTED', 'DECLINED', 'TENTATIVE']:
                participant.rsvp_status = status
                participant.save()
                messages.success(request, f"RSVP updated to {status}.")
        except Participant.DoesNotExist:
            messages.error(request, "You are not a participant of this meeting.")
            
    return redirect(request.META.get('HTTP_REFERER', 'notifications'))

@login_required
def settings_view(request):
    return render(request, 'settings.html')

def request_otp_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        from core.models import CustomUser, PasswordResetOTP
        from django.core.mail import send_mail
        from django.conf import settings
        import random
        import string
        
        try:
            user = CustomUser.objects.get(email=email)
            otp = ''.join(random.choices(string.digits, k=6))
            PasswordResetOTP.objects.create(user=user, otp=otp)
            
            subject = "Password Reset OTP"
            message = f"Your 6-digit OTP for password reset is: {otp}"
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
            
            request.session['reset_email'] = email
            return redirect('verify_otp')
        except CustomUser.DoesNotExist:
            # Silently redirect to avoid email enumeration
            request.session['reset_email'] = email
            return redirect('verify_otp')
            
    return render(request, 'registration/password_reset_form.html')

def verify_otp_view(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('password_reset')
        
    if request.method == 'POST':
        otp = request.POST.get('otp')
        from core.models import CustomUser, PasswordResetOTP
        from django.utils import timezone
        import datetime
        
        try:
            user = CustomUser.objects.get(email=email)
            otp_record = PasswordResetOTP.objects.filter(user=user, otp=otp, is_used=False).order_by('-created_at').first()
            if otp_record:
                # Check expiration (e.g. 15 minutes)
                if timezone.now() - otp_record.created_at < datetime.timedelta(minutes=15):
                    otp_record.is_used = True
                    otp_record.save()
                    request.session['otp_verified'] = True
                    return redirect('set_new_password')
                else:
                    return render(request, 'registration/password_reset_done.html', {'error': 'OTP has expired.'})
            else:
                return render(request, 'registration/password_reset_done.html', {'error': 'Invalid OTP.'})
        except CustomUser.DoesNotExist:
            return render(request, 'registration/password_reset_done.html', {'error': 'Invalid request.'})
            
    return render(request, 'registration/password_reset_done.html')

def set_new_password_view(request):
    email = request.session.get('reset_email')
    verified = request.session.get('otp_verified')
    if not email or not verified:
        return redirect('password_reset')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            return render(request, 'registration/password_reset_confirm.html', {'error': 'Passwords do not match.'})
            
        from core.models import CustomUser
        try:
            user = CustomUser.objects.get(email=email)
            user.set_password(password)
            user.save()
            
            # Clear session
            del request.session['reset_email']
            del request.session['otp_verified']
            
            return render(request, 'registration/password_reset_complete.html')
        except CustomUser.DoesNotExist:
            return redirect('password_reset')
            
    return render(request, 'registration/password_reset_confirm.html')

@login_required
def generate_summary(request, meeting_id):
    from core.models import Meeting, MeetingMinutes, ActionItem, CustomUser
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    import json
    import os
    import google.generativeai as genai
    
    meeting = get_object_or_404(Meeting, id=meeting_id)
    if not hasattr(meeting, 'minutes') or not meeting.minutes.history:
        return JsonResponse({'status': 'error', 'message': "No transcript available to summarize."})
        
    minutes = meeting.minutes
    minutes.status = 'GENERATING'
    minutes.save()
    
    try:
        transcript_lines = json.loads(minutes.history)
    except:
        transcript_lines = []
        
    transcript_text = "\n".join([f"{t.get('speaker', 'Unknown')}: {t.get('text', '')}" for t in transcript_lines])
    
    # Check if we have anything to summarize
    if len(transcript_text.strip()) < 10:
        minutes.status = 'NO_TRANSCRIPT'
        minutes.save()
        return JsonResponse({'status': 'error', 'message': "Transcript is too short."})
        
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        minutes.status = 'PENDING'
        minutes.save()
        return JsonResponse({'status': 'error', 'message': "GEMINI_API_KEY is not configured in .env"})
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
    You are an expert executive assistant. Review the following meeting transcript.
    Extract the following structured information and return it EXACTLY as a valid JSON object without markdown formatting blocks (do not wrap in ```json).
    {{
        "Summary": "A concise paragraph summarizing the overall meeting.",
        "Discussion_Points": ["Point 1", "Point 2"],
        "Decisions_Taken": ["Decision 1", "Decision 2"],
        "Action_Items": [
            {{"task": "Task description", "owner": "Assigned Person", "due_date": "YYYY-MM-DD or None"}}
        ]
    }}
    
    Transcript:
    {transcript_text}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        parsed = json.loads(result_text)
        
        # Format the discussion points into the AI summary text
        summary = parsed.get("Summary", "No summary provided.")
        discussion_pts = parsed.get("Discussion_Points", [])
        if discussion_pts:
            summary += "\n\n### Discussion Points\n- " + "\n- ".join(discussion_pts)
            
        minutes.ai_summary = summary
        minutes.decisions = parsed.get("Decisions_Taken", [])
        minutes.action_items_raw = parsed.get("Action_Items", [])
        minutes.save()
        
        # Optional: Auto-create Action Items in DB
        for item in minutes.action_items_raw:
            owner_str = item.get("owner", "")
            # Try to map owner to existing user
            owner_user = CustomUser.objects.filter(username__icontains=owner_str).first()
            if owner_user:
                ActionItem.objects.create(
                    meeting=meeting,
                    task_name=item.get("task", "New Task")[:255],
                    description=item.get("task", ""),
                    assigned_to=owner_user,
                    due_date=meeting.date # Fallback to meeting date
                )
        
        # Now automatically generate exports and save to FileFields
        from io import BytesIO
        from django.core.files.base import ContentFile
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import docx
        
        # PDF Generation
        try:
            pdf_buffer = BytesIO()
            p = canvas.Canvas(pdf_buffer, pagesize=letter)
            p.drawString(100, 750, f"Transcript: {meeting.title}")
            y = 730
            for line in transcript_lines:
                if y < 50:
                    p.showPage()
                    y = 750
                text = f"{line.get('speaker')}: {line.get('text')}"
                p.drawString(100, y, text[:90])
                y -= 15
            p.showPage()
            p.save()
            pdf_buffer.seek(0)
            minutes.pdf_export.save(f'transcript_{meeting.id}.pdf', ContentFile(pdf_buffer.read()), save=False)
        except Exception as e:
            print("Error generating PDF:", e)
            
        # DOCX Generation
        try:
            doc = docx.Document()
            doc.add_heading(f"Transcript: {meeting.title}", 0)
            for line in transcript_lines:
                p_doc = doc.add_paragraph()
                p_doc.add_run(f"{line.get('speaker')}: ").bold = True
                p_doc.add_run(f"{line.get('text')}")
            docx_buffer = BytesIO()
            doc.save(docx_buffer)
            docx_buffer.seek(0)
            minutes.docx_export.save(f'transcript_{meeting.id}.docx', ContentFile(docx_buffer.read()), save=False)
        except Exception as e:
            print("Error generating DOCX:", e)
            
        minutes.status = 'READY'
        minutes.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        minutes.status = 'PENDING'
        minutes.save()
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def export_pdf(request, meeting_id):
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from core.models import Meeting
    import json
    
    meeting = Meeting.objects.get(id=meeting_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="transcript_{meeting.id}.pdf"'
    
    p = canvas.Canvas(response, pagesize=letter)
    p.drawString(100, 750, f"Transcript: {meeting.title}")
    
    y = 730
    if hasattr(meeting, 'minutes') and meeting.minutes.history:
        try:
            lines = json.loads(meeting.minutes.history)
            for line in lines:
                if y < 50:
                    p.showPage()
                    y = 750
                # reportlab doesn't wrap text automatically with drawString, but this is a basic export
                text = f"{line.get('speaker')}: {line.get('text')}"
                p.drawString(100, y, text[:90]) # limit length to prevent runoff
                y -= 15
        except:
            pass
            
    p.showPage()
    p.save()
    return response

@login_required
def download_transcript(request, meeting_id):
    from django.http import HttpResponse
    from core.models import Meeting
    import json
    
    meeting = Meeting.objects.get(id=meeting_id)
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="transcript_{meeting.id}.txt"'
    
    if hasattr(meeting, 'minutes') and meeting.minutes.history:
        try:
            lines = json.loads(meeting.minutes.history)
            for line in lines:
                response.write(f"{line.get('speaker', 'Unknown')}: {line.get('text', '')}\n")
        except Exception as e:
            response.write(f"Error parsing transcript: {e}")
    else:
        response.write("No transcript available.")
        
    return response

@login_required
def download_ai_summary(request, meeting_id):
    from django.http import HttpResponse
    from core.models import Meeting
    import json
    
    meeting = Meeting.objects.get(id=meeting_id)
    response = HttpResponse(content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="ai_summary_{meeting.id}.json"'
    
    if hasattr(meeting, 'minutes'):
        data = {
            "title": meeting.title,
            "date": str(meeting.date),
            "summary": meeting.minutes.ai_summary,
            "decisions": meeting.minutes.decisions,
            "action_items": meeting.minutes.action_items_raw
        }
        response.write(json.dumps(data, indent=4))
    else:
        response.write(json.dumps({"error": "No minutes available."}))
        
    return response

@login_required
def export_docx(request, meeting_id):
    from django.http import HttpResponse
    import docx
    from core.models import Meeting
    import json
    import io
    
    meeting = Meeting.objects.get(id=meeting_id)
    doc = docx.Document()
    doc.add_heading(f"Transcript: {meeting.title}", 0)
    
    if hasattr(meeting, 'minutes') and meeting.minutes.history:
        try:
            lines = json.loads(meeting.minutes.history)
            for line in lines:
                p = doc.add_paragraph()
                p.add_run(f"{line.get('speaker')}: ").bold = True
                p.add_run(f"{line.get('text')}")
        except:
            pass
            
    f = io.BytesIO()
    doc.save(f)
    length = f.tell()
    f.seek(0)
    response = HttpResponse(f.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="transcript_{meeting.id}.docx"'
    response['Content-Length'] = length
    return response

@login_required
def export_txt(request, meeting_id):
    from django.http import HttpResponse
    from core.models import Meeting
    import json
    
    meeting = Meeting.objects.get(id=meeting_id)
    content = f"Transcript: {meeting.title}\n\n"
    
    if hasattr(meeting, 'minutes') and meeting.minutes.history:
        try:
            lines = json.loads(meeting.minutes.history)
            for line in lines:
                content += f"{line.get('speaker')}: {line.get('text')}\n"
        except:
            pass
            
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="transcript_{meeting.id}.txt"'
    return response

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
@login_required
def autosave_transcript(request, meeting_id):
    from core.models import Meeting, MeetingMinutes
    import json
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            transcript_text = data.get('transcript', '')
            mode = data.get('mode', 'replace')
            
            if not transcript_text:
                return JsonResponse({'status': 'empty'})
                
            meeting = Meeting.objects.get(id=meeting_id)
            
            # Parse lines simply
            lines = transcript_text.strip().split('\n')
            parsed_lines = []
            for line in lines:
                if ':' in line:
                    speaker, text = line.split(':', 1)
                    parsed_lines.append({'speaker': speaker.strip(), 'text': text.strip()})
                else:
                    parsed_lines.append({'speaker': 'Unknown', 'text': line.strip()})
                    
            minutes, created = MeetingMinutes.objects.get_or_create(meeting=meeting, defaults={'notes': 'Autosaved transcript'})
            
            if mode == 'append':
                existing_history = []
                if minutes.history:
                    try:
                        existing_history = json.loads(minutes.history)
                    except:
                        pass
                existing_history.extend(parsed_lines)
                minutes.history = json.dumps(existing_history)
            else:
                minutes.history = json.dumps(parsed_lines)
                
            minutes.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'invalid method'})

@login_required
def latest_transcript(request, meeting_id):
    from core.models import Meeting
    import json
    import datetime
    from django.utils import timezone
    from django.http import JsonResponse
    
    try:
        meeting = Meeting.objects.get(id=meeting_id)
        
        # Check if still ongoing
        start_dt = datetime.datetime.combine(meeting.date, meeting.time)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_default_timezone())
        try:
            duration = int(meeting.duration)
        except:
            duration = 60
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        now = timezone.localtime(timezone.now())
        is_ongoing = start_dt <= now <= end_dt
        
        lines = []
        if hasattr(meeting, 'minutes') and meeting.minutes and meeting.minutes.history:
            lines = json.loads(meeting.minutes.history)
            
        return JsonResponse({'status': 'success', 'lines': lines, 'is_ongoing': is_ongoing})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def unread_notification_count(request):
    from django.http import JsonResponse
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'status': 'success', 'count': count})

@login_required
def fetch_notifications(request):
    from django.http import JsonResponse
    notifications = request.user.notifications.order_by('-created_at')[:20]
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'message': n.message,
            'type': n.notification_type,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d, %I:%M %p'),
            'meeting_id': n.related_meeting.id if n.related_meeting else None
        })
    return JsonResponse({'status': 'success', 'notifications': data})

@login_required
def mark_notification_read(request, notification_id):
    from django.http import JsonResponse
    from core.models import InAppNotification
    try:
        notification = InAppNotification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except InAppNotification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'})
