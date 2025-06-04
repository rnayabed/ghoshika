import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build # Not strictly needed for auth, but good for testing scope
from googleapiclient.errors import HttpError

# --- Configuration ---
# These should match the SCOPES used by your main application (main2.py)
# Ensure main2.py uses the same SCOPES if it needs to perform actions beyond readonly.
# For main2.py as it is, gmail.readonly is sufficient if it only reads.
# However, if main2.py also marks emails as read, it needs gmail.modify.
# Let's use the more permissive scope here to ensure the token is versatile.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"] # Match main2.py's current scope
TOKEN_FILE = "google_token.json"
CREDENTIALS_FILE = "google_credentials.json"  # Your OAuth 2.0 client secrets file

def generate_token():
    """
    Runs the OAuth 2.0 flow to generate a token.json file.
    """
    creds = None
    # Check if token.json already exists and is valid
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"Warning: Could not load existing token file '{TOKEN_FILE}': {e}. Will attempt to generate a new one.")
            creds = None

    if creds and creds.valid:
        print(f"Token file '{TOKEN_FILE}' already exists and credentials are valid.")
        try:
            # Optional: Test the credentials by making a simple API call
            service = build("gmail", "v1", credentials=creds)
            service.users().labels().list(userId="me").execute()
            print("Credentials successfully tested with Gmail API.")
        except HttpError as error:
            print(f"Credentials in '{TOKEN_FILE}' are valid but failed API test: {error}")
            print("Consider regenerating the token if issues persist.")
        except Exception as e:
            print(f"An unexpected error occurred during credential test: {e}")
        
        user_choice = input(f"Do you want to regenerate '{TOKEN_FILE}' anyway? (yes/no): ").lower()
        if user_choice != 'yes':
            print("Exiting without regenerating token.")
            return
        else:
            print("Proceeding to regenerate token...")
            creds = None # Force regeneration

    # If there are no (valid) credentials available, or user chose to regenerate, let the user log in.
    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.")
            print("Please download your OAuth 2.0 client secrets file from the Google Cloud Console")
            print("and place it in the same directory as this script.")
            return

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        # The run_local_server will open a browser tab for authentication.
        # It must use localhost or 127.0.0.1 for "Desktop app" OAuth clients.
        try:
            print("Attempting to run local server for authentication on http://localhost:[port]")
            creds = flow.run_local_server(
                host='localhost', # Important: Use localhost for desktop app flow
                port=0 # Use a dynamically assigned port
            )
            print("Authentication successful.")
        except Exception as e:
            print(f"OAuth flow failed: {e}")
            print("Ensure you have a browser environment available or try running this on a machine with a GUI.")
            return

        # Save the credentials for the next run
        try:
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            print(f"Credentials saved to '{TOKEN_FILE}'.")
            print(f"You can now copy '{TOKEN_FILE}' (and '{CREDENTIALS_FILE}') to your server/Raspberry Pi.")
        except Exception as e:
            print(f"Failed to save credentials to '{TOKEN_FILE}': {e}")

if __name__ == "__main__":
    generate_token()
