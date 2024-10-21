from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from django.utils import timezone
from main.models import EmailMetadata
from utils.email_utils import get_headers_value
from utils.response_utils import get_data_from_gmail

def check_email_responses():
    """Function to check for responses to sent emails."""
    emails = EmailMetadata.objects.filter(responded=False)
    for email in emails:
        if email.sender == email.user.email:
            responder = email.recipient
            messages = get_data_from_gmail(None)  # Pass session if needed
            for msg in messages:
                sender = get_headers_value(msg['payload']['headers'], 'From')
                timestamp_ms = int(msg.get('internalDate', 0))
                sent_at_naive = datetime.fromtimestamp(timestamp_ms / 1000)
                sent_at = timezone.make_aware(sent_at_naive, timezone.get_current_timezone())

                if sender == responder and email.sent_at < sent_at:
                    email.responded = True
                    email.save()
                    print(f'Email {email.id} marked as responded.')

def start_scheduler():
    """Starts the APScheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_email_responses, 'interval', minutes=5)
    scheduler.start()
