import requests

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