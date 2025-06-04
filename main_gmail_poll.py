import os
import time
import re
import base64
# subprocess is no longer needed as get_local_ip is removed
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
# InstalledAppFlow is no longer needed here
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from gtts import gTTS
import playsound3 # For playing the audio

# Attempt to import RPi.GPIO and set up a flag
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    print("WARNING: RPi.GPIO library not found or not usable. LED functionality will be disabled.")

# If modifying these SCOPES, delete the file token.json.
# This MUST match the SCOPES used in auth_gen.py
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_FILE = "google_token.json"
CREDENTIALS_FILE = "google_credentials.json" # Still needed for client_id/client_secret if refresh token needs them
AUDIO_FILENAME = "temp_speech.mp3"
SAVE_CREDS_INTERVAL_SECONDS = 3600  # Save/Refresh credentials every 1 hour (was 10 seconds)

TARGET_SENDER = "transaction.alerts@idfcfirstbank.com"
TARGET_SUBJECT = "Transaction alert from IDFC FIRST Bank"
SEARCH_TEXT_PATTERN = r"has been credited with INR\s*([0-9,]+\.?[0-9]{0,2})\s+on\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})"

# --- GPIO Configuration ---
LED_GPIO_PIN = 17  # BCM Pin number for the LED

def setup_gpio():
    if not HAS_GPIO:
        return
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(LED_GPIO_PIN, GPIO.OUT)
        GPIO.output(LED_GPIO_PIN, GPIO.LOW)  # Start with LED OFF
        print(f"INFO: GPIO {LED_GPIO_PIN} setup for LED.")
    except Exception as e:
        print(f"ERROR: Failed to setup GPIO: {e}. LED functionality may be affected.")

def cleanup_gpio():
    if not HAS_GPIO:
        return
    try:
        print("INFO: Cleaning up GPIO...")
        GPIO.output(LED_GPIO_PIN, GPIO.LOW)  # Turn LED OFF
        GPIO.cleanup()
        print("INFO: GPIO cleanup complete.")
    except Exception as e:
        print(f"ERROR: Failed to cleanup GPIO: {e}")

def led_on():
    if not HAS_GPIO:
        return
    try:
        GPIO.output(LED_GPIO_PIN, GPIO.HIGH)
    except Exception as e:
        print(f"ERROR: Failed to turn LED ON: {e}")

def led_off():
    if not HAS_GPIO:
        return
    try:
        GPIO.output(LED_GPIO_PIN, GPIO.LOW)
    except Exception as e:
        print(f"ERROR: Failed to turn LED OFF: {e}")

def blink_led_sync(times=3, on_duration=0.15, off_duration=0.15):
    if not HAS_GPIO:
        return
    try:
        for _ in range(times):
            GPIO.output(LED_GPIO_PIN, GPIO.HIGH)
            time.sleep(on_duration)
            GPIO.output(LED_GPIO_PIN, GPIO.LOW)
            time.sleep(off_duration)
        GPIO.output(LED_GPIO_PIN, GPIO.HIGH)
    except Exception as e:
        print(f"ERROR: Failed to blink LED (sync): {e}")

# get_local_ip function is removed as it's no longer needed for OAuth flow here.

def speak_text(text_to_speak):
    try:
        print(f"Attempting to speak: \"{text_to_speak}\"")
        tts = gTTS(text=text_to_speak, lang='en', slow=False)
        tts.save(AUDIO_FILENAME)
        playsound3.playsound(AUDIO_FILENAME)
    except Exception as e:
        print(f"Error in text-to-speech or playback: {e}")
    finally:
        if os.path.exists(AUDIO_FILENAME):
            try:
                os.remove(AUDIO_FILENAME)
            except Exception as e:
                print(f"Error deleting temporary audio file {AUDIO_FILENAME}: {e}")

def save_credentials_to_file(credentials, filename):
    try:
        with open(filename, "w") as token_file:
            token_file.write(credentials.to_json())
        print(f"INFO: Credentials successfully saved to {filename}.")
    except Exception as e:
        print(f"ERROR: Failed to save credentials to {filename}: {e}")

