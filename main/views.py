from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework.views import APIView
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

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
