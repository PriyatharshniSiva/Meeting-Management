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

def send_meeting_invites(meeting, users):
    if not users:
        return
        
    ics_data = generate_ics(meeting)
    
    for user in users:
        subject = f"Meeting Invitation: {meeting.title}"
        text_content = f"Hello {user.username},\n\nYou have been invited to a meeting: {meeting.title}.\nOrganizer: {meeting.created_by.username}\nDate: {meeting.date} at {meeting.time}\nAgenda: {meeting.description}\nLink: {meeting.meeting_link or 'N/A'}\n\nPlease check your dashboard to RSVP."
        
        html_content = f"""
        <html>
            <body style="font-family: sans-serif; color: #333;">
                <h2>Meeting Invitation: {meeting.title}</h2>
                <p>Hello <strong>{user.username}</strong>,</p>
                <p>You have been invited to a meeting organized by <strong>{meeting.created_by.username}</strong>.</p>
                <ul>
                    <li><strong>Title:</strong> {meeting.title}</li>
                    <li><strong>Date & Time:</strong> {meeting.date} at {meeting.time}</li>
                    <li><strong>Agenda / Description:</strong> {meeting.description}</li>
                    <li><strong>Meeting Link / Location:</strong> <a href="{meeting.meeting_link or '#'}">{meeting.meeting_link or meeting.location or 'N/A'}</a></li>
                </ul>
                <br>
                <a href="http://127.0.0.1:8000/" style="padding: 10px 20px; background-color: #6d28d9; color: white; text-decoration: none; border-radius: 5px;">View Meeting</a>
            </body>
        </html>
        """
        
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
        msg.attach_alternative(html_content, "text/html")
        msg.attach('invite.ics', ics_data, 'text/calendar')
        
        try:
            msg.send(fail_silently=False)
        except Exception as e:
            print(f"FAILED TO SEND EMAIL TO {user.email}: {e}")
