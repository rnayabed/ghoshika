import asyncio
import websockets
import json
import re
import os
import signal
import requests # For fetching attachment content
import socket # For socket.gaierror
from gtts import gTTS
import playsound3 # For playing the audio

# Attempt to import RPi.GPIO and set up a flag
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    print("WARNING: RPi.GPIO library not found or not usable. LED functionality will be disabled.")

# --- Configuration ---
NTFY_SERVER_HOST = "ntfy.sh"
NTFY_TOPIC = "ghoshika"
NTFY_WEBSOCKET_URL = f"wss://{NTFY_SERVER_HOST}/{NTFY_TOPIC}/ws"

TARGET_NTFY_TITLE = "Transaction alert from IDFC FIRST Bank"
TARGET_ATTACHMENT_NAME = "attachment.txt"

SEARCH_TEXT_PATTERN = r"has been credited with INR\s*([0-9,]+\.?[0-9]{0,2})\s+on\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})"
AUDIO_FILENAME = "temp_speech_ntfy.mp3"

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
        # Optionally, disable HAS_GPIO if setup fails critically
        # global HAS_GPIO
        # HAS_GPIO = False

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

async def blink_led(times=3, on_duration=0.15, off_duration=0.15):
    if not HAS_GPIO:
        return
    try:
        # print("INFO: Blinking LED...")
        for _ in range(times):
            GPIO.output(LED_GPIO_PIN, GPIO.HIGH)
            await asyncio.sleep(on_duration)
            GPIO.output(LED_GPIO_PIN, GPIO.LOW)
            await asyncio.sleep(off_duration)
        GPIO.output(LED_GPIO_PIN, GPIO.HIGH)  # Ensure LED is ON after blinking (if connection is active)
        # print("INFO: LED Blink finished.")
    except Exception as e:
        print(f"ERROR: Failed to blink LED: {e}")


# --- Text-to-Speech Function ---
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

# --- ntfy Message Processing ---
async def process_transaction_alert(attachment_content):
    match = re.search(SEARCH_TEXT_PATTERN, attachment_content, re.IGNORECASE)
    if match:
        raw_amount = match.group(1)
        extracted_sum_for_speech = raw_amount.replace(",", "")
        transaction_date = match.group(2)
        transaction_time = match.group(3)

        print_message = (
            f"Transaction Alert (from ntfy): Credited amount = INR {raw_amount} "
            f"on {transaction_date} at {transaction_time}"
        )
        print(print_message)

        speech_message = f"Rupees {extracted_sum_for_speech} received."
        speak_text(speech_message)
        await blink_led() # Blink LED after successful processing and speech
    else:
        print(f"Pattern not found in ntfy attachment content:\n---\n{attachment_content[:200]}...\n---")

async def ntfy_listener():
    print(f"Connecting to ntfy.sh WebSocket: {NTFY_WEBSOCKET_URL}")
    print(f"Listening for topic: {NTFY_TOPIC}")
    print(f"Expecting title: \"{TARGET_NTFY_TITLE}\"")
    print(f"Expecting attachment: \"{TARGET_ATTACHMENT_NAME}\"")

    # Flag to control the main loop
    running = True
    
    # Create an event to signal when to stop
    stop_event = asyncio.Event()
    
    # Define signal handlers
    def signal_handler():
        nonlocal running
        print("\nReceived termination signal. Shutting down...")
        running = False
        stop_event.set()
    
    # Register signal handlers for both SIGINT and SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    while running:
        # led_on() # Attempt to turn LED ON indicating an active connection attempt or state
        try:
            async with websockets.connect(NTFY_WEBSOCKET_URL) as websocket:
                print(f"Successfully connected to {NTFY_WEBSOCKET_URL}. LED ON.")
                led_on() # Ensure LED is on after successful connection
                async for message_json in websocket:
                    try:
                        message = json.loads(message_json)
                        # print(f"Received ntfy message: {message}") # For debugging all messages

                        if message.get("event") == "message" and \
                           message.get("title") == TARGET_NTFY_TITLE:
                            
                            print(f"Received relevant ntfy message: {message}")

                            attachment_info = message.get("attachment")
                            if attachment_info and attachment_info.get("name") == TARGET_ATTACHMENT_NAME:
                                attachment_url = attachment_info.get("url")
                                if not attachment_url:
                                    print(f"Error: Attachment '{TARGET_ATTACHMENT_NAME}' found but no URL provided.")
                                    continue
                                
                                if not attachment_url.startswith(('http://', 'https://')):
                                    if attachment_url.startswith('/'):
                                        attachment_url = f"https://{NTFY_SERVER_HOST}{attachment_url}"
                                    else:
                                        print(f"Warning: Attachment URL '{attachment_url}' might be malformed. Trying as is.")

                                print(f"Found matching notification with attachment. Fetching: {attachment_url}")
                                try:
                                    response = requests.get(attachment_url, timeout=10)
                                    response.raise_for_status()
                                    attachment_content = response.text
                                    
                                    print(f"Successfully fetched attachment '{TARGET_ATTACHMENT_NAME}'. Processing...")
                                    await process_transaction_alert(attachment_content)

                                except requests.exceptions.RequestException as req_err:
                                    print(f"Error fetching attachment from {attachment_url}: {req_err}")
                                except Exception as e:
                                    print(f"An unexpected error occurred while fetching or processing attachment: {e}")
                            else:
                                print(f"Message title matched, but no valid attachment '{TARGET_ATTACHMENT_NAME}' found or attachment info missing.")
                        # else:
                            # print(f"Ignoring ntfy message (event: {message.get('event')}, title: {message.get('title')})")

                    except json.JSONDecodeError:
                        print(f"Error decoding JSON from ntfy: {message_json}")
                    except Exception as e:
                        print(f"Error processing ntfy message: {e}")
        
        except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK) as e:
            print(f"WebSocket connection closed: {e}. LED OFF. Reconnecting in 5 seconds...")
            led_off()
        except websockets.exceptions.InvalidURI:
            print(f"Error: Invalid WebSocket URI: {NTFY_WEBSOCKET_URL}. LED OFF. Please check configuration.")
            led_off()
            break 
        except ConnectionRefusedError:
            print(f"Error: Connection refused for {NTFY_WEBSOCKET_URL}. LED OFF. Is ntfy.sh reachable? Reconnecting in 5 seconds...")
            led_off()
        except socket.gaierror:
            print(f"Error: Could not resolve hostname {NTFY_SERVER_HOST}. LED OFF. Check network. Reconnecting in 10 seconds...")
            led_off()
            await asyncio.sleep(5) # Extra 5s for DNS, total 10s with outer sleep
        except Exception as e:
            print(f"An unexpected WebSocket error occurred: {e}. LED OFF. Reconnecting in 5 seconds...")
            led_off()
        
        await asyncio.sleep(5)

# --- Main Execution ---
if __name__ == "__main__":
    setup_gpio()
    try:
        asyncio.run(ntfy_listener())
    # KeyboardInterrupt is now handled by the signal handler in ntfy_listener
    except Exception as e:
        print(f"Unhandled exception in main: {e}")
    finally:
        print("INFO: Shutting down. Turning LED OFF and cleaning up resources.")
        led_off() # Ensure LED is off before cleanup
        cleanup_gpio()
        if os.path.exists(AUDIO_FILENAME):
            try:
                os.remove(AUDIO_FILENAME)
                print(f"Cleaned up temporary audio file: {AUDIO_FILENAME}")
            except Exception as e:
                print(f"Error cleaning up temporary audio file {AUDIO_FILENAME} on exit: {e}")
        print("Listener stopped.")
