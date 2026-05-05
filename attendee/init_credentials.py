#!/usr/bin/env python3
"""Run this once after attendee-app starts to restore credentials."""
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendee.settings.development")
django.setup()

from bots.models import Credentials, Project

project = Project.objects.first()
if not project:
    print("No project found")
    exit(1)

# Deepgram
cred, _ = Credentials.objects.get_or_create(project=project, credential_type=1)
cred.set_credentials({"api_key": os.environ["DEEPGRAM_API_KEY"]})
print("Deepgram credentials saved")

# Zoom
zoom_client_id = os.environ.get("ZOOM_CLIENT_ID")
zoom_client_secret = os.environ.get("ZOOM_CLIENT_SECRET")
if zoom_client_id and zoom_client_secret:
    cred2, _ = Credentials.objects.get_or_create(project=project, credential_type=2)
    cred2.set_credentials({"client_id": zoom_client_id, "client_secret": zoom_client_secret})
    print("Zoom credentials saved")
