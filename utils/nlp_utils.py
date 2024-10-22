import spacy
import base64
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
    doc = nlp(text)
    keywords = [
        token.text for token in doc 
        if not token.is_stop and not token.is_punct and len(token.text) > 2
    ]
    return keywords

def find_bullet_points(text):
    """Find bullet points in text."""
    lines = text.splitlines()
    bullet_points = [line.strip() for line in lines if line.strip().startswith(('-', '*', '•'))]
    return bullet_points

def decode_email_body(encoded_body):
    """Decode the Base64 email body content."""
    decoded_bytes = base64.urlsafe_b64decode(encoded_body.encode('UTF-8'))
    return decoded_bytes.decode('UTF-8', errors='ignore')    