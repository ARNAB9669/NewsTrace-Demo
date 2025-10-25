#!/usr/bin/env python3
"""
Backend Flask server for NewsTrace prototype.

Usage:
    cd "<project-root>/Backend"
    python3 app.py

Behavior:
- Serves frontend static files from the project root (one level up from Backend/).
- POST /api/scrape accepts JSON { "outlet": "<name or url>" }.
- It runs Backend/scrapper.py (if present) with the outlet argument.
- Reads data.json (in project root) written by scrapper.py and returns it as JSON.
- If scrapper.py fails or data.json is missing, returns an empty list.
"""

import os
import subprocess
import json
import shlex
from flask import Flask, send_from_directory, jsonify, request, make_response

# Paths
THIS_DIR = os.path.dirname(os.path.abspath(__file__))          # .../Backend
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..'))   # project root where index.html lives
DATA_FILE = os.path.join(PROJECT_ROOT, 'data.json')
SCRAPPER_PY = os.path.join(THIS_DIR, 'scrapper.py')
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

def json_response(obj, status=200):
    resp = make_response(jsonify(obj), status)
    resp.headers['Content-Type'] = 'application/json'
    # Allow local dev from file:// or different ports
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/')
def index():
    # serve index.html from project root
    return send_from_directory(PROJECT_ROOT, 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    # serve static files (style.css, script.js, etc.) from the static folder in project root
    return send_from_directory(STATIC_DIR, filename)

@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    """
    Expects JSON body: { "outlet": "The Hindu" } or { "outlet": "https://example.com" }
    Tries to execute scrapper.py (which should write ../data.json), then returns contents of data.json.
    """
    body = request.get_json(silent=True) or {}
    outlet = body.get('outlet', '').strip()

    # If scrapper.py exists attempt to run it (it should write ../data.json)
    if os.path.exists(SCRAPPER_PY):
        try:
            # Run scrapper.py with the outlet as argument.
            # Use shlex.split to avoid shell quoting issues.
            cmd = ['python3', SCRAPPER_PY, outlet]
            # subprocess.run will wait; keep a modest timeout to avoid blocking too long
            subprocess.run(cmd, cwd=THIS_DIR, timeout=45, check=False)
        except subprocess.TimeoutExpired:
            print("scrapper.py timed out")
        except Exception as e:
            # don't crash the API - just log and continue to read any existing data file
            print("Error invoking scrapper.py:", e)

    # Read produced data.json (if present)
    data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # ensure we return a list
                if isinstance(loaded, list):
                    data = loaded
                else:
                    # if file contains an object with a key like 'profiles', try that
                    if isinstance(loaded, dict) and 'profiles' in loaded and isinstance(loaded['profiles'], list):
                        data = loaded['profiles']
        except Exception as e:
            print("Failed to read/parse data.json:", e)
            data = []

    return json_response(data)

@app.route('/health')
def health():
    return json_response({"status":"ok","backend":"flask","project_root":PROJECT_ROOT})

if __name__ == '__main__':
    # Run dev server for prototype. Bind to 127.0.0.1 to avoid exposing publicly by default.
    print("Starting NewsTrace backend at http://127.0.0.1:5000 (project root: {})".format(PROJECT_ROOT))
    app.run(host='127.0.0.1', port=5000, debug=True)