from datetime import datetime
from django.utils import timezone
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.views import APIView
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from utils.nlp_utils import extract_email_entities
from django.http import JsonResponse
from utils.email_utils import get_headers_value
from .models import EmailMetadata
from .serializers import GmailMessageSerializer

class GmailDataView(APIView):
    def get(self, request, *args, **kwargs):
        # Check if credentials exist in session
        creds_data = request.session.get('credentials')
        if not creds_data:
            return redirect('authorize')

        # Load credentials from session
        creds = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )

        # Refresh the token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            request.session['credentials'] = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }

        # Build Gmail API service
        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])

        # Fetch detailed message content
        detailed_messages = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            detailed_messages.append({
                'id': msg['id'],
                'snippet': msg['snippet'],
                'subject': next(
                    (header['value'] for header in msg['payload']['headers'] if header['name'] == 'Subject'), 
                    'No Subject'
                ),
                'sender': next(
                    (header['value'] for header in msg['payload']['headers'] if header['name'] == 'From'), 
                    'Unknown'
                )
            })

        # Serialize the messages and return as JSON response
        serializer = GmailMessageSerializer(detailed_messages, many=True)
        return Response(serializer.data)


def fetch_and_store_emails(request):
    """Fetch emails, analyze with spaCy, and store metadata in the database."""
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

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()

        email_body = msg.get('snippet', '')  # Get a short preview of the email
        metadata = extract_email_entities(email_body)

        # Convert the timestamp to a naive datetime as google use a different timezone
        timestamp_ms = int(msg.get('internalDate', 0))
        sent_at_naive = datetime.fromtimestamp(timestamp_ms / 1000)

        # Make the datetime timezone-aware
        sent_at = timezone.make_aware(sent_at_naive, timezone=timezone.get_current_timezone())
        
        sender = get_headers_value(msg['payload']['headers'], 'From')
        recipient = get_headers_value(msg['payload']['headers'], 'To')

        if not sender:
            sender = 'Unknown Sender'
        if not recipient:
            recipient = 'Unknown Recipient'    
        # Save email metadata to the database
        EmailMetadata.objects.create(
            sender=sender, 
            recipient=recipient,
            subject=msg.get('snippet', 'No Subject'),
            persons=metadata["persons"],
            organizations=metadata["organizations"],
            job_titles=metadata["job_titles"],
            dates=metadata["dates"],
            sent_at=sent_at,
            responded=False  # Initial value; can update later
        )

    return JsonResponse({'message': 'Emails processed and saved successfully.'}, status=200)