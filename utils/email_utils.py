import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.http import JsonResponse
import re

def get_headers_value(headers, header_name):
    """Utility function to get a specific header from a list of headers."""

    for header in headers:
        if header['name'].lower() == header_name.lower():
            return header['value']
    return None

def get_google_user_info(credentials):
    """Fetch user profile info from Google API."""
    user_info_endpoint = 'https://www.googleapis.com/oauth2/v1/userinfo'
    response = requests.get(
        user_info_endpoint,
        headers={'Authorization': f'Bearer {credentials.token}'}
    )
    return response.json()

def get_email_body(msg):
    """Extract the full email body from the message payload."""
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            if part['mimeType'] == 'text/plain':
                return part['body']['data']
            elif part['mimeType'] == 'text/html':
                return part['body']['data']
    else:
        return msg['payload']['body']['data']
    
    return ''    

def get_gmail_service(request):
    """Initialize and return the Gmail service."""
    creds_data = request.session.get('credentials')
    if not creds_data:
        return None, JsonResponse({'error': 'Unauthorized'}, status=401)

    creds = Credentials(**creds_data)
    service = build('gmail', 'v1', credentials=creds)
    return service, None

def list_gmail_messages(service):
    """Fetch a list of messages from the Gmail account."""
    results = service.users().messages().list(userId='me').execute()
    return results.get('messages', [])

def get_thread_messages(service, thread_id):
    """Fetch all messages within a specific thread."""
    thread = service.users().threads().get(userId='me', id=thread_id).execute()
    return thread.get('messages', [])

def extract_email_address(raw_sender):
    """Extract email address from 'From' header."""
    match = re.search(r'<(.*?)>', raw_sender)
    return match.group(1) if match else raw_sender.strip()

def list_sent_gmail_messages(service):
    """List sent messages from Gmail."""
    results = service.users().messages().list(userId='me', q='in:sent').execute()
    messages = results.get('messages', [])
    sent_messages = []

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        sent_messages.append({
            'subject': get_headers_value(msg['payload']['headers'], 'Subject'),
            'internalDate': msg['internalDate'],
            'message_id': msg['id'],
        })

    return sent_messages

def list_received_gmail_messages(service, sent_subject, sent_at):
    """List received messages related to the sent email."""
    results = service.users().messages().list(userId='me', q=f'to:me subject:({sent_subject}) after:{sent_at.timestamp()}').execute()
    messages = results.get('messages', [])
    received_messages = []

    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        received_messages.append({
            'subject': get_headers_value(msg['payload']['headers'], 'Subject'),
            'internalDate': msg['internalDate'],
            'in_reply_to': get_headers_value(msg['payload']['headers'], 'In-Reply-To'),
            'message_id': msg['id'],
        })

    return received_messages

def batch_fetch_threads(service, thread_ids):
    """Batch fetch threads using the Gmail API."""
    threads = []
    for thread_id in thread_ids:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        threads.append(thread)
    return threads
