from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from django.shortcuts import redirect
from django.contrib.auth.models import User
import os
import requests
from urllib.parse import quote
from decouple import config
from .email_utils import get_google_user_info
import logging

logger = logging.getLogger(__name__)

ENVIRONMENT = config('ENVIRONMENT')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'secrets/client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

if ENVIRONMENT == 'production':
    REDIRECT_URI = "https://email-analytics-surl.onrender.com/oauth2callback"
    # REDIRECT_URI = "http://localhost:5173"
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
    logger.info(f"authorized url : {authorize_url},, with state : {state}")
    request.session['state'] = state
    return redirect(authorize_url)

def oauth2callback(request):
    state = request.session.get('state')  # Safely get state from session
    logger.info(f"incoming state : {state}")
    if not state:
        logger.warning('State not found in session. Redirecting to authorization.')
        return redirect('http://localhost:5177/')
    
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
    user_info = get_google_user_info(credentials)

    email = user_info.get('email')
    name = user_info.get('name')

    user, created = User.objects.get_or_create(username=email, defaults={'email': email, 'first_name': name})

    # frontend_url = 'http://localhost:5173'
    # if frontend_available(frontend_url):
    return redirect(f'http://localhost:5173/?auth_token={quote(credentials.token)}')
    # else:
    # return redirect('gmail_data')

