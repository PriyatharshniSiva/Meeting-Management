import time
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Meeting, Participant, InAppNotification
from core.utils import send_meeting_invites

class Command(BaseCommand):
    help = 'Runs a continuous background process to send meeting reminders.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Started Meeting Reminder Daemon..."))
        
        while True:
            now = timezone.localtime(timezone.now())
            target_time_lower = now + datetime.timedelta(minutes=14, seconds=50)
            target_time_upper = now + datetime.timedelta(minutes=15, seconds=10)
            
            # Find meetings starting in exactly 15 minutes (with a 10-second buffer)
            meetings = Meeting.objects.all()
            for meeting in meetings:
                start_dt = datetime.datetime.combine(meeting.date, meeting.time)
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt, timezone.get_default_timezone())
                
                if target_time_lower <= start_dt <= target_time_upper:
                    # Time to send a reminder!
                    # Only send to participants who accepted or are pending
                    participants = Participant.objects.filter(meeting=meeting, rsvp_status__in=['ACCEPTED', 'PENDING'])
                    users_to_remind = [p.user for p in participants]
                    
                    if users_to_remind:
                        self.stdout.write(f"Sending reminders for: {meeting.title} to {len(users_to_remind)} users")
                        
                        # Create In-App Notifications
                        notifications = []
                        for u in users_to_remind:
                            notifications.append(InAppNotification(
                                user=u,
                                message=f"Reminder: '{meeting.title}' is starting in 15 minutes!",
                                notification_type='REMINDER',
                                related_meeting=meeting
                            ))
                        InAppNotification.objects.bulk_create(notifications)
                        
                        # Send emails
                        from django.core.mail import EmailMultiAlternatives
                        from django.conf import settings
                        
                        for user in users_to_remind:
                            subject = f"Reminder: Meeting '{meeting.title}' starts in 15 minutes!"
                            text_content = f"Hello {user.username},\n\nThis is a friendly reminder that your meeting '{meeting.title}' organized by {meeting.created_by.username} starts in 15 minutes.\nDate & Time: {meeting.date} at {meeting.time}\nLink: {meeting.meeting_link or 'N/A'}"
                            
                            html_content = f"""
                            <html>
                                <body style="font-family: sans-serif; color: #333;">
                                    <h2>Meeting Reminder</h2>
                                    <p>Hello <strong>{user.username}</strong>,</p>
                                    <p>This is a reminder that the meeting <strong>{meeting.title}</strong> is starting in 15 minutes.</p>
                                    <ul>
                                        <li><strong>Date & Time:</strong> {meeting.date} at {meeting.time}</li>
                                        <li><strong>Meeting Link / Location:</strong> <a href="{meeting.meeting_link or '#'}">{meeting.meeting_link or meeting.location or 'N/A'}</a></li>
                                    </ul>
                                </body>
                            </html>
                            """
                            msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
                            msg.attach_alternative(html_content, "text/html")
                            try:
                                msg.send(fail_silently=False)
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"Failed email to {user.email}: {e}"))
                                
            # Sleep for 10 seconds before checking again
            time.sleep(10)
