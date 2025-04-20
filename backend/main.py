# # backend/main.py
# from fastapi import FastAPI, WebSocket, WebSocketDisconnect
# from fastapi.middleware.cors import CORSMiddleware
# from typing import List
# import os
# import re
# import asyncio
# import openai
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from backend.config import OPENAI_API_KEY
# from backend.knowledge_base import knowledge_base, load_knowledge_base, save_knowledge_base

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
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# LOG_FILE = os.path.join(BASE_DIR, "vault.log")

# # WebSocket connection list
# active_connections = []

# # OpenAI Setup
# openai.api_key = OPENAI_API_KEY

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

# def search_local_knowledge_base(error_line):
#     """Check for resolution in local knowledge base"""
#     for known_error, resolution in knowledge_base.items():
#         if known_error.lower() in error_line.lower():
#             return resolution["steps"]
#     return None

# def query_openai_for_solution(error_line):
#     """Query OpenAI API for a resolution if not found locally"""
#     prompt = f"""You are an expert in HashiCorp Vault DevOps.
# You received the following Vault error:
# "{error_line}"

# Give me a step-by-step resolution in this format:

# STEP 1: ...
# STEP 2: ...

# Don't include 'Resolution:', just give exact steps as a Python list of strings.
# """

#     try:
#         response = openai.ChatCompletion.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are a helpful DevOps assistant."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.5,
#         )
#         content = response['choices'][0]['message']['content']
#         steps = re.findall(r"STEP \d+: (.+)", content)
#         return steps
#     except Exception as e:
#         print(f"OpenAI API error: {e}")
#         return []

# def append_to_knowledge_base(error_line, steps):
#     """Append new error resolution to knowledge_base.json"""
#     load_knowledge_base()  # Load the existing knowledge base
#     error_key = error_line.strip()

#     if error_key in knowledge_base:
#         return

#     knowledge_base[error_key] = {"steps": steps}
#     save_knowledge_base()  # Save the updated knowledge base

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
#         else:
#             # For other log entries, check if there's a known resolution
#             steps = search_local_knowledge_base(log_line)
#             if steps:
#                 self.report_resolution(log_line, steps)
#             else:
#                 print(f"Unknown error detected: {log_line}")
#                 self.ask_openai_for_resolution(log_line)

#     def report_issue(self, issue: str):
#         """Report detected issue to WebSocket clients."""
#         print(f"Detected Issue: {issue}")
#         send_issue_to_frontend(issue)

#     def report_resolution(self, error_line, steps):
#         """Send resolution steps to the frontend."""
#         resolution = f"Error: {error_line}\nResolution:\n"
#         for i, step in enumerate(steps, 1):
#             resolution += f"STEP {i}: {step}\n"
#         send_issue_to_frontend(resolution)

#     def ask_openai_for_resolution(self, log_line):
#         """Query OpenAI for a solution and send it back."""
#         print(f"Querying AI for solution to: {log_line}")
#         steps = query_openai_for_solution(log_line)
#         if steps:
#             self.report_resolution(log_line, steps)
#             append_to_knowledge_base(log_line, steps)

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



from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import re
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "vault.log")

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

