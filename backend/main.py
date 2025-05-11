import os
import re
import json
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
JSON_FILE = "error_solutions.json"
CONFIG_FILE = "vault_config.json"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# FastAPI app initialization
app = FastAPI()

# Enable CORS for all origins (adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections list
active_connections: List[WebSocket] = []

# --- Helper Functions ---

def get_vault_config_value(key: str, default: str = "") -> str:
    """Retrieve configuration value from the vault_config.json."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get(key, default)
            except json.JSONDecodeError:
                print("❗ vault_config.json is malformed.")
    return default

def load_resolutions_from_json() -> List[dict]:
    """Load previously saved error resolutions from JSON."""
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_resolutions_to_json(data: List[dict]):
    """Save updated error resolutions back to JSON."""
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def send_issue_to_frontend(message: str):
    """Send error resolution message to frontend via WebSocket."""
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            print(f"WebSocket send error: {e}")

async def fetch_solution_from_openai(error_message: str) -> str:
    """Fetch error resolution from OpenAI's GPT model."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a Vault expert assistant. When I provide a Vault issue, return a solution strictly in JSON format with the following structure:\n\n"
                        "{\n"
                        "  \"issue\": \"<short issue summary>\",\n"
                        "  \"root_cause\": \"<brief explanation>\",\n"
                        "  \"resolution_steps\": [\n"
                        "    {\n"
                        "      \"step\": <number>,\n"
                        "      \"description\": \"<action>\",\n"
                        "      \"command\": \"<command>\",\n"
                        "      \"expected_output\": {\"<key>\": <value>}\n"
                        "    }\n"
                        "  ],\n"
                        "  \"recommendations\": [\"<rec1>\", \"<rec2>\"]\n"
                        "}\n\n"
                        "Do NOT include real Vault logs, only return JSON. Here's the issue:"
                    )
                },
                {
                    "role": "user",
                    "content": f"{error_message}"
                }
            ],
            temperature=0,
            max_tokens=500,
        )
        solution = response.choices[0].message.content.strip()
        return solution
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return "❗ Failed to fetch solution from AI."

# Define a list of known error keywords
error_keywords = [
    "vault is sealed",
    "vault is unsealed",
    "authentication failed",
    "permission denied",
    "access denied",
    "failed to authenticate",
    "invalid token",
    "token expired",
    "insufficient permissions",
    "server unavailable",
    "server timeout",
    "vault not initialized",
    "missing secret",
    "failed to retrieve secret",
    "secrets engine error",
    "failed to create secret",
    "failed to read secret",
    "storage backend error",
    "database connection failed",
    "unable to reach backend",
    "unexpected shutdown",
    "vault service crashed",
    "vault process terminated",
    "error in policy",
    "invalid policy",
    "failed to update policy",
    "policy creation failed",
    "service unavailable",
    "raft leadership change",
    "raft consensus failure",
    "replication failure",
    "seal migration error",
    "mounting path error",
    "mount failed",
    "error initializing Vault",
    "seal key threshold not met",
    "failed to verify token",
    "lease expired",
    "lease revocation error",
    "audit logging error",
    "unrecognized API request",
    "vault restart required",
    "failed to initialize storage",
    "metrics collection failed",
    "failed to configure backend",
    "invalid address for Vault",
    "incorrect token permissions",
    "failed to renew lease",
    "plugin error",
    "plugin initialization failed",
    "revoked lease",
]

def match_known_error(log_line: str) -> str | None:
    """Match known errors from the log."""
    line = log_line.lower()
    for keyword in error_keywords:
        if keyword in line:
            return keyword
    return None


# def match_known_error(log_line: str) -> str | None:
#     """Match known errors from the log."""
#     line = log_line.lower()
#     if "vault is sealed" in line:
#         return "vault is sealed"
#     return None

