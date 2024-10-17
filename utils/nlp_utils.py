import spacy

# Load spaCy's pre-trained English model
nlp = spacy.load('en_core_web_sm')

def extract_email_entities(email_body):
    """Extract relevant information from email content."""
    doc = nlp(email_body)

    entities = {
        "persons": [],
        "organizations": [],
        "job_titles": [],
        "dates": [],
        "emails": []
    }

    # Extract named entities from the email
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            entities["persons"].append(ent.text)
        elif ent.label_ == "ORG":
            entities["organizations"].append(ent.text)
        elif ent.label_ in ("DATE", "TIME"):
            entities["dates"].append(ent.text)

    # Use regex to extract emails from the text
    entities["emails"] = list(set([token.text for token in doc if token.like_email]))

    return entities
