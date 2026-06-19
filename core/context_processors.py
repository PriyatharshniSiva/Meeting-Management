from django.utils import timezone
import datetime
from core.models import Meeting

def ongoing_meeting_processor(request):
    if not request.user.is_authenticated:
        return {'global_ongoing_meeting': None}
        
    now = timezone.localtime(timezone.now())
    if request.user.role == 'ADMIN':
        meetings = Meeting.objects.all()
    else:
        meetings = Meeting.objects.filter(participants__user=request.user)
        
    for m in meetings:
        start_dt = datetime.datetime.combine(m.date, m.time)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_default_timezone())
        try:
            duration = int(m.duration)
        except:
            duration = 60
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        if start_dt <= now <= end_dt:
            return {'global_ongoing_meeting': m}
            
    return {'global_ongoing_meeting': None}
