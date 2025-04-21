from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import re
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from fastapi.responses import JSONResponse
import json

# FastAPI setup
app = FastAPI()

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
ERROR_JSON_PATH = os.path.join(CURRENT_DIR, "errors.json")

# WebSocket connection list
active_connections = []

@app.get("/")
def read_root():
    return {"message": "FastAPI is running"}

@app.get("/logs", response_model=List[str])
def get_logs(limit: int = 100):
    if not os.path.exists(LOG_FILE):
        return ["Log file not found."]
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()[-limit:]
    return [line.strip() for line in lines]

def extract_vault_address_from_logs(log_file):
    if not os.path.exists(log_file):
        return "http://127.0.0.1:8200"  # Fallback default
    with open(log_file, "r") as f:
        for line in f:
            match = re.search(r'(https?://[^\s":]+:\d+)', line)
            if match:
                return match.group(1)
    return "http://127.0.0.1:8200"

@app.get("/resolutions")
def get_resolutions():
    if not os.path.exists(ERROR_JSON_PATH):
        return JSONResponse(status_code=404, content={"error": "Resolution file not found."})

    with open(ERROR_JSON_PATH, "r") as f:
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
            await asyncio.sleep(3600)  # Keep connection open
    except WebSocketDisconnect:
        active_connections.remove(websocket)

def send_issue_to_frontend(issue: str):
    for connection in active_connections:
        try:
            asyncio.create_task(connection.send_text(issue))
        except Exception as e:
            print(f"Error sending to websocket: {e}")

class VaultLogMonitor(FileSystemEventHandler):
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path

    def on_modified(self, event):
        if event.src_path == self.log_file_path:
            with open(self.log_file_path, 'r') as f:
                lines = f.readlines()
                for line in lines[-10:]:
                    self.detect_anomalies(line)

    def detect_anomalies(self, log_line: str):
        if re.search(r"Vault sealed", log_line):
            self.report_issue("Vault is sealed")
        elif re.search(r"token revoked", log_line):
            self.report_issue("Token was revoked")
        elif re.search(r"generated new token", log_line):
            self.report_issue("New token generated")

    def report_issue(self, issue: str):
        print(f"Detected Issue: {issue}")
        send_issue_to_frontend(issue)

def run_log_monitor():
    event_handler = VaultLogMonitor(LOG_FILE)
    observer = Observer()
    observer.schedule(event_handler, path=LOG_FILE, recursive=False)
    observer.start()
    try:
        while True:
            asyncio.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_log_monitor)
