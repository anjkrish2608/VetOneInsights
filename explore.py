import os
import requests
from dotenv import load_dotenv

load_dotenv()
base = os.environ["VETONE_BASE_URL"]

# First call can take ~20s because the API scales down when idle
resp = requests.post(
    f"{base}/auth/token",
    json={
        "client_id": os.environ["VETONE_CLIENT_ID"],
        "client_secret": os.environ["VETONE_CLIENT_SECRET"],
    },
    timeout=60,
)
print(resp.status_code)
print(resp.json())