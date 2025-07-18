import os
import json
import requests
from flask import Flask, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import threading

# --- Configuration ---
app = Flask(__name__)
DATA_FILE = 'data.json'
# A lock to prevent race conditions when reading/writing the file
file_lock = threading.Lock()

# --- File Handling Functions ---
def read_data():
    """Safely reads data from the JSON file."""
    with file_lock:
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # If file is empty, corrupted, or not found, return empty list
            return []

def write_data(data):
    """Safely writes data to the JSON file."""
    with file_lock:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

# --- API Fetching and Storage Logic ---
def fetch_and_store_data():
    """
    Fetches data from the API and stores new results in the JSON file.
    """
    print("Scheduler: Fetching data from API...")
    api_url = "https://kbtpredictor.shop/API/1_min.php"
    
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        api_data = response.json()

        if isinstance(api_data, list) and api_data:
            stored_data = read_data()
            # Use a set for efficient checking of existing periods
            existing_periods = {str(item.get('period')) for item in stored_data}
            
            new_results_found = 0
            for item in api_data:
                period_id = str(item.get('period'))
                if period_id not in existing_periods:
                    stored_data.append(item)
                    existing_periods.add(period_id) # Add new period to our set
                    new_results_found += 1
            
            if new_results_found > 0:
                # Sort data by period descending before writing
                stored_data.sort(key=lambda x: str(x.get('period', '0')), reverse=True)
                write_data(stored_data)
                print(f"Scheduler: Successfully stored {new_results_found} new results.")
            else:
                print("Scheduler: No new results to store.")
        else:
            print("Scheduler: API response was not a valid list or was empty.")

    except Exception as e:
        print(f"Scheduler Error: An unexpected error occurred: {e}")

# --- Flask Routes ---
@app.route('/')
def index():
    """
    The main page. Fetches the last 100 results from our JSON file and displays them.
    """
    all_data = read_data()
    # Display the most recent 100 results
    results_to_display = all_data[:100]
    
    # Get current time in Indian Standard Time (IST)
    ist = pytz.timezone('Asia/Kolkata')
    last_updated = datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S %Z')
    
    return render_template('index.html', results=results_to_display, error=None, last_updated=last_updated)

# --- App Initialization ---
# Ensure the data file exists on startup
if not os.path.exists(DATA_FILE):
    write_data([])

# --- Background Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(fetch_and_store_data, 'interval', seconds=60)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=False)
