from django.shortcuts import render, redirect
from utils.google_authorize import Credentials
from googleapiclient.discovery import build
import datetime
# Create your views here.


def gmail_data(request):
    creds_data = request.session.get('credentials')
    if not creds_data:
        return redirect('authorize')

    creds = Credentials(
        token=creds_data['token'],
        refresh_token=creds_data['refresh_token'],
        token_uri=creds_data['token_uri'],
        client_id=creds_data['client_id'],
        client_secret=creds_data['client_secret'],
        scopes=creds_data['scopes']
    )

    # Refresh token if expired
    if creds.expired and creds.refresh_token:
        creds.refresh()

        # Update session with new token
        request.session['credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }

    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(userId='me').execute()
    messages = results.get('messages', [])

    return render(request, 'gmail_data.html', {'messages': messages})