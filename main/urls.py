from django.urls import path
from .views import fetch_and_store_emails, EmailMetadataListView, google_login, get_time_slot_count, search_keywords, search_multiple_keywords

urlpatterns = [
    path('fetch-and-store-emails/', fetch_and_store_emails, name='fetch_and_store_emails'),
    path('email-metadata/', EmailMetadataListView.as_view(), name='email-metadata'),
    path('google-login/', google_login, name='google-login'),
    path('get-response-time-slot/', get_time_slot_count, name='get_response_time_slot'),
    path('search-keywords/', search_keywords, name='search_keywords'),
    path('search-multiple-keywords/', search_multiple_keywords, name='search_multiple_keywords'),
]