#!/bin/bash
set -e

# Start Django in background, init credentials after it's ready, then wait
python manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!

# Wait for Django to be ready
sleep 8

# Auto-restore credentials
python manage.py shell -c "
from bots.models import Credentials, Project
import os
p = Project.objects.first()
if p:
    c, _ = Credentials.objects.get_or_create(project=p, credential_type=1)
    c.set_credentials({'api_key': os.environ['DEEPGRAM_API_KEY']})
    c2, _ = Credentials.objects.get_or_create(project=p, credential_type=2)
    c2.set_credentials({'client_id': os.environ['ZOOM_CLIENT_ID'], 'client_secret': os.environ['ZOOM_CLIENT_SECRET']})
    print('Credentials auto-restored on startup')
else:
    print('No project found - credentials not restored')
" 2>&1 || true

# Keep Django running
wait $DJANGO_PID
