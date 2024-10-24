from datetime import datetime
from django.utils import timezone
from django.shortcuts import redirect, render
from urllib.parse import urlencode
from django.db.models import Q, Count, Avg
from collections import Counter
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import ListAPIView
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from utils.nlp_utils import extract_email_entities, extract_keywords, decode_email_body, find_bullet_points, extract_email_body
from django.http import JsonResponse, HttpResponseRedirect
from decouple import config
from utils.email_utils import get_headers_value, get_email_body, get_gmail_service, get_thread_messages, list_gmail_messages, extract_email_address, list_sent_gmail_messages, list_received_gmail_messages
from utils.func_utils import TIME_SLOTS, classify_email_by_time_slot
from .models import EmailMetadata
from .serializers import GmailMessageSerializer, EmailMetadataSerializer
from collections import defaultdict
import math
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

EMAIL_CACHE_TIMEOUT = 86400  # 24 hours

def fetch_and_store_emails(request):
    """Fetch emails, analyze with spaCy, and store metadata in the database."""
    print(f"user: {request.user}")
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
    logger.info(f"Fetching {len(messages)} emails...")
    for message in messages:
        email_id = message['id']

        if cache.get(f"email_{email_id}"):
            continue

        msg = service.users().messages().get(userId='me', id=message['id']).execute()

        email_body = extract_email_body(msg)
        logger.info(f"Extracted email body: {email_body}")
        logger.info(f"Processing email with ID: {email_id}")
        logger.info(f"Email body: {email_body}")
        email_length = len(email_body.split())
        bullet_points = find_bullet_points (email_body)
        keywords = extract_keywords(email_body)
        metadata = extract_email_entities(email_body)

        timestamp_ms = int(msg.get('internalDate', 0))
        sent_at_naive = datetime.fromtimestamp(timestamp_ms / 1000)
        sent_at = timezone.make_aware(sent_at_naive, timezone=timezone.get_current_timezone())

        sender = get_headers_value(msg['payload']['headers'], 'From') or 'Unknown Sender'
        recipient = get_headers_value(msg['payload']['headers'], 'To') or 'Unknown Recipient'
        subject = get_headers_value(msg['payload']['headers'], 'Subject') or 'No Subject'

        try:
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
                responded=False,
                email_length=email_length,
                bullet_points=bullet_points,
                keywords=keywords,
                user=request.user
            )
            print(f"Email {email_id} saved successfully.")
        except Exception as e:
            print(f"Failed to save email {email_id}: {str(e)}")
        cache.set(f"email_{email_id}", True, timeout=EMAIL_CACHE_TIMEOUT)

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

TIME_SLOT_CACHE_TIMEOUT = 86400  # Cache timeout of 1 day

def get_time_slot_count(request):
    """Retrieve and cache the count of emails in each predefined time slot."""
    # Retrieve cached counts if they exist
    cache_key = "time_slot_counts"
    cached_counts = cache.get(cache_key)

    if cached_counts:
        logger.info("Serving time slot counts from cache...")
        return JsonResponse(cached_counts)

    # If not cached, proceed to recompute counts
    service, error = get_gmail_service(request)
    if error:
        return error

    messages = list_gmail_messages(service)
    time_slot_counts = {slot: 0 for slot, _, _ in TIME_SLOTS}

    for message in messages:
        thread_id = message.get('threadId')

        # Fetch messages in thread (avoid reprocessing cached threads)
        thread_cache_key = f"thread_{thread_id}"
        if cache.get(thread_cache_key):
            logger.info(f"Skipping cached thread {thread_id}")
            continue  # Skip threads that were processed before

        messages_in_thread = get_thread_messages(service, thread_id)

        for msg in messages_in_thread:
            headers = {h['name']: h['value'] for h in msg['payload']['headers']}
            sender = extract_email_address(headers.get('From', ''))
            timestamp_ms = int(msg.get('internalDate', 0))

            sent_at = timezone.make_aware(
                datetime.fromtimestamp(timestamp_ms / 1000),
                timezone=timezone.get_current_timezone()
            )

            logger.info(f"Sender: {sender}, Sent at: {sent_at}")

            # Classify email into a time slot
            time_slot = classify_email_by_time_slot(sent_at)
            logger.info(f"Time slot: {time_slot}")

            if time_slot in time_slot_counts:
                time_slot_counts[time_slot] += 1
                logger.info(f"Updated count for {time_slot}: {time_slot_counts[time_slot]}")

        # Cache the processed thread to prevent reprocessing
        cache.set(thread_cache_key, True, timeout=TIME_SLOT_CACHE_TIMEOUT)
    # Cache the final time slot counts
    cache.set(cache_key, time_slot_counts, timeout=TIME_SLOT_CACHE_TIMEOUT)

    logger.info(f"Final time slot counts: {time_slot_counts}")
    return JsonResponse(time_slot_counts)

