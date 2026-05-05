#!/bin/bash
set -e

# Auto-restore credentials from env vars on every start
python manage.py shell -c "
import time; time.sleep(2)
from bots.models import Credentials, Project
import os
p = Project.objects.first()
if p:
    c, _ = Credentials.objects.get_or_create(project=p, credential_type=1)
    c.set_credentials({'api_key': os.environ['DEEPGRAM_API_KEY']})
    c2, _ = Credentials.objects.get_or_create(project=p, credential_type=2)
    c2.set_credentials({'client_id': os.environ['ZOOM_CLIENT_ID'], 'client_secret': os.environ['ZOOM_CLIENT_SECRET']})
    print('Credentials auto-restored')
" 2>/dev/null || echo "Credential init skipped (no project yet)"

exec python manage.py runserver 0.0.0.0:8000
