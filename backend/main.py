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

# Correct vault.log path relative to backend folder
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Update vault.log path to point to the root directory
LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")  # Path to vault.log

ERROR_JSON_PATH = os.path.join(CURRENT_DIR, "errors.json") # path to errors.json


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

@app.get("/resolutions")
def get_resolutions():
    # Update path for error.json inside the backend directory
    print(f"Looking for error.json at: {ERROR_JSON_PATH}")  # Debugging log
    if not os.path.exists(ERROR_JSON_PATH):
        return JSONResponse(status_code=404, content={"error": "Resolution file not found."})
    with open(ERROR_JSON_PATH, "r") as f:
        data = json.load(f)
    return JSONResponse(content=data)


# WebSocket endpoint to listen for anomalies
@app.websocket("/ws/issues")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await asyncio.sleep(3600)  # Keep connection open
    except WebSocketDisconnect:
        active_connections.remove(websocket)

# Anomaly detection logic
def send_issue_to_frontend(issue: str):
    """Send detected issue to all active WebSocket clients"""
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
                for line in lines[-10:]:  # Check the last 10 lines
                    self.detect_anomalies(line)

    def detect_anomalies(self, log_line: str):
        """Detect anomalies in Vault logs."""
        if re.search(r"Vault sealed", log_line):
            self.report_issue("Vault is sealed")
        elif re.search(r"token revoked", log_line):
            self.report_issue("Token was revoked")
        elif re.search(r"generated new token", log_line):
            self.report_issue("New token generated")

    def report_issue(self, issue: str):
        """Report detected issue to WebSocket clients."""
        print(f"Detected Issue: {issue}")
        send_issue_to_frontend(issue)

# Background task to monitor logs
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
    """Start log monitoring on app startup."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, run_log_monitor)



# from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
# from fastapi.middleware.cors import CORSMiddleware
# from typing import List
# import os
# import re
# import asyncio
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from fastapi.responses import JSONResponse
# import json

# # FastAPI setup
# app = FastAPI()

# # Middleware for CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Correct vault.log path relative to backend folder
# CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# LOG_FILE = os.path.join(CURRENT_DIR, "..", "vault.log")
# # LOG_FILE = os.path.join(CURRENT_DIR, "vault.log")

# # WebSocket connection list
# active_connections = []

# @app.get("/")
# def read_root():
#     return {"message": "FastAPI is running"}

# @app.get("/logs", response_model=List[str])
# def get_logs(limit: int = 100):
#     if not os.path.exists(LOG_FILE):
#         return ["Log file not found."]
#     with open(LOG_FILE, "r") as f:
#         lines = f.readlines()[-limit:]
#     return [line.strip() for line in lines]

# @app.get("/resolutions")
# def get_resolutions():
#     file_path = os.path.join(CURRENT_DIR, "errors.json")
#     if not os.path.exists(file_path):
#         return JSONResponse(status_code=404, content={"error": "Resolution file not found."})
#     with open(file_path, "r") as f:
#         data = json.load(f)
#     return JSONResponse(content=data)

# # WebSocket endpoint to listen for anomalies
# @app.websocket("/ws/issues")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     active_connections.append(websocket)
#     try:
#         while True:
#             await asyncio.sleep(3600)  # Keep connection open
#     except WebSocketDisconnect:
#         active_connections.remove(websocket)

# # Anomaly detection logic
# def send_issue_to_frontend(issue: str):
#     """Send detected issue to all active WebSocket clients"""
#     for connection in active_connections:
#         try:
#             asyncio.create_task(connection.send_text(issue))
#         except Exception as e:
#             print(f"Error sending to websocket: {e}")

# class VaultLogMonitor(FileSystemEventHandler):
#     def __init__(self, log_file_path: str):
#         self.log_file_path = log_file_path

#     def on_modified(self, event):
#         if event.src_path == self.log_file_path:
#             with open(self.log_file_path, 'r') as f:
#                 lines = f.readlines()
#                 for line in lines[-10:]:  # Check the last 10 lines
#                     self.detect_anomalies(line)

#     def detect_anomalies(self, log_line: str):
#         """Detect anomalies in Vault logs."""
#         if re.search(r"Vault sealed", log_line):
#             self.report_issue("Vault is sealed")
#         elif re.search(r"token revoked", log_line):
#             self.report_issue("Token was revoked")
#         elif re.search(r"generated new token", log_line):
#             self.report_issue("New token generated")

#     def report_issue(self, issue: str):
#         """Report detected issue to WebSocket clients."""
#         print(f"Detected Issue: {issue}")
#         send_issue_to_frontend(issue)

# # Background task to monitor logs
# def run_log_monitor():
#     event_handler = VaultLogMonitor(LOG_FILE)
#     observer = Observer()
#     observer.schedule(event_handler, path=LOG_FILE, recursive=False)
#     observer.start()
#     try:
#         while True:
#             asyncio.sleep(1)
#     except KeyboardInterrupt:
#         observer.stop()
#     observer.join()

# @app.on_event("startup")
# async def startup_event():
#     """Start log monitoring on app startup."""
#     loop = asyncio.get_event_loop()
#     loop.run_in_executor(None, run_log_monitor)
