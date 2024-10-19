from rest_framework import serializers
from .models import EmailMetadata
class GmailMessageSerializer(serializers.Serializer):
    id = serializers.CharField()
    snippet = serializers.CharField()
    subject = serializers.CharField()
    sender = serializers.CharField()



class EmailMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMetadata
        fields = [
            'id', 'sender', 'recipient', 'subject', 'persons', 
            'organizations', 'job_titles', 'dates', 'sent_at', 'responded'
        ]