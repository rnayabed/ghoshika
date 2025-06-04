# ghoshika - #vibemaxxing

![It's just getting started](https://external-content.duckduckgo.com/iu/?u=https%3A%2F%2Fi.kym-cdn.com%2Fphotos%2Fimages%2Foriginal%2F002%2F297%2F483%2F14d.png&f=1&nofb=1&ipt=8601b719faaf18bf2ed97b4cfed571fcf7ab2cbac461359b3da2fe34c6301909)

- Recreate [PhonePe SmartSpeaker]() on a personal level, for free.
- Explore AI Pair programming with [Aider](https://aider.chat/) and Gemini 2.5 Pro Preview
- Files
  - `main_gmail_poll.py`:  Faster, but locked with gmail only
  - `main_ntfy_pub_sub.py`: Slower, but much easier to use
    - The slowness is mainly attributed to gmail taking a few seconds longer to forward mails. 
    Other mail providers may be faster.


## Setup

### Prerequisites 

- Python3 w/ packages installed: `pip install -r requirements.txt`
- Sound available
- IDFC First Bank accounts w/ transaction alerts setup on gmail only
  - `main_ntfy_pub_sub.py` is not mail vendor locked and can be used with other providers.

### main_gmail_poll.py

- Obtain `google_credentials.json` from Google Cloud
  - Enable Google Auth Platform and create `Desktop` OAuth Client
  - Enable Gmail API
- Run `auth_gen.py` to generate `google_token.json`
  - Login with gmail account where transaction alerts are sent
- If aim to run on a headless device, make sure to copy `google_token.json` and  `google_credentials.json` to the target device
- Run `main_gmail_poll.py` on target device
- Enjoy

### main_ntfy_pub_sub.py

- Setup email forwarding from gmail to ntfy
  - Make sure to change the ntfy pub/sub topic
- Run `main_ntfy_pub_sub.py` on target device