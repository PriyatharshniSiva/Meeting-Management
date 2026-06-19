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
            participants = Participant.objects.filter(meeting=meeting, rsvp_status='ACCEPTED')
            for participant in participants:
                msg = f"Reminder: Your meeting '{meeting.title}' is starting in {reminder_type.replace('h', ' hours').replace('m', ' minutes')}."
                if not InAppNotification.objects.filter(user=participant.user, related_meeting=meeting, message=msg).exists():
                    InAppNotification.objects.create(
                        user=participant.user,
                        message=msg,
                        notification_type='REMINDER',
                        related_meeting=meeting
                    )
                    logger.info(f"Sent {reminder_type} reminder for meeting {meeting.title} to {participant.user.username}")

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