async def handle_error(error_key: str):
    """Handle error and fetch resolution."""
    resolutions = load_resolutions_from_json()

    # Check if the error already has a resolution
    resolution = next(
        (item["resolution"] for item in resolutions if item["error"].lower() == error_key.lower()),
        None
    )

    # If not found, fetch solution from OpenAI
    if not resolution:
        print("🔎 New error detected, querying OpenAI...")
        resolution = await fetch_solution_from_openai(error_key)
        resolutions.append({"error": error_key, "resolution": resolution})
        save_resolutions_to_json(resolutions)

    # Replace placeholders in resolution with actual config values
    vault_address = get_vault_config_value("vault_address", "http://127.0.0.1:8200")
    if isinstance(resolution, str):
        resolution_with_addr = resolution.replace("<Vault ADDR>", vault_address)
    else:
        resolution_with_addr = resolution

    # Send resolution to frontend
    await send_issue_to_frontend(f"Problem: {error_key}\n\nResolution:\n{resolution_with_addr}")

def extract_error_message(log_line: str) -> str | None:
    """Extract error message from log line."""
    if any(keyword in log_line.lower() for keyword in [
    "vault is sealed",
    "vault is unsealed",
    "authentication failed",
    "permission denied",
    "access denied",
    "failed to authenticate",
    "invalid token",
    "token expired",
    "insufficient permissions",
    "server unavailable",
    "server timeout",
    "vault not initialized",
    "missing secret",
    "failed to retrieve secret",
    "secrets engine error",
    "failed to create secret",
    "failed to read secret",
    "storage backend error",
    "database connection failed",
    "unable to reach backend",
    "unexpected shutdown",
    "vault service crashed",
    "vault process terminated",
    "error in policy",
    "invalid policy",
    "failed to update policy",
    "policy creation failed",
    "service unavailable",
    "raft leadership change",
    "raft consensus failure",
    "replication failure",
    "seal migration error",
    "mounting path error",
    "mount failed",
    "error initializing Vault",
    "seal key threshold not met",
    "failed to verify token",
    "lease expired",
    "lease revocation error",
    "audit logging error",
    "unrecognized API request",
    "vault restart required",
    "failed to initialize storage",
    "metrics collection failed",
    "failed to configure backend",
    "invalid address for Vault",
    "incorrect token permissions",
    "failed to renew lease",
    "plugin error",
    "plugin initialization failed",
    "revoked lease",
]):
        return match_known_error(log_line) or log_line.strip()
    return None

async def monitor_logs_async():
    """Monitor logs asynchronously and handle errors."""
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
                    print(f"🛑 Error detected: {error_message}")
                    await handle_error(error_message)
            else:
                await asyncio.sleep(1)

# --- FastAPI Routes ---

@app.get("/")
def read_root():
    """Root endpoint to check if the app is running."""
    return {"message": "Vault Log Watcher API is running securely."}

@app.get("/logs", response_model=List[str])
def get_logs(limit: int = 100):
    """Get recent logs."""
    if not os.path.exists(LOG_FILE):
        return ["Log file not found."]
    with open(LOG_FILE, "r") as f:
        return [line.strip() for line in f.readlines()[-limit:]]

@app.get("/resolutions")
def get_resolutions():
    """Get list of error resolutions."""
    if not os.path.exists(JSON_FILE):
        return JSONResponse(status_code=404, content={"error": "Resolution file not found."})
    try:
        with open(JSON_FILE, "r") as f:
            data = json.load(f)
        vault_address = get_vault_config_value("vault_address", "http://127.0.0.1:8200")
        for item in data:
            if "<Vault ADDR>" in item["resolution"]:
                item["resolution"] = item["resolution"].replace("<Vault ADDR>", vault_address)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.websocket("/ws/issues")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for sending real-time error resolutions."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

@app.get("/search_error/{error_message}")
async def search_error(error_message: str):
    """Search for error and display resolution."""
    await handle_error(error_message)
    return {"message": "Check UI for solution."}

@app.on_event("startup")
async def startup_event():
    """Startup event to start log monitoring."""
    print("🚀 Starting Vault log monitoring...")
    asyncio.create_task(monitor_logs_async())



# import os
# import re
# import json
# import asyncio
# from typing import List

# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# from openai import OpenAI
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # Configuration
# CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
# JSON_FILE = "error_solutions.json"
# CONFIG_FILE = "vault_config.json"
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# openai_client = OpenAI(api_key=OPENAI_API_KEY)

# # FastAPI app initialization
# app = FastAPI()