def refresh_gmail_creds(creds):
    """Attempts to refresh credentials. Returns refreshed creds or None."""
    if not creds or not creds.refresh_token:
        print("ERROR: No refresh token found in credentials. Cannot refresh.")
        return None
    try:
        # The google.oauth2.credentials.Credentials object needs client_id and client_secret
        # for refreshing. These are typically loaded from the token.json if it was created
        # by google-auth, or from credentials.json if needed.
        # Ensure credentials.json is available if the refresh token alone isn't enough.
        # if not creds.client_id or not creds.client_secret:
        #     if os.path.exists(CREDENTIALS_FILE):
        #         # This is a bit of a workaround. Ideally, the token.json from auth_gen.py
        #         # should contain all necessary info. If not, we might need to load
        #         # client_id/secret from credentials.json.
        #         # However, `creds.refresh(Request())` should handle this if token.json is complete.
        #         print("INFO: client_id or client_secret missing in creds, refresh might rely on token file structure or fail.")
        #     else:
        #         print(f"WARNING: {CREDENTIALS_FILE} not found, which might be needed for refresh if token.json is incomplete.")

        creds.refresh(Request())
        print("INFO: Credentials refreshed successfully.")
        save_credentials_to_file(creds, TOKEN_FILE)
        return creds
    except Exception as e:
        print(f"ERROR: Failed to refresh credentials: {e}.")
        print("Please run auth_gen.py to re-authenticate and generate a new token.json.")
        return None


def get_gmail_service():
    """
    Loads credentials from token.json, refreshes if necessary, and builds the Gmail service.
    Assumes token.json is generated by auth_gen.py.
    """
    creds = None
    if not os.path.exists(TOKEN_FILE):
        print(f"ERROR: Token file '{TOKEN_FILE}' not found.")
        print(f"Please run auth_gen.py first to generate '{TOKEN_FILE}'.")
        return None, None

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    except Exception as e:
        print(f"ERROR: Could not load credentials from '{TOKEN_FILE}': {e}")
        print(f"Please ensure '{TOKEN_FILE}' is valid or run auth_gen.py to regenerate it.")
        return None, None
    
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("INFO: Credentials expired, attempting refresh...")
            creds = refresh_gmail_creds(creds)
            if not creds: # Refresh failed
                return None, None # Error message already printed by refresh_gmail_creds
        else:
            print(f"ERROR: Credentials in '{TOKEN_FILE}' are invalid and cannot be refreshed (e.g., no refresh token or not expired).")
            print(f"Please run auth_gen.py to generate a new '{TOKEN_FILE}'.")
            return None, None

    if not creds or not creds.valid: # Final check after potential refresh
        print("ERROR: Unable to obtain valid credentials after attempting load/refresh.")
        return None, None

    try:
        service = build("gmail", "v1", credentials=creds)
        print("INFO: Gmail service built successfully.")
        return service, creds
    except HttpError as error:
        print(f"An error occurred while building the Gmail service: {error}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred while building the Gmail service: {e}")
        return None, None

def get_email_body(message_payload):
    if "parts" in message_payload:
        for part in message_payload["parts"]:
            if part["mimeType"] == "text/plain":
                if "data" in part["body"]:
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
            elif "parts" in part:
                body = get_email_body(part)
                if body:
                    return body
    elif message_payload["mimeType"] == "text/plain":
        if "data" in message_payload["body"]:
            return base64.urlsafe_b64decode(message_payload["body"]["data"]).decode("utf-8")
    return None

def process_email(service, message_id):
    try:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload")
        if not payload:
            print(f"No payload in message ID {message_id}")
            return

        email_body_text = get_email_body(payload)
        if email_body_text:
            match = re.search(SEARCH_TEXT_PATTERN, email_body_text, re.IGNORECASE)
            if match:
                extracted_sum = match.group(1).replace(",", "").replace(".00", "")
                transaction_date = match.group(2)
                transaction_time = match.group(3)
                
                print_message = f"Transaction Alert: Credited amount = INR {match.group(1)} on {transaction_date} at {transaction_time}"
                print(print_message)

                speech_message = f"Rupees. {extracted_sum}. received."
                speak_text(speech_message)
                blink_led_sync()
            else:
                pass
        else:
            print(f"Could not extract plain text body from email ID {message_id}")
        mark_email_as_read(service, message_id)
    except HttpError as error:
        print(f"An error occurred while processing email ID {message_id}: {error}")
        if error.resp.status == 401: # Unauthorized
             print("ERROR: Gmail API returned 401 Unauthorized. Credentials may have been revoked.")
             # This might trigger re-authentication attempt in the main loop if creds become invalid.
    except Exception as e:
        print(f"An unexpected error occurred with email ID {message_id}: {e}")

def mark_email_as_read(service, message_id):
    try:
        service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()
    except HttpError as error:
        print(f"An error occurred while marking email ID {message_id} as read: {error}")

