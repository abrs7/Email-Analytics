from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from django.shortcuts import redirect
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'secrets/client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
REDIRECT_URI = "http://localhost:8000/oauth2callback"  # Matches Google Console URI

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def authorize(request):
    # Ensure the redirect_uri is passed correctly inside the constructor
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorize_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    request.session['state'] = state
    return redirect(authorize_url)

def oauth2callback(request):
    state = request.session.get('state')  # Safely get state from session
    if not state:
        return redirect('authorize')

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES, 
        state=state, 
        redirect_uri=REDIRECT_URI  # Ensure it's redirect_uri
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())

    credentials = flow.credentials
    request.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return redirect('gmail_data')
