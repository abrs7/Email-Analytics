import spacy

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



def extract_keywords(email_body):
    """Extract keywords from email content."""
    doc = nlp(email_body)
    keywords = [token.text for token in doc if not token.is_stop]
    return keywords

def find_bullet_poits(text):
    """Find bullet points in text."""
    lines = text.splitlines()
    bullet_points = [line.strip() for line in lines if line.strip().startswith(('-', '*', '•'))]
    return bullet_points
    