# # Enable CORS for all origins (adjust in prod)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # WebSocket connections list
# active_connections: List[WebSocket] = []

# # --- Helper Functions ---

# def get_vault_config_value(key: str, default: str = "") -> str:
#     if os.path.exists(CONFIG_FILE):
#         with open(CONFIG_FILE, "r", encoding="utf-8") as f:
#             try:
#                 data = json.load(f)
#                 return data.get(key, default)
#             except json.JSONDecodeError:
#                 print("❗ vault_config.json is malformed.")
#     return default

# def load_resolutions_from_json() -> List[dict]:
#     if os.path.exists(JSON_FILE):
#         with open(JSON_FILE, "r", encoding="utf-8") as f:
#             return json.load(f)
#     return []

# def save_resolutions_to_json(data: List[dict]):
#     with open(JSON_FILE, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=4, ensure_ascii=False)

# async def send_issue_to_frontend(message: str):
#     for connection in active_connections:
#         try:
#             await connection.send_text(message)
#         except Exception as e:
#             print(f"WebSocket send error: {e}")

# async def fetch_solution_from_openai(error_message: str) -> str:
#     try:
#         response = openai_client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": (
#                         "You are a Vault expert assistant. When I provide a Vault issue, return a solution strictly in JSON format with the following structure:\n\n"
#                         "{\n"
#                         "  \"issue\": \"<short issue summary>\",\n"
#                         "  \"root_cause\": \"<brief explanation>\",\n"
#                         "  \"resolution_steps\": [\n"
#                         "    {\n"
#                         "      \"step\": <number>,\n"
#                         "      \"description\": \"<action>\",\n"
#                         "      \"command\": \"<command>\",\n"
#                         "      \"expected_output\": {\"<key>\": <value>}\n"
#                         "    }\n"
#                         "  ],\n"
#                         "  \"recommendations\": [\"<rec1>\", \"<rec2>\"]\n"
#                         "}\n\n"
#                         "Do NOT include real Vault logs, only return JSON. Here's the issue:"
#                     )
#                 },
#                 {
#                     "role": "user",
#                     "content": f"{error_message}"
#                 }
#             ],
#             temperature=0,
#             max_tokens=500,
#         )
#         return response.choices[0].message.content.strip()
#     except Exception as e:
#         print(f"OpenAI API error: {e}")
#         return "❗ Failed to fetch solution from AI."

# def match_known_error(log_line: str) -> str | None:
#     line = log_line.lower()
#     if "vault is sealed" in line:
#         return "vault is sealed"
#     return None

# async def handle_error(error_key: str):
#     resolutions = load_resolutions_from_json()

#     for item in resolutions:
#         if item["error"].lower() == error_key.lower():
#             resolution = item["resolution"]
#             break
#     else:
#         print("🔎 New error detected, querying OpenAI...")
#         resolution = await fetch_solution_from_openai(error_key)
#         resolutions.append({"error": error_key, "resolution": resolution})
#         save_resolutions_to_json(resolutions)

#     vault_address = get_vault_config_value("vault_address", "http://127.0.0.1:8200")

#     if isinstance(resolution, str):
#         resolution_with_addr = resolution.replace("<Vault ADDR>", vault_address)
#     else:
#         resolution_with_addr = resolution

#     await send_issue_to_frontend(f"Problem: {error_key}\n\nResolution:\n{resolution_with_addr}")

# def extract_error_message(log_line: str) -> str | None:
#     if any(keyword in log_line.lower() for keyword in ["error", "failed", "vault is sealed"]):
#         return match_known_error(log_line) or log_line.strip()
#     return None

# async def monitor_logs_async():
#     if not os.path.exists(LOG_FILE):
#         print(f"❗ Log file {LOG_FILE} does not exist.")
#         return

#     with open(LOG_FILE, "r", encoding="utf-8") as log_file:
#         log_file.seek(0, os.SEEK_END)
#         while True:
#             line = log_file.readline()
#             if line:
#                 error_message = extract_error_message(line)
#                 if error_message:
#                     print(f"🛑 Error detected: {error_message}")
#                     await handle_error(error_message)
#             else:
#                 await asyncio.sleep(1)

# # --- FastAPI Routes ---

