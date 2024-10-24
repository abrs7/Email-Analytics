from django.http import JsonResponse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import timedelta
from django.utils import timezone
from main.models import EmailMetadata
from .email_utils import get_headers_value
from datetime import datetime


def get_data_from_gmail(request):
    creds_data = request.session.get('credentials')
    if not creds_data:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data['refresh_token'],
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me').execute()
    messages = results.get('messages', [])
    
    full_messages = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        full_messages.append(msg)
        print(f"Extracted email body: {msg['snippet']}")
    
    return full_messages
