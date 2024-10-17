from django.db import models

class EmailMetadata(models.Model):
    sender = models.EmailField()
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    persons = models.JSONField()
    organizations = models.JSONField() 
    job_titles = models.JSONField(blank=True, null=True)
    dates = models.JSONField(blank=True, null=True)
    sent_at = models.DateTimeField()
    responded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.subject} - {self.sender}"