def check_new_emails(service):
    try:
        query = f"is:unread from:{TARGET_SENDER} subject:\"{TARGET_SUBJECT}\" in:inbox"
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query)
            .execute()
        )
        messages = response.get("messages", [])
        if not messages:
            pass
        else:
            print(f"Found {len(messages)} new transaction alert email(s).")
            for message_summary in messages:
                process_email(service, message_summary["id"])
    except HttpError as error:
        print(f"An error occurred while checking for new emails: {error}")
        if error.resp.status == 401:
            print("ERROR: Received 401 Unauthorized while checking emails. Credentials may be invalid or revoked.")
    except Exception as e:
        print(f"An unexpected error occurred while checking emails: {e}")

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: Credentials file '{CREDENTIALS_FILE}' not found.")
        print("Please download your OAuth 2.0 client secrets file from the Google Cloud Console.")
        return

    setup_gpio()

    service, creds = get_gmail_service()
    if not service or not creds:
        print("Failed to initialize Gmail service or obtain credentials. Exiting.")
        led_off()
        cleanup_gpio()
        return

    print("Starting email listener with voice alerts...")
    led_on()
    print(f"Looking for emails from: {TARGET_SENDER}")
    print(f"With subject: {TARGET_SUBJECT}")
    print(f"Searching for text pattern: \"{SEARCH_TEXT_PATTERN}\"")
    print("Press Ctrl+C to stop.")

    last_creds_save_time = time.time()

    try:
        while True:
            # Check if credentials are still valid before making API calls
            if not creds or not creds.valid:
                print("WARNING: Credentials became invalid. Attempting to refresh/re-acquire.")
                led_off()
                service, creds = get_gmail_service()
                if not service or not creds:
                    print("ERROR: Failed to re-initialize Gmail service after credentials became invalid. Stopping.")
                    break
                else:
                    print("INFO: Successfully re-initialized service and credentials.")
                    led_on()
                    last_creds_save_time = time.time() # Reset timer

            check_new_emails(service)
            
            current_time = time.time()
            if (current_time - last_creds_save_time) > SAVE_CREDS_INTERVAL_SECONDS:
                if creds and creds.valid and creds.refresh_token: # Only try to refresh if we have a refresh token
                    print(f"INFO: Scheduled time to refresh credentials. Next refresh in approx. {SAVE_CREDS_INTERVAL_SECONDS/3600.0:.2f} hour(s).")
                    refreshed_creds = refresh_gmail_creds(creds)
                    if refreshed_creds:
                        creds = refreshed_creds
                        try:
                            service = build("gmail", "v1", credentials=creds) # Rebuild service with new creds
                            print("INFO: Gmail service rebuilt with refreshed credentials.")
                        except Exception as e_build:
                            print(f"ERROR: Failed to rebuild Gmail service after refresh: {e_build}. Stopping.")
                            led_off()
                            break
                    else: # Refresh failed
                        print("ERROR: Scheduled credential refresh failed. Attempting full re-authentication in next cycle if creds invalid.")
                        # The main loop's check for `creds.valid` will handle re-triggering `get_gmail_service`
                        # which will then guide user to run auth_gen.py if token.json is problematic.
                        # For now, we mark as if save occurred to prevent rapid retries of failed refresh.
                        led_off() # Turn off LED as we might be in a bad state
                elif creds and creds.valid and not creds.refresh_token:
                    print("INFO: Credentials are valid but no refresh token. Cannot perform scheduled refresh.")
                    print(f"If issues arise, run auth_gen.py to get a token with a refresh token.")

                last_creds_save_time = current_time # Update time regardless of refresh success to avoid tight loop on failure
            
            time.sleep(1) # Poll every 10 seconds (increased from 1s)
    except KeyboardInterrupt:
        print("\nStopping email listener...")
    except Exception as e:
        print(f"Unhandled exception in main loop: {e}")
    finally:
        print("INFO: Shutting down. Turning LED OFF and cleaning up resources.")
        led_off()
        cleanup_gpio()
        if os.path.exists(AUDIO_FILENAME):
            try:
                os.remove(AUDIO_FILENAME)
                print(f"Cleaned up temporary audio file: {AUDIO_FILENAME}")
            except Exception as e:
                print(f"Error cleaning up temporary audio file {AUDIO_FILENAME} on exit: {e}")
        print("Listener stopped.")

if __name__ == "__main__":
    main()
