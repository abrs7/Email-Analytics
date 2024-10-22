from datetime import datetime

TIME_SLOTS = [
    ('6am - 9am', 6, 9),
    ('9am - 12pm', 9, 12),
    ('12pm - 3pm', 12, 15),
    ('3pm - 6pm', 15, 18),
    ('6pm - 9pm', 18, 21),
    ('9pm - 12am', 21, 24),
    ('12am - 6am', 0, 6),
]

def classify_email_by_time_slot(timestamp):
    """Classify the email's timestamp into a predefined time slot."""
    hour = timestamp.hour
    print(f"Classifying email sent at hour: {hour}")

    for slot, start, end in TIME_SLOTS:
        if start <= hour < end:
            return slot
    return 'Unknown'
