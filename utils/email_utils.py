import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.http import JsonResponse

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
