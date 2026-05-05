#!/bin/bash
# Wait for DB to be ready
echo "Waiting for database..."
python manage.py wait_for_db 2>/dev/null || sleep 5

# Auto-restore credentials from env vars
if [ -n "$DEEPGRAM_API_KEY" ]; then
  python - <<'EOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "attendee.settings.development")
django.setup()
from bots.models import Credentials, Project
project = Project.objects.first()
if project:
    cred, _ = Credentials.objects.get_or_create(project=project, credential_type=1)
    cred.set_credentials({"api_key": os.environ["DEEPGRAM_API_KEY"]})
    print("Deepgram credentials auto-restored")
    zoom_id = os.environ.get("ZOOM_CLIENT_ID")
    zoom_secret = os.environ.get("ZOOM_CLIENT_SECRET")
    if zoom_id and zoom_secret:
        cred2, _ = Credentials.objects.get_or_create(project=project, credential_type=2)
        cred2.set_credentials({"client_id": zoom_id, "client_secret": zoom_secret})
        print("Zoom credentials auto-restored")
EOF
fi

exec "$@"
