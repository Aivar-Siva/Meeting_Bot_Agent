# Learnings — Attendee Setup & Troubleshooting

A record of every bug hit and how it was resolved during setup of the Meeting Bot Agent stack.

---

## 1. No Pre-Built Docker Image for Attendee

**Problem:** `docker-compose up` failed with `denied` — tried to pull `ghcr.io/attendee-labs/attendee:latest` which doesn't exist publicly.

**Fix:** Attendee must be built from source. Clone the repo as a subfolder and use `build: ./attendee` in docker-compose.

```yaml
attendee-app:
  build: ./attendee   # not image: ghcr.io/...
```

---

## 2. Attendee Needs Redis (Not Just Postgres)

**Problem:** Attendee worker crashed silently — Celery task queue requires Redis.

**Fix:** Add Redis to docker-compose and pass `REDIS_URL` to all Attendee services.

```yaml
redis:
  image: redis:7-alpine

environment:
  - REDIS_URL=redis://redis:6379/5
```

---

## 3. Attendee Dev Settings Hardcode DB Credentials

**Problem:** Passing `POSTGRES_HOST`, `POSTGRES_DB`, `POSTGRES_USER` env vars was ignored. Attendee's `development.py` hardcodes `attendee_development_user` / `attendee_development`.

**Fix:** Give Attendee its own local Postgres container with matching hardcoded credentials instead of fighting the settings file.

```yaml
attendee-postgres:
  image: postgres:15.3-alpine
  environment:
    POSTGRES_DB: attendee_development
    POSTGRES_USER: attendee_development_user
    POSTGRES_PASSWORD: attendee_development_user
```

---

## 4. SECRET_KEY and ALLOWED_HOSTS Not Set

**Problem:** Every request to Attendee returned `500 — The SECRET_KEY setting must not be empty` and `DisallowedHost`.

**Root cause:** The env var name is `DJANGO_SECRET_KEY` (not `SECRET_KEY`), and `ALLOWED_HOSTS` must be a comma-separated string.

**Fix:**
```yaml
environment:
  - DJANGO_SECRET_KEY=${ATTENDEE_SECRET_KEY}
  - ALLOWED_HOSTS=localhost,attendee-app,${EC2_PUBLIC_IP}
```

---

## 5. `docker-compose restart` Does Not Pick Up Env Changes

**Problem:** After updating docker-compose env vars, `restart` had no effect — containers kept old env.

**Fix:** Use `docker-compose up -d --no-build <service>` to recreate containers with new env. `restart` only restarts the process, not the container config.

---

## 6. Credentials Lost on Every Container Restart

**Problem:** Deepgram and Zoom credentials saved via Attendee UI or Django shell were wiped every time `attendee-app` restarted (stored in local Postgres volume, but container recreation resets the volume mount path).

**Fix:** Created `init_credentials.py` script and run it via `docker cp` + `docker-compose exec` after every restart:

```bash
docker cp attendee/init_credentials.py attendee-app:/attendee/init_credentials.py
docker-compose exec attendee-app python init_credentials.py
```

---

## 7. Credentials Use Fernet Encryption

**Problem:** Saving credentials directly to `_encrypted_data` field failed — it's a binary encrypted field.

**Fix:** Must use the model's `set_credentials()` method, which requires `CREDENTIALS_ENCRYPTION_KEY` env var (a valid Fernet key).

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add output to .env as CREDENTIALS_ENCRYPTION_KEY
```

---

## 8. Attendee API Key Hash Mismatch

**Problem:** API key copied from Attendee UI returned `401 Invalid or disabled API key`.

**Root cause:** Attendee hashes the key with SHA256 and stores the hash. The UI shows the raw key only once at creation. Copying it later from the settings page shows a truncated display ID, not the actual key.

**Fix:** Copy the key immediately when shown after creation. Verify with:
```bash
python3 -c "import hashlib; print(hashlib.sha256('YOUR_KEY'.encode()).hexdigest())"
# Must match key_hash in DB
```

---

## 9. Google Meet Bot Login Fails for @gmail.com Accounts

**Problem:** Bot navigated to `accounts.google.com` but never logged in — browser history showed `['', 'accounts.google.com']` and bot exited.

**Root cause:** Attendee's Google Meet login flow is designed for **Google Workspace (GSuite)** accounts, not personal `@gmail.com`. The default flow uses `mail.google.com/a/{domain}` which only works for org domains.

**Fix:** Switch to Zoom — uses SDK-based joining, no browser login required.

---

## 10. Deepgram Callback Does Not Work for Streaming

**Problem:** Configured `transcription_settings.deepgram.callback` URL but FastAPI never received any POST requests during the meeting.

**Root cause:** The Deepgram `callback` setting is for **pre-recorded/batch** transcription, not streaming. For streaming, Deepgram sends results directly back over the WebSocket connection that Attendee opens — there is no HTTP callback.

**Fix:** Poll Attendee's `GET /api/v1/bots/{id}/transcript` endpoint every 2 seconds during the meeting and push new utterances to WebSocket clients via the `transcript_poller.py` background task.

---

## 11. EC2 t3.micro OOM Crash

**Problem:** EC2 became unresponsive after starting all containers. SSH timed out.

**Root cause:** t3.micro has 1 GB RAM. Attendee (Chrome + Celery + Django) + FastAPI + Qdrant + Redis + Postgres exceeded available memory.

**Fix:** Upgrade to t3.small (2 GB RAM, still within AWS free tier 12-month limit).

```bash
aws ec2 stop-instances --instance-ids i-xxx
aws ec2 modify-instance-attribute --instance-id i-xxx --instance-type '{"Value":"t3.small"}'
aws ec2 start-instances --instance-ids i-xxx
```

---

## 12. Three Attendee Services Building the Same Image

**Problem:** `attendee-app`, `attendee-worker`, `attendee-webpage-streamer` all had `build: ./attendee` — Docker built the 5.9 GB image three times, filling the 20 GB disk.

**Fix:** Build once with `attendee-app`, reuse with `image:` tag for the others:
```yaml
attendee-worker:
  build: ./attendee
  image: meeting_bot_agent-attendee-app   # tag the built image
attendee-webpage-streamer:
  build: ./attendee
  image: meeting_bot_agent-attendee-app   # reuse same image
```

---

## 13. `docker compose` vs `docker-compose`

**Problem:** `docker compose up -d --build` failed with `unknown shorthand flag: 'd'`.

**Root cause:** Ubuntu's apt-installed Docker does not include the Compose v2 plugin. Only the legacy `docker-compose` binary was available.

**Fix:**
```bash
sudo apt-get install -y docker-compose
docker-compose up --build -d   # legacy syntax
```
