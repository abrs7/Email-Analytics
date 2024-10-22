from datetime import datetime
from django.utils import timezone
from django.shortcuts import redirect, render
from urllib.parse import urlencode
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from utils.nlp_utils import extract_email_entities, extract_keywords, find_bullet_poits
from django.http import JsonResponse, HttpResponseRedirect
from decouple import config
from utils.email_utils import get_headers_value, get_email_body, get_gmail_service, get_thread_messages, list_gmail_messages, extract_email_address
from utils.func_utils import TIME_SLOTS, classify_email_by_time_slot
from .models import EmailMetadata
from .serializers import GmailMessageSerializer, EmailMetadataSerializer
import logging

logger = logging.getLogger(__name__)

class GmailDataView(APIView):
    def get(self, request, *args, **kwargs):
        # Check if credentials exist in session
        creds_data = request.session.get('credentials')
        if not creds_data:
            return redirect('authorize')

        # Load credentials from session
        try:
            creds = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )
        except KeyError as e:
            return Response({"error": f"Missing credential field: {str(e)}"}, status=400)     

        # Refresh the token if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                request.session['credentials'] = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
            except Exception as e:
                return Response({"error": f"Failed to refresh credentials: {str(e)}"}, status=500)    

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
        email_length = len(email_body)
        bullet_points = find_bullet_poits(email_body)
        # Extract keywords from email content using NLP
        keywords = extract_keywords(email_body)
        metadata = extract_email_entities(email_body)
        email_body = get_email_body(msg) 
        # Convert the timestamp to a naive datetime as google use a different timezone
        timestamp_ms = int(msg.get('internalDate', 0))
        sent_at_naive = datetime.fromtimestamp(timestamp_ms / 1000)

        # Make the datetime timezone-aware
        sent_at = timezone.make_aware(sent_at_naive, timezone=timezone.get_current_timezone())
        
        sender = get_headers_value(msg['payload']['headers'], 'From')
        recipient = get_headers_value(msg['payload']['headers'], 'To')
        subject = get_headers_value(msg['payload']['headers'], 'Subject') 

        if not sender:
            sender = 'Unknown Sender'
        if not recipient:
            recipient = 'Unknown Recipient'    
        # Save email metadata to the database
        EmailMetadata.objects.create(
            sender=sender, 
            recipient=recipient,
            subject=subject,
            email_body=email_body,
            persons=metadata["persons"],
            organizations=metadata["organizations"],
            job_titles=metadata["job_titles"],
            dates=metadata["dates"],
            sent_at=sent_at,
            responded=False , # Initial value; can update later
            email_length=email_length,
            bullet_points=bullet_points,
            keywords=keywords,
            user=request.user
        )

    return JsonResponse({'message': 'Emails processed and saved successfully.'}, status=200)

class EmailMetadataListView(ListAPIView):
    queryset = EmailMetadata.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = EmailMetadataSerializer
    
    def get_queryset(self):
        # Filter emails to only show those belonging to the logged-in user
        return EmailMetadata.objects.filter(user=self.request.user)

def google_login(request):
    params = {
        'response_type': 'code',
        'client_id': config('GOOGLE_CLIENT_ID'),
        'redirect_uri': 'https://email-analytics-surl.onrender.com/oauth2callback',
        'scope': 'https://www.googleapis.com/auth/gmail.readonly',
        'state': 'random_state_string',
        'access_type': 'offline',
        'prompt': 'consent',
        'include_granted_scopes': 'true',
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    return HttpResponseRedirect(google_auth_url)

def get_response_mail_data_time(request):
    creds_data = request.session.get('credentials')
    if not creds_data:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    creds = Credentials(**creds_data)
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me').execute()
    messages = results.get('messages', [])

    response_times = []

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        thread_id = msg.get('threadId')

        # Fetch all messages in the thread
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages_in_thread = thread.get('messages', [])

        # Identify sent and response times
        sent_email = None
        for m in messages_in_thread:
            headers = {h['name']: h['value'] for h in m['payload']['headers']}
            sender = headers.get('From', '')
            timestamp_ms = int(m.get('internalDate', 0))
            sent_at = timezone.make_aware(
                datetime.fromtimestamp(timestamp_ms / 1000), timezone=timezone.get_current_timezone()
            )

            if sender == request.user.email:
                sent_email = sent_at  
            elif sent_email:
                response_time = sent_at - sent_email
                response_times.append(response_time.total_seconds() / 60)
                break

    return JsonResponse({'response_times': response_times})
def get_time_slot_count(request):
    """Get the count of emails in each predefined time slot."""
    service, error = get_gmail_service(request)
    if error:
        return error

    messages = list_gmail_messages(service)
    time_slot_counts = {slot: 0 for slot, _, _ in TIME_SLOTS}

    for message in messages:
        msg_details = service.users().messages().get(userId='me', id=message['id']).execute()
        thread_id = msg_details.get('threadId')
        messages_in_thread = get_thread_messages(service, thread_id)

        sent_email = None

        for msg in messages_in_thread:
            headers = {h['name']: h['value'] for h in msg['payload']['headers']}
            sender = extract_email_address(headers.get('From', ''))
            timestamp_ms = int(msg.get('internalDate', 0))
            
            sent_at = timezone.make_aware(
                datetime.fromtimestamp(timestamp_ms / 1000), 
                timezone=timezone.get_current_timezone()
            )

            print(f"Sender: {sender}, Sent at: {sent_at}")
            logger.info(f"Sender: {sender}, Sent at: {sent_at}")
            if sender.lower() == request.user.email.strip().lower():
                sent_email = sent_at

            elif sent_email and sender.lower() != request.user.email.strip().lower():
                time_slot = classify_email_by_time_slot(sent_at)
                if time_slot in time_slot_counts:
                    time_slot_counts[time_slot] += 1
                break

    return JsonResponse(time_slot_counts)
def search_keywords(request):
    """Search for keywords in the email body."""
    q = request.GET.get('q')
    if q:
        emails = EmailMetadata.objects.filter(keywords__icontains=q)
        return JsonResponse(list(emails.values()), safe=False)
    else:
        return JsonResponse([])