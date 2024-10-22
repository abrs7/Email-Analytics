import spacy
import base64
import quopri
from bs4 import BeautifulSoup
# Load spaCy's pre-trained English model
nlp = spacy.load('en_core_web_sm')

def extract_email_entities(text):
    """Extract relevant information from email content."""
    doc = nlp(text)
    persons = [ent.text for ent in doc.ents if ent.label_ == 'PERSON']
    organizations = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
    job_titles = [ent.text for ent in doc.ents if ent.label_ == 'TITLE']
    dates = [ent.text for ent in doc.ents if ent.label_ == 'DATE']
    return {"persons": persons, "organizations": organizations, "job_titles": job_titles, "dates": dates}

def extract_keywords(text):
    """Extract meaningful keywords from email text."""
    clean_text = BeautifulSoup(text, 'html.parser').get_text(strip=True)
    unwanted_keywords = {"\n", "read", "   ", " ", "", "\r\n\r\n"}
    doc = nlp(clean_text)
    keywords = [
        token.text for token in doc 
        if not token.is_stop and not token.is_punct and len(token.text) > 2 and token.text not in unwanted_keywords
    ]
    return keywords

def find_bullet_points(text):
    """Find bullet points in text."""
    lines = text.splitlines()
    bullet_points = [line.strip() for line in lines if line.strip().startswith(('-', '*', '•'))]
    return bullet_points

def decode_email_body(encoded_body):
    """Decode the email body from base64."""
    try:
        decoded_bytes = base64.urlsafe_b64decode(encoded_body)
        return decoded_bytes.decode('utf-8')
    except (base64.binascii.Error, UnicodeDecodeError):
        return quopri.decodestring(encoded_body).decode('utf-8', errors='ignore')

def extract_email_body(msg):
    """Extracts the email body from the payload."""
    parts = msg.get('payload', {}).get('parts', [])
    for part in parts:
        mime_type = part.get('mimeType')
        if mime_type == 'text/plain':
            encoded_body = part.get('body', {}).get('data', '')
            return decode_email_body(encoded_body)
        elif mime_type == 'text/html':
            encoded_body = part.get('body', {}).get('data', '')
            return decode_email_body(encoded_body)

    # Fallback to 'body' if no parts are found
    encoded_body = msg.get('payload', {}).get('body', {}).get('data', '')
    return decode_email_body(encoded_body) if encoded_body else "No Content"