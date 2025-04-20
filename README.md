# log-watcher


# Vault Log Viewer with Real-time Issue Detection

This project is a web application that allows users to view live logs from Vault, detect issues in real-time, and display suggested resolutions. The application uses **FastAPI** for the backend and **WebSocket** for real-time communication between the frontend and backend.

## Features

- **Live Log Viewing**: View live logs from the Vault application.
- **Real-time Issue Detection**: Detect issues in the logs (e.g., Vault sealed, token revoked) and display them in real-time.
- **Suggested Resolutions**: Automatically suggest resolutions for detected issues.
- **Auto Refresh**: Auto-refresh the logs every second with an option to pause/resume auto-refresh.

## Technologies Used

- **Backend**: Python with FastAPI
- **Frontend**: HTML, JavaScript
- **Real-time Communication**: WebSocket
- **Logging**: Vault logs stored in `vault.log`
- **Virtual Environment**: `venv` for managing Python dependencies

## Prerequisites

Before running the application, make sure you have the following installed:

- Python 3.7 or higher
- `pip` (Python package manager)
- `virtualenv` (optional, but recommended for creating a virtual environment)

## Project Structure

```
.
├── backend
│   ├── __pycache__
│   ├── main.py           # FastAPI backend logic
│   ├── requirements.txt  # Python dependencies
│   └── venv              # Python virtual environment
├── frontend
│   └── index.html        # Frontend HTML file
├── run.sh                # Shell script to start the app
└── vault.log             # Vault log file
```

## Installation

1. Clone the repository:

   ```bash
   git clone <repository_url>
   cd <project_directory>
   ```

2. Set up a virtual environment:

   ```bash
   python3 -m venv backend/venv
   ```

3. Activate the virtual environment:

   - On Linux/macOS:

     ```bash
     source backend/venv/bin/activate
     ```

   - On Windows:

     ```bash
     backendenv\Scriptsctivate
     ```

4. Install the required Python dependencies:

   ```bash
   pip install -r backend/requirements.txt
   ```

## Running the Application

1. **Start the FastAPI backend server**:

   You can start the FastAPI server using the following command:

   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

   This will start the FastAPI server on `http://localhost:8000`.

2. **Serve the frontend**:

   You can open the `frontend/index.html` file directly in your web browser. The frontend will automatically start fetching logs and display real-time detected issues and suggested resolutions.

3. **(Optional) Run the application via `run.sh`**:

   If you have a Unix-based system, you can also run the application using the provided shell script:

   ```bash
   ./run.sh
   ```

   This script will start both the backend and the frontend (if applicable).

## Usage

1. **Live Logs**: 
   - The "Live Vault Logs" section shows the most recent logs from the Vault system, updating in real-time.
   
2. **Detected Issues**:
   - The "Detected Issues" section lists issues detected in the logs (e.g., `Vault is sealed`, `Token was revoked`).
   
3. **Suggested Resolutions**:
   - For each issue detected, suggested resolutions are displayed in the "Suggested Resolutions" section.

4. **Auto Refresh**:
   - By default, the logs are auto-refreshed every second.
   - You can pause/resume auto-refresh by clicking the "Pause Auto Refresh" button.

5. **Manual Log Refresh**:
   - You can manually refresh the logs by clicking the "Refresh Logs" button.

## WebSocket Connection

- The frontend connects to the backend via a WebSocket to receive real-time issues detected in the logs.
- WebSocket URL: `ws://localhost:8000/ws/issues`

## Error Detection Logic

- The application looks for common Vault issues in the logs, including:
  - **Vault is sealed**
  - **Token was revoked**
  - **New token generated**
  - **Connection errors**
  - **Permission errors**

- The frontend will display the issues and automatically suggest resolutions based on the detected error.

## Troubleshooting

- **Logs not updating**: Ensure that the backend server is running and that the frontend is connected to the correct WebSocket URL (`ws://localhost:8000/ws/issues`).
- **WebSocket connection errors**: Check for firewall or network issues that may be preventing the WebSocket connection.
- **No issues detected**: If no issues are being detected, make sure that `vault.log` contains errors or issues related to Vault's operations.

## Contributing

Feel free to fork the repository and submit pull requests with improvements or bug fixes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

