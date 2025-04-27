import os
import re
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv
from typing import List

# Load environment variables
load_dotenv()

# Configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
JSON_FILE = "error_solutions.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# FastAPI app
app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# List of active WebSocket connections
active_connections: List[WebSocket] = []

# --- Helper Functions ---

def extract_vault_address_from_logs(log_file):
    if not os.path.exists(log_file):
        return "http://127.0.0.1:8200"
    with open(log_file, "r") as f:
        for line in f:
            match = re.search(r'(https?://[^\s":]+:\d+)', line)
            if match:
                return match.group(1)
    return "http://127.0.0.1:8200"

def load_resolutions_from_json():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_resolutions_to_json(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def send_issue_to_frontend(message: str):
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            print(f"WebSocket send error: {e}")

async def fetch_solution_from_openai(error_message: str):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional DevOps Engineer. When asked about Vault errors, respond ONLY with the exact terminal commands required to fix the error. Do not include explanations, just provide the commands. Example response: 'vault operator unseal <unseal_key>'."
                },
                {
                    "role": "user",
                    "content": f"Provide only the terminal commands to fix this Vault error (no explanation): {error_message}"
                }
            ],
            temperature=0,
            max_tokens=150,  # Adjusted max tokens to avoid unnecessary verbosity
        )
        solution = response.choices[0].message.content.strip()
        # Ensure we only return commands and remove any explanations or extraneous text
        solution = re.sub(r"(?:\n|^)[^\w\s\-\.\:]+(?:\n|$)", "", solution).strip()  # Remove non-command text.
        return solution
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "❗ Failed to fetch solution from AI."



def match_known_error(log_line: str):
    """Try to match the log line with known errors."""
    log_line = log_line.lower()

    if "vault is sealed" in log_line:
        return "vault is sealed"

    # Add more patterns here if needed
    return None

async def handle_error(error_key: str):
    """Handle error: check in JSON, fetch from OpenAI if new, and send to frontend."""
    resolutions = load_resolutions_from_json()

    # Check if error already exists
    for item in resolutions:
        if item["error"] == error_key:
            resolution = item["resolution"]
            break
    else:
        print(f"🔎 New error detected, querying OpenAI...")
        ai_solution = await fetch_solution_from_openai(error_key)

        # Add new entry
        new_entry = {
            "error": error_key,
            "resolution": ai_solution
        }
        resolutions.append(new_entry)
        save_resolutions_to_json(resolutions)
        resolution = ai_solution

    vault_address = extract_vault_address_from_logs(LOG_FILE)
    resolution_with_addr = resolution.replace("<Vault ADDR>", vault_address)
    solution_text = f"Problem: {error_key}\n\nResolution:\n{resolution_with_addr}"
    await send_issue_to_frontend(solution_text)

def extract_error_message(log_line: str):
    """Extract error messages from log line."""
    if "error" in log_line.lower() or "failed" in log_line.lower() or "vault is sealed" in log_line.lower():
        matched_error = match_known_error(log_line)
        if matched_error:
            return matched_error
        return log_line.strip()
    return None

async def monitor_logs_async():
    """Async monitor for Vault logs."""
    if not os.path.exists(LOG_FILE):
        print(f"❗ Log file {LOG_FILE} does not exist.")
        return

    with open(LOG_FILE, "r", encoding="utf-8") as log_file:
        log_file.seek(0, os.SEEK_END)

        while True:
            line = log_file.readline()
            if line:
                error_message = extract_error_message(line)
                if error_message:
                    print(f"\n🛑 Error detected: {error_message}")
                    await handle_error(error_message)
            else:
                await asyncio.sleep(1)

# --- FastAPI Endpoints ---

@app.get("/")
def read_root():
    return {"message": "FastAPI is running"}

@app.get("/logs", response_model=List[str])
def get_logs(limit: int = 100):
    if not os.path.exists(LOG_FILE):
        return ["Log file not found."]
    with open(LOG_FILE, "r") as f:
        return [line.strip() for line in f.readlines()[-limit:]]

@app.get("/resolutions")
def get_resolutions():
    if not os.path.exists(JSON_FILE):
        return JSONResponse(status_code=404, content={"error": "Resolution file not found."})

    with open(JSON_FILE, "r") as f:
        data = json.load(f)

    vault_address = extract_vault_address_from_logs(LOG_FILE)

    for item in data:
        item["resolution"] = item["resolution"].replace("<Vault ADDR>", vault_address)

    return JSONResponse(content=data)

@app.websocket("/ws/issues")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.get("/search_error/{error_message}")
async def search_error(error_message: str):
    await handle_error(error_message)
    return {"message": "Check UI for solution"}

# --- Startup Event ---

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Vault log monitoring...")
    asyncio.create_task(monitor_logs_async())