def search_keywords(request):
    """Search for keywords in the email body."""
    q = request.GET.get('q')
    
    sanitized_query = q.replace(":", "_").replace(",", "_") if q else ""
    cache_key = f"search_{sanitized_query}"

    cached_result = cache.get(cache_key)
    if cached_result:
        logger.info("Serving from cache...")
        return JsonResponse(cached_result, safe=False)

    result = []

    if q:
        if request.user.is_authenticated:
            emails = EmailMetadata.objects.filter(user=request.user, keywords__icontains=q)
            result = list(emails.values())
            cache.set(cache_key, result, timeout=60000)
            return JsonResponse(result, safe=False)
        else:
            return JsonResponse({'error': 'User not authenticated'}, status=403)
    else:
        return JsonResponse([], safe=False)
    
def search_multiple_keywords(request):
    """
    Search for multiple keywords in the email body and return the frequency 
    of emails containing each keyword. Uses Redis caching to store results.
    """
    query = request.GET.get('q')

    if not query:
        return JsonResponse({"error": "No keywords provided"}, status=400)

    cache_key = f"search_{'_'.join(query.split(',')).strip()}"

    cached_result = cache.get(cache_key)
    if cached_result:
        return JsonResponse(cached_result)

    keywords = [kw.strip() for kw in query.split(",") if kw.strip()]
    keyword_counts = defaultdict(int)

    for keyword in keywords:
        count = EmailMetadata.objects.filter(
            Q(subject__icontains=keyword) | Q(body__icontains=keyword)
        ).count()
        keyword_counts[keyword] = count

    # Store the result in the cache for 10 minutes
    cache.set(cache_key, keyword_counts, timeout=60000)

    return JsonResponse(keyword_counts)

def get_email_responses(request):
    """Retrieve and cache the responses to sent emails and classify them, including response date."""
    cache_key = "email_responses"
    cached_responses = cache.get(cache_key)
    response_times = []
    if cached_responses:
        logger.info("Serving email responses from cache...")
        return JsonResponse(cached_responses, safe=False)

    service, error = get_gmail_service(request)
    if error:
        return error

    sent_messages = list_sent_gmail_messages(service)
    
    email_responses = []

    for sent in sent_messages:
        sent_subject = sent['subject']
        sent_timestamp_ms = int(sent.get('internalDate', 0))
        
        sent_at = timezone.make_aware(
            datetime.fromtimestamp(sent_timestamp_ms / 1000),
            timezone=timezone.get_current_timezone()
        )

        print(f"Sent email subject: {sent_subject}, Sent at: {sent_at}")

        # Check for responses to the sent email
        received_messages = list_received_gmail_messages(service, sent_subject, sent_at)

        for received in received_messages:
            received_subject = received['subject']
            received_timestamp_ms = int(received.get('internalDate', 0))
            received_at = timezone.make_aware(
                datetime.fromtimestamp(received_timestamp_ms / 1000),
                timezone=timezone.get_current_timezone()
            )

            print(f"Received email subject: {received_subject}, Received at: {received_at}")

            # Determine if the received email is a direct response or a thread continuation
            if received.get('in_reply_to') == sent['message_id']:
                response_type = 'direct_response'
            elif sent_subject in received_subject:
                response_type = 'thread_response'
            else:
                response_type = 'normal_response'  

            # Calculate response date
            response_date = received_at.date()
            response_time = (received_at - sent_at).total_seconds() / (60 * 60 )

            response_times.append(response_time)

            email_responses.append({
                'sent_email': sent,
                'received_email': received,
                'response_type': response_type,
                'response_date': response_date,  
                'response_time': response_time 
            })

    average_response_time = sum(response_times) / len(response_times) if response_times else 0 
    average_response_time_in_hours = math.ceil(average_response_time / 60 )
    result = {
        'average_response_time': average_response_time_in_hours,
        'email_responses': email_responses
    }
    cache.set(cache_key, result, timeout=TIME_SLOT_CACHE_TIMEOUT)

    print(f"Final result of email responses: {result}")
    return JsonResponse(result, safe=False)

def get_email_statistics(request):
    """Retrieve average response time, top used keywords, average email length, and percentage of non-responded emails."""
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=403)

    user_emails = EmailMetadata.objects.filter(user=request.user)

    average_email_length = user_emails.aggregate(Avg('email_length'))['email_length__avg'] or 0

    responded_emails = None
    average_response_time = 0

    all_keywords = []
    for email in user_emails:
        if isinstance(email.keywords, list):  # Check if keywords is a list
            all_keywords.extend(email.keywords)  # Directly extend the list
        elif isinstance(email.keywords, str):  # If it's a string, split it
            all_keywords.extend(email.keywords.split(','))  # Assuming keywords are stored as a comma-separated string

    top_keywords = Counter(all_keywords).most_common(10)


    total_sent_emails = user_emails.count()
    non_responded_count = user_emails.filter(responded=False).count()
    non_responded_percentage = (non_responded_count / total_sent_emails) * 100 if total_sent_emails > 0 else 0

    statistics = {
        'average_email_length': average_email_length,
        'average_response_time': average_response_time,
        'top_keywords': top_keywords,
        'non_responded_percentage': non_responded_percentage
    }

    return JsonResponse(statistics, status=200)