# @app.get("/")
# def read_root():
#     return {"message": "Vault Log Watcher API is running securely."}

# @app.get("/logs", response_model=List[str])
# def get_logs(limit: int = 100):
#     if not os.path.exists(LOG_FILE):
#         return ["Log file not found."]
#     with open(LOG_FILE, "r") as f:
#         return [line.strip() for line in f.readlines()[-limit:]]

# @app.get("/resolutions")
# def get_resolutions():
#     if not os.path.exists(JSON_FILE):
#         return JSONResponse(status_code=404, content={"error": "Resolution file not found."})
#     try:
#         with open(JSON_FILE, "r") as f:
#             data = json.load(f)
#         vault_address = get_vault_config_value("vault_address", "http://127.0.0.1:8200")
#         for item in data:
#             if "<Vault ADDR>" in item["resolution"]:
#                 item["resolution"] = item["resolution"].replace("<Vault ADDR>", vault_address)
#         return JSONResponse(content=data)
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})

# @app.websocket("/ws/issues")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     active_connections.append(websocket)
#     try:
#         while True:
#             await websocket.receive_text()
#     except WebSocketDisconnect:
#         active_connections.remove(websocket)

# @app.get("/search_error/{error_message}")
# async def search_error(error_message: str):
#     await handle_error(error_message)
#     return {"message": "Check UI for solution."}

# @app.on_event("startup")
# async def startup_event():
#     print("🚀 Starting Vault log monitoring...")
#     asyncio.create_task(monitor_logs_async())






# import os
# import re
# import json
# import asyncio
# from typing import List

# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.responses import JSONResponse
# from fastapi.middleware.cors import CORSMiddleware
# from openai import OpenAI
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # Configuration
# CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
# JSON_FILE = "error_solutions.json"
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# openai_client = OpenAI(api_key=OPENAI_API_KEY)

# # FastAPI app initialization
# app = FastAPI()

# # Enable CORS for all origins (you can restrict it as needed)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # In-memory list of active WebSocket connections
# active_connections: List[WebSocket] = []

# # --- Helper Functions ---

# def extract_vault_address_from_logs(log_file: str) -> str:
#     if not os.path.exists(log_file):
#         return "http://127.0.0.1:8200"
#     with open(log_file, "r") as f:
#         for line in f:
#             match = re.search(r'(https?://[^\s":]+:\d+)', line)
#             if match:
#                 return match.group(1)
#     return "http://127.0.0.1:8200"

# def load_resolutions_from_json() -> List[dict]:
#     if os.path.exists(JSON_FILE):
#         with open(JSON_FILE, "r", encoding="utf-8") as f:
#             return json.load(f)
#     return []

# def save_resolutions_to_json(data: List[dict]):
#     with open(JSON_FILE, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=4, ensure_ascii=False)

# async def send_issue_to_frontend(message: str):
#     for connection in active_connections:
#         try:
#             await connection.send_text(message)
#         except Exception as e:
#             print(f"WebSocket send error: {e}")

# async def fetch_solution_from_openai(error_message: str) -> str:
#     try:
#         response = openai_client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": (
#                         "You are a Vault expert assistant. When I provide a Vault issue, return a solution strictly in JSON format with the following structure:\n\n"
#                         "{\n"
#                         "  \"issue\": \"<short issue summary>\",\n"
#                         "  \"root_cause\": \"<brief explanation of what causes the issue>\",\n"
#                         "  \"resolution_steps\": [\n"
#                         "    {\n"
#                         "      \"step\": <number>,\n"
#                         "      \"description\": \"<what to do>\",\n"
#                         "      \"command\": \"<command to run>\",\n"
#                         "      \"expected_output\": {\n"
#                         "        \"<key>\": <value>\n"
#                         "      }\n"
#                         "    }\n"
#                         "  ],\n"
#                         "  \"optional_automation\": {\n"
#                         "    \"description\": \"<optional automation tip>\",\n"
#                         "    \"config_example\": {\n"
#                         "      \"<config_file>\": {\n"
#                         "        \"<key>\": \"<value>\"\n"
#                         "      }\n"
#                         "    },\n"
#                         "    \"note\": \"<note on how to apply automation>\"\n"
#                         "  },\n"
#                         "  \"recommendations\": [\n"
#                         "    \"<proactive recommendation 1>\",\n"
#                         "    \"<proactive recommendation 2>\"\n"
#                         "  ]\n"
#                         "}\n\n"
#                         "Now respond only in JSON. Here's the issue: Vault is sealed."
#                     ),
#                 },
#                 {
#                     "role": "user",
#                     "content": f"Provide only the solution in JSON format for the Vault error: {error_message}"
#                 }
#             ],
#             temperature=0,
#             max_tokens=250,
#         )
#         solution = response.choices[0].message.content.strip()
#         return solution
#     except Exception as e:
#         print(f"OpenAI API error: {e}")
#         return "❗ Failed to fetch solution from AI."

