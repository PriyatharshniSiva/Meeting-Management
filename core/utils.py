from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from icalendar import Calendar, Event
import pytz
from datetime import datetime

def generate_ics(meeting):
    cal = Calendar()
    cal.add('prodid', '-//Meeting Management System//mxm.dk//')
    cal.add('version', '2.0')
    
    event = Event()
    event.add('summary', meeting.title)
    
    # Combine date and time
    meeting_dt = datetime.combine(meeting.date, meeting.time)
    
    # Needs to be timezone aware
    timezone = pytz.timezone(settings.TIME_ZONE)
    meeting_dt = timezone.localize(meeting_dt)
    
    event.add('dtstart', meeting_dt)
    event.add('description', meeting.description)
    if meeting.location:
        event.add('location', meeting.location)
    
    cal.add_component(event)
    return cal.to_ical()

def send_meeting_invites(meeting, participants):
    from core.models import EmailLog
    if not participants:
        return
        
    ics_data = generate_ics(meeting)
    
    for participant in participants:
        is_external = not participant.user
        recipient_email = participant.external_email if is_external else participant.user.email
        recipient_name = participant.external_name if is_external else participant.user.username
        
        subject = f"Meeting Invitation: {meeting.title}"
        text_content = f"Hello {recipient_name},\n\nYou have been invited to a meeting: {meeting.title}.\nOrganizer: {meeting.created_by.username}\nDate: {meeting.date} at {meeting.time}\nDuration: {meeting.duration} mins\nAgenda: {meeting.description}\nLink: {meeting.meeting_link or 'N/A'}\n\nPlease click Accept or Decline."
        
        # Build RSVP links
        accept_link = f"http://127.0.0.1:8000/meetings/rsvp_email/{meeting.id}/?participant_id={participant.id}&status=ACCEPTED"
        decline_link = f"http://127.0.0.1:8000/meetings/rsvp_email/{meeting.id}/?participant_id={participant.id}&status=DECLINED"
        
        html_content = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <h2>Meeting Invitation: {meeting.title}</h2>
                <p>Hello <strong>{recipient_name}</strong>,</p>
                <p>You have been invited to a meeting organized by <strong>{meeting.created_by.username}</strong>.</p>
                <div style="background: #f4f4f5; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <ul style="list-style-type: none; padding: 0;">
                        <li><strong>Title:</strong> {meeting.title}</li>
                        <li><strong>Date:</strong> {meeting.date}</li>
                        <li><strong>Time:</strong> {meeting.time}</li>
                        <li><strong>Duration:</strong> {meeting.duration} mins</li>
                        <li><strong>Agenda:</strong> {meeting.description}</li>
                        <li><strong>Location/Link:</strong> <a href="{meeting.meeting_link or '#'}">{meeting.meeting_link or meeting.location or 'N/A'}</a></li>
                    </ul>
                </div>
                
                <p>Please respond to this invitation:</p>
                <a href="{accept_link}" style="padding: 10px 20px; background-color: #10b981; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px; display: inline-block;">✅ Accept Meeting</a>
                <a href="{decline_link}" style="padding: 10px 20px; background-color: #ef4444; color: white; text-decoration: none; border-radius: 5px; display: inline-block;">❌ Decline Meeting</a>
            </body>
        </html>
        """
        
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [recipient_email])
        msg.attach_alternative(html_content, "text/html")
        msg.attach('invite.ics', ics_data, 'text/calendar')
        
        if meeting.attachment:
            import mimetypes
            import os
            mime_type, _ = mimetypes.guess_type(meeting.attachment.name)
            mime_type = mime_type or 'application/octet-stream'
            msg.attach(os.path.basename(meeting.attachment.name), meeting.attachment.read(), mime_type)
            meeting.attachment.seek(0)
        
        try:
            msg.send(fail_silently=False)
            EmailLog.objects.create(
                meeting=meeting,
                recipient_email=recipient_email,
                subject=subject,
                body=html_content
            )
        except Exception as e:
            print(f"FAILED TO SEND EMAIL TO {recipient_email}: {e}")
