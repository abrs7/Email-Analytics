from django.db import models
from django.contrib.auth.models import User

class EmailMetadata(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sender = models.EmailField()
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    email_body = models.TextField()
    persons = models.JSONField()
    organizations = models.JSONField() 
    job_titles = models.JSONField(blank=True, null=True)
    dates = models.JSONField(blank=True, null=True)
    sent_at = models.DateTimeField()
    responded = models.BooleanField(default=False)
    email_length = models.IntegerField()
    bullet_points = models.JSONField()
    keywords = models.JSONField()

    def __str__(self):
        return f"{self.subject} - {self.sender}"
