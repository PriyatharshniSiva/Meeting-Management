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
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6; padding: 20px; margin: 0; color: #1f2937; line-height: 1.6;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
                
                <!-- Header -->
                <div style="background-color: #4f46e5; color: #ffffff; padding: 30px 20px; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">Meeting Invitation</h1>
                </div>
                
                <!-- Body -->
                <div style="padding: 30px;">
                    <p style="font-size: 18px; margin-top: 0;">Hello <strong>{recipient_name}</strong>,</p>
                    <p style="font-size: 16px; color: #4b5563;">You have been invited to a meeting organized by <strong>{meeting.created_by.username}</strong>.</p>
                    
                    <!-- Details Card -->
                    <div style="margin-top: 30px; margin-bottom: 30px;">
                        <h2 style="font-size: 20px; font-weight: 600; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-bottom: 20px;">Meeting Details</h2>
                        
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; width: 120px; font-weight: 600; color: #6b7280; font-size: 16px;">Title:</td>
                                <td style="padding: 8px 0; font-weight: 500; font-size: 16px;">{meeting.title}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: 600; color: #6b7280; font-size: 16px;">Date:</td>
                                <td style="padding: 8px 0; font-weight: 500; font-size: 16px;">{meeting.date}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: 600; color: #6b7280; font-size: 16px;">Time:</td>
                                <td style="padding: 8px 0; font-weight: 500; font-size: 16px;">{meeting.time}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: 600; color: #6b7280; font-size: 16px;">Duration:</td>
                                <td style="padding: 8px 0; font-weight: 500; font-size: 16px;">{meeting.duration} mins</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: 600; color: #6b7280; font-size: 16px;">Agenda:</td>
                                <td style="padding: 8px 0; font-weight: 500; font-size: 16px;">{meeting.description or 'No agenda provided'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: 600; color: #6b7280; font-size: 16px;">Link/Location:</td>
                                <td style="padding: 8px 0; font-size: 16px;"><a href="{meeting.meeting_link or '#'}" style="color: #4f46e5; text-decoration: none; font-weight: 500;">{meeting.meeting_link or meeting.location or 'N/A'}</a></td>
                            </tr>
                        </table>
                    </div>
                    
                    <!-- Action Section -->
                    <div style="background-color: #f9fafb; border: 1px solid #f3f4f6; border-radius: 8px; padding: 25px; text-align: center;">
                        <h2 style="font-size: 20px; font-weight: 600; color: #111827; margin-top: 0; margin-bottom: 20px;">Action Required</h2>
                        <p style="font-size: 15px; color: #4b5563; margin-bottom: 25px;">Please confirm your attendance by clicking one of the buttons below:</p>
                        
                        <div style="display: flex; justify-content: center; gap: 15px; flex-wrap: wrap;">
                            <a href="{accept_link}" style="display: inline-block; padding: 14px 28px; background-color: #10b981; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; border-radius: 6px; box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);">✅ Accept Invitation</a>
                            <a href="{decline_link}" style="display: inline-block; padding: 14px 28px; background-color: #ef4444; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; border-radius: 6px; box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);">❌ Decline Invitation</a>
                        </div>
                    </div>
                    
                </div>
                <!-- Footer -->
                <div style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                    <p style="font-size: 13px; color: #9ca3af; margin: 0;">Powered by MeetingMind</p>
                </div>
            </div>
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
