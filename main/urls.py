from django.urls import path
from .views import fetch_and_store_emails, EmailMetadataListView, google_login

urlpatterns = [
    path('fetch-and-store-emails/', fetch_and_store_emails, name='fetch_and_store_emails'),
    path('email-metadata/', EmailMetadataListView.as_view(), name='email-metadata'),
    path('google-login/', google_login, name='google-login'),
]