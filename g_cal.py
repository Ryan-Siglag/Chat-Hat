import datetime
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def get_upcoming_events(n=3):
    try:
        service = build("calendar", "v3", credentials=get_credentials())
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=n,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = result.get("items", [])

        if not events:
            return []

        output = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "(No title)")
            location = event.get("location", "")

            if "T" in start:
                dt = datetime.datetime.fromisoformat(start)
                start_fmt = dt.strftime("%A, %b %d at %I:%M %p")
            else:
                start_fmt = start

            entry = f"{summary} on {start_fmt}"
            if location:
                entry += f" @ {location}"

            output.append(entry)

        return output

    except HttpError as e:
        print(f"API error: {e}")
        return []

if __name__ == "__main__":
    events = get_upcoming_events(3)
    print(events)