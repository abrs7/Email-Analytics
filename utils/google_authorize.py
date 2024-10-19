from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from django.shortcuts import redirect
import os
import requests
from decouple import config

ENVIRONMENT = config('ENVIRONMENT')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'secrets/client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

if ENVIRONMENT == 'production':
    REDIRECT_URI = "https://email-analytics-surl.onrender.com/oauth2callback"
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
else:
    REDIRECT_URI = "http://localhost:8000/oauth2callback"

def get_flow():
    """Create OAuth2 Flow based on the environment."""
    if ENVIRONMENT == 'production':
        # Use environment variables in production
        flow = Flow.from_client_config(
            {
                "installed": {
                    "client_id": config('GOOGLE_CLIENT_ID'),
                    "client_secret": config('GOOGLE_CLIENT_SECRET'),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
    else:
        # Use the local JSON file in development
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
    return flow

def authorize(request):
    # Ensure the redirect_uri is passed correctly inside the constructor
    flow = get_flow()
    authorize_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    request.session['state'] = state
    return redirect(authorize_url)

def frontend_available(url):
    """Ping the frontend URL to check if it's available."""
    try:
        response = requests.head(url, timeout=3)
        return response.status_code == 200
    except requests.RequestException:
        return False    

def oauth2callback(request):
    state = request.session.get('state')  # Safely get state from session
    if not state:
        return redirect('authorize')
    
    flow = get_flow()
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
    frontend_url = 'http://localhost:5173'
    if frontend_available(frontend_url):
        return redirect(frontend_url)
    else:
        return redirect('gmail_data')
