from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Owner/Admin'),
        ('TL', 'Team Leader'),
        ('EMPLOYEE', 'Employee'),
        ('INTERN', 'Intern'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')

    @property
    def unread_notifications_count(self):
        return self.notifications.filter(is_read=False).count()

class Meeting(models.Model):
    TYPE_CHOICES = (
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
    )
    title = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    meeting_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='ONLINE')
    location = models.CharField(max_length=255, blank=True, null=True)
    meeting_link = models.URLField(max_length=500, blank=True, null=True, help_text="Link for online meetings")
    description = models.TextField()
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_meetings')
    created_at = models.DateTimeField(auto_now_add=True)
    target_roles = models.JSONField(default=list, blank=True, help_text="List of roles invited to this meeting")

    def __str__(self):
        return self.title

class Participant(models.Model):
    STATUS_CHOICES = (
        ('ATTENDED', 'Attended'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('PENDING', 'Pending'),
    )
    RSVP_CHOICES = (
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
        ('TENTATIVE', 'Tentative'),
    )
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rsvp_status = models.CharField(max_length=20, choices=RSVP_CHOICES, default='PENDING')
    attendance_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

class MeetingMinutes(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Transcript'),
        ('PROCESSING', 'Processing Transcript'),
        ('GENERATING', 'Generating AI Summary'),
        ('READY', 'Minutes Ready'),
        ('NO_TRANSCRIPT', 'No Transcript Available'),
    )
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name='minutes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField()
    history = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to='mom_attachments/', blank=True, null=True)
    ai_summary = models.TextField(blank=True, null=True)
    decisions = models.JSONField(default=list, blank=True)
    action_items_raw = models.JSONField(default=list, blank=True)
    agenda = models.TextField(blank=True, null=True)
    pdf_export = models.FileField(upload_to='exports/pdf/', blank=True, null=True)
    docx_export = models.FileField(upload_to='exports/docx/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ActionItem(models.Model):
    PRIORITY_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('BLOCKED', 'Blocked'),
    )
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='action_items')
    task_name = models.CharField(max_length=255)
    description = models.TextField()
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assigned_tasks')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.task_name

class InAppNotification(models.Model):
    NOTIFICATION_TYPES = (
        ('INVITE', 'Meeting Invite'),
        ('REMINDER', 'Meeting Reminder'),
        ('SYSTEM', 'System Alert'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='SYSTEM')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_meeting = models.ForeignKey(Meeting, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.notification_type}"

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username} - {self.otp}"