# def match_known_error(log_line: str) -> str | None:
#     line = log_line.lower()
#     if "vault is sealed" in line:
#         return "vault is sealed"
#     return None  # Add more patterns if needed

# async def handle_error(error_key: str):
#     resolutions = load_resolutions_from_json()

#     for item in resolutions:
#         if item["error"].lower() == error_key.lower():
#             resolution = item["resolution"]
#             if isinstance(resolution, dict):
#                 resolution = resolution.get("text", "")
#             break
#     else:
#         print("🔎 New error detected, querying OpenAI...")
#         resolution = await fetch_solution_from_openai(error_key)
#         resolutions.append({"error": error_key, "resolution": resolution})
#         save_resolutions_to_json(resolutions)

#     vault_address = extract_vault_address_from_logs(LOG_FILE)

#     if isinstance(resolution, str):
#         resolution_with_addr = resolution.replace("<Vault ADDR>", vault_address)
#     else:
#         resolution_with_addr = resolution

#     await send_issue_to_frontend(f"Problem: {error_key}\n\nResolution:\n{resolution_with_addr}")

# def extract_error_message(log_line: str) -> str | None:
#     if any(keyword in log_line.lower() for keyword in ["error", "failed", "vault is sealed"]):
#         matched = match_known_error(log_line)
#         return matched or log_line.strip()
#     return None

# async def monitor_logs_async():
#     if not os.path.exists(LOG_FILE):
#         print(f"❗ Log file {LOG_FILE} does not exist.")
#         return

#     with open(LOG_FILE, "r", encoding="utf-8") as log_file:
#         log_file.seek(0, os.SEEK_END)
#         while True:
#             line = log_file.readline()
#             if line:
#                 error_message = extract_error_message(line)
#                 if error_message:
#                     print(f"\n🛑 Error detected: {error_message}")
#                     await handle_error(error_message)
#             else:
#                 await asyncio.sleep(1)

# # --- FastAPI Routes ---

# @app.get("/")
# def read_root():
#     return {"message": "Vault Log Watcher API is running."}

# @app.get("/logs", response_model=List[str])
# def get_logs(limit: int = 100):
#     if not os.path.exists(LOG_FILE):
#         return ["Log file not found."]
#     with open(LOG_FILE, "r") as f:
#         return [line.strip() for line in f.readlines()[-limit:]]

# @app.get("/resolutions")
# def get_resolutions():
#     if not os.path.exists(JSON_FILE):
#         return JSONResponse(status_code=404, content={"error": "Resolution file not found."})

#     try:
#         with open(JSON_FILE, "r") as f:
#             data = json.load(f)

#         vault_address = extract_vault_address_from_logs(LOG_FILE)
#         for item in data:
#             if "<Vault ADDR>" in item["resolution"]:
#                 item["resolution"] = item["resolution"].replace("<Vault ADDR>", vault_address)

#         return JSONResponse(content=data)
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})

# @app.websocket("/ws/issues")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     active_connections.append(websocket)
#     try:
#         while True:
#             await websocket.receive_text()
#     except WebSocketDisconnect:
#         active_connections.remove(websocket)

# @app.get("/search_error/{error_message}")
# async def search_error(error_message: str):
#     await handle_error(error_message)
#     return {"message": "Check UI for solution"}

# @app.on_event("startup")
# async def startup_event():
#     print("🚀 Starting Vault log monitoring...")
#     asyncio.create_task(monitor_logs_async())
