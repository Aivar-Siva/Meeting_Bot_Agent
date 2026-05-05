import os, requests

class AttendeeClient:
    def __init__(self):
        self.base = os.environ["ATTENDEE_BASE_URL"]
        self.headers = {"Authorization": f"Token {os.environ['ATTENDEE_API_KEY']}"}

    def create_bot(self, meeting_url: str, bot_name: str) -> dict:
        r = requests.post(f"{self.base}/api/v1/bots",
                          json={
                              "meeting_url": meeting_url,
                              "bot_name": bot_name,
                              "transcription_settings": {
                                  "deepgram": {
                                      "language": "multi"
                                  }
                              }
                          },
                          headers=self.headers)
        r.raise_for_status()
        return r.json()

    def get_bot(self, bot_id: str) -> dict:
        r = requests.get(f"{self.base}/api/v1/bots/{bot_id}", headers=self.headers)
        r.raise_for_status()
        return r.json()

    def get_transcript(self, bot_id: str) -> list:
        r = requests.get(f"{self.base}/api/v1/bots/{bot_id}/transcript", headers=self.headers)
        r.raise_for_status()
        return r.json()
