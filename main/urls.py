from django.urls import path
from .views import fetch_and_store_emails

urlpatterns = [
    path('fetch-and-store-emails/', fetch_and_store_emails, name='fetch_and_store_emails'),
]