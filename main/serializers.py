from rest_framework import serializers

class GmailMessageSerializer(serializers.Serializer):
    id = serializers.CharField()
    snippet = serializers.CharField()
    subject = serializers.CharField()
    sender = serializers.CharField()
