from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

def send_meeting_reminders():
    from core.models import Meeting, Participant, InAppNotification
    now = timezone.now()
    
    meetings = Meeting.objects.all()
    for meeting in meetings:
        # Construct datetime aware object for the meeting start
        try:
            meeting_datetime = timezone.make_aware(timezone.datetime.combine(meeting.date, meeting.time))
        except ValueError:
            # Already aware or tz issue
            meeting_datetime = timezone.datetime.combine(meeting.date, meeting.time)
            if timezone.is_naive(meeting_datetime):
                meeting_datetime = timezone.make_aware(meeting_datetime)

        time_diff = meeting_datetime - now
        minutes_until = time_diff.total_seconds() / 60
        
        reminder_type = None
        if 1435 <= minutes_until <= 1445:  # ~24 hours
            reminder_type = '24h'
        elif 55 <= minutes_until <= 65:  # ~1 hour
            reminder_type = '1h'
        elif 10 <= minutes_until <= 20:  # ~15 mins
            reminder_type = '15m'
            
        if reminder_type:
            participants = Participant.objects.filter(meeting=meeting, rsvp_status__in=['ACCEPTED', 'PENDING'])
            for participant in participants:
                is_external = not participant.user
                recipient_name = participant.external_name if is_external else participant.user.username
                recipient_email = participant.external_email if is_external else participant.user.email
                
                msg = f"Reminder: Your meeting '{meeting.title}' is starting in {reminder_type.replace('h', ' hours').replace('m', ' minutes')}."
                
                # In App Notification (Only for internal users)
                if not is_external:
                    if not InAppNotification.objects.filter(user=participant.user, related_meeting=meeting, message=msg).exists():
                        InAppNotification.objects.create(
                            user=participant.user,
                            message=msg,
                            notification_type='REMINDER',
                            related_meeting=meeting
                        )
                
                # Email Reminder
                from django.core.mail import send_mail
                from django.conf import settings
                from core.models import EmailLog
                
                subject = f"Meeting Reminder: {meeting.title}"
                html_message = f"""
                <html>
                <body>
                    <p>Hello {recipient_name},</p>
                    <p>{msg}</p>
                    <p>Date: {meeting.date} at {meeting.time}</p>
                    <p>Meeting Link: <a href="{meeting.meeting_link or '#'}">{meeting.meeting_link or meeting.location or 'N/A'}</a></p>
                </body>
                </html>
                """
                
                if not EmailLog.objects.filter(meeting=meeting, recipient_email=recipient_email, subject=subject).exists():
                    try:
                        send_mail(
                            subject,
                            msg,
                            settings.DEFAULT_FROM_EMAIL,
                            [recipient_email],
                            html_message=html_message,
                            fail_silently=False,
                        )
                        EmailLog.objects.create(
                            meeting=meeting,
                            recipient_email=recipient_email,
                            subject=subject,
                            body=html_message
                        )
                        logger.info(f"Sent {reminder_type} reminder email for meeting {meeting.title} to {recipient_name}")
                    except Exception as e:
                        logger.error(f"Failed to send reminder email to {recipient_email}: {e}")

def start():
    scheduler = BackgroundScheduler()
    # Run every 5 minutes
    scheduler.add_job(
        send_meeting_reminders,
        trigger=IntervalTrigger(minutes=5),
        id='meeting_reminders',
        name='Send Meeting Reminders',
        replace_existing=True,
    )
    scheduler.start()
