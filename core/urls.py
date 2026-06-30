from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='root_login'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    
    path('meetings/', views.meetings_view, name='meetings'),
    path('meetings/invite/<int:user_id>/', views.invite_user_view, name='invite_user'),
    path('meetings/delete/<int:user_id>/', views.delete_user_view, name='delete_user'),
    path('meeting/delete/<int:meeting_id>/', views.delete_meeting_view, name='delete_meeting'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/update_time/', views.update_meeting_time, name='update_meeting_time'),
    path('attendance/', views.attendance_view, name='attendance'),
    path('attendance/update/<int:participant_id>/', views.update_attendance, name='update_attendance'),
    
    path('meetings/rsvp/<int:meeting_id>/', views.rsvp_view, name='rsvp'),
    path('meetings/rsvp_email/<int:meeting_id>/', views.rsvp_email_view, name='rsvp_email'),
    path('meetings/join/<int:meeting_id>/', views.join_meeting, name='join_meeting'),
    path('meetings/leave/<int:meeting_id>/', views.leave_meeting, name='leave_meeting'),
    
    path('mom/', views.mom_view, name='mom'),
    path('mom/<int:meeting_id>/', views.mom_view, name='mom_detail'),
    path('mom/<int:meeting_id>/content/', views.mom_content_partial, name='mom_content_partial'),
    path('mom/<int:meeting_id>/upload_audio/', views.upload_audio_for_transcription, name='upload_audio_for_transcription'),
    path('mom/<int:meeting_id>/paste_text/', views.paste_transcript_text, name='paste_transcript_text'),
    path('mom/<int:meeting_id>/check_status/', views.check_transcription_status, name='check_transcription_status'),
    path('mom/<int:meeting_id>/export/<str:format>/', views.export_transcript, name='export_transcript'),
    path('mom/autosave/<int:meeting_id>/', views.autosave_transcript, name='autosave_transcript'),
    path('mom/latest/<int:meeting_id>/', views.latest_transcript, name='latest_transcript'),
    
    path('transcription/<int:meeting_id>/retry/', views.retry_transcription_view, name='retry_transcription'),
    path('transcription/<int:meeting_id>/delete/', views.delete_transcription_view, name='delete_transcription'),
    path('zoom/webhook/', views.zoom_webhook, name='zoom_webhook'),
    path('zoom/simulate/<int:meeting_id>/', views.simulate_zoom_webhook, name='simulate_zoom_webhook'),
    
    # Notifications AJAX
    path('notifications/unread-count/', views.unread_notification_count, name='unread_notification_count'),
    path('notifications/fetch/', views.fetch_notifications, name='fetch_notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    
    path('mom/generate_summary/<int:meeting_id>/', views.generate_summary, name='generate_summary'),
    path('mom/export/pdf/<int:meeting_id>/', views.export_pdf, name='export_pdf'),
    path('mom/export/docx/<int:meeting_id>/', views.export_docx, name='export_docx'),
    path('mom/export/txt/<int:meeting_id>/', views.export_txt, name='export_txt'),
    path('mom/download/transcript/<int:meeting_id>/', views.download_transcript, name='download_transcript'),
    path('mom/download/ai_summary/<int:meeting_id>/', views.download_ai_summary, name='download_ai_summary'),
    
    path('tasks/', views.tasks_view, name='tasks'),
    path('reports/', views.reports_view, name='reports'),
    path('ai-features/', views.ai_features_view, name='ai_features'),
    
    # Projects
    path('projects/', views.projects_view, name='projects'),
    path('projects/edit/<int:project_id>/', views.edit_project, name='edit_project'),
    path('projects/delete/<int:project_id>/', views.delete_project, name='delete_project'),
    path('projects/accept/<int:project_id>/', views.accept_project, name='accept_project'),
    path('projects/decline/<int:project_id>/', views.decline_project, name='decline_project'),
    
    path('settings/', views.settings_view, name='settings'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('rsvp/<int:meeting_id>/', views.rsvp_view, name='rsvp'),
    path('password_reset/', views.request_otp_view, name='password_reset'),
    path('password_reset/verify/', views.verify_otp_view, name='verify_otp'),
    path('password_reset/new_password/', views.set_new_password_view, name='set_new_password'),
]
