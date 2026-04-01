#!/usr/bin/env python3
"""
Zendesk Ticket Export & Gemini Analyzer - Web Interface

Features:
- Export tickets by date range and organization
- Download exported JSON files
- Upload existing ticket files
- Run Gemini analysis with data reduction options
- Interactive analysis results display
"""

import os
import json
import logging
import subprocess
import threading
import uuid
import glob
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.urandom(24)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Job tracking
export_jobs = {}
analysis_jobs = {}
jobs_lock = threading.Lock()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTER_SCRIPT = os.path.join(SCRIPT_DIR, 'zendesk_exporter.py')


def get_organizations_from_zendesk(credential_set=1):
    """Fetch organizations from Zendesk API."""
    import requests
    from requests.auth import HTTPBasicAuth

    if credential_set == 1:
        subdomain = os.getenv('ZENDESK_SUBDOMAIN')
        email = os.getenv('ZENDESK_EMAIL')
        token = os.getenv('ZENDESK_API_TOKEN')
    else:
        subdomain = os.getenv('ZENDESK_SUBDOMAIN_2')
        email = os.getenv('ZENDESK_EMAIL_2')
        token = os.getenv('ZENDESK_API_TOKEN_2')

    if not all([subdomain, email, token]):
        return []

    try:
        url = f"https://{subdomain}.zendesk.com/api/v2/organizations.json"
        response = requests.get(url, auth=HTTPBasicAuth(f"{email}/token", token), timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('organizations', [])
    except Exception as e:
        logger.error(f"Error fetching organizations from set {credential_set}: {e}")
        return []


def run_export_background(job_id, start_date, end_date, org_id, credential_sets, include_history=False):
    """
    Run export in background thread.

    Args:
        include_history: If False, skips fetching full audit/comment history for 5-10x speedup
    """
    try:
        with jobs_lock:
            export_jobs[job_id]['status'] = 'running'
            history_msg = ' (with full history)' if include_history else ' (fast mode)'
            export_jobs[job_id]['message'] = f'Exporting tickets{history_msg}...'

        cmd = [
            'python3', EXPORTER_SCRIPT,
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json',
            '--priorities', 'P1,P2,P3,P4'  # All priorities to skip interactive prompt
        ]

        if org_id:
            cmd.extend(['--organization-id', org_id])

        if credential_sets:
            cmd.extend(['--credential-set', str(credential_sets)])

        # Skip full history fetch for better performance (default)
        # Full history adds 0.1s + API calls per ticket
        if not include_history:
            cmd.append('--no-history')
            logger.info("Using fast export mode (no full history)")

        # Preserve environment variables explicitly
        env = os.environ.copy()

        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,  # Prevent hanging on input() calls
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1800,
            cwd=SCRIPT_DIR,
            env=env
        )

        if result.returncode == 0:
            # Find generated file - check both stdout and stderr (logging goes to stderr)
            output_file = None
            combined_output = result.stdout + '\n' + result.stderr

            for line in combined_output.split('\n'):
                if 'Using generated filename:' in line:
                    output_file = line.split('Using generated filename:')[1].strip()
                    logger.info(f"Found filename from output: {output_file}")
                    break
                elif 'Exported' in line and 'tickets to' in line:
                    # Fallback: parse from "Exported X tickets to filename.json"
                    parts = line.split('tickets to')
                    if len(parts) > 1:
                        output_file = parts[1].strip()
                        logger.info(f"Found filename from export message: {output_file}")
                        break

            if output_file and not os.path.isabs(output_file):
                output_file = os.path.join(SCRIPT_DIR, output_file)

            # If file not found, try to find most recent tickets_*.json file
            if not output_file or not os.path.exists(output_file):
                logger.warning(f"Parsed filename not found, searching for recent JSON files...")
                json_pattern = os.path.join(SCRIPT_DIR, 'tickets_*.json')
                json_files = glob.glob(json_pattern)

                # Find most recent file (created in last 60 seconds)
                recent_files = []
                current_time = time.time()
                for f in json_files:
                    if current_time - os.path.getmtime(f) < 60:
                        recent_files.append((f, os.path.getmtime(f)))

                if recent_files:
                    output_file = sorted(recent_files, key=lambda x: x[1], reverse=True)[0][0]
                    logger.info(f"Found recent file: {output_file}")

            if output_file and os.path.exists(output_file):
                # Get file metadata
                try:
                    file_size_bytes = os.path.getsize(output_file)
                    file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

                    # Count tickets
                    with open(output_file, 'r') as f:
                        data = json.load(f)

                    if isinstance(data, dict):
                        ticket_count = len(data.get('tickets', []))
                        metadata = data.get('export_metadata', {})
                        priority_breakdown = metadata.get('priority_breakdown', {})
                    else:
                        ticket_count = len(data) if isinstance(data, list) else 0
                        priority_breakdown = {}

                    message = f'Export completed: {ticket_count} tickets, {file_size_mb} MB'

                except Exception as e:
                    logger.warning(f"Could not read file metadata: {e}")
                    ticket_count = 0
                    file_size_mb = 0
                    priority_breakdown = {}
                    message = 'Export completed'

                with jobs_lock:
                    export_jobs[job_id]['status'] = 'completed'
                    export_jobs[job_id]['output_file'] = output_file
                    export_jobs[job_id]['filename'] = os.path.basename(output_file)
                    export_jobs[job_id]['ticket_count'] = ticket_count
                    export_jobs[job_id]['file_size_mb'] = file_size_mb
                    export_jobs[job_id]['priority_breakdown'] = priority_breakdown
                    export_jobs[job_id]['message'] = message
                logger.info(f"Export successful: {output_file} - {ticket_count} tickets, {file_size_mb} MB")
            else:
                # Log the output for debugging
                logger.error(f"Could not find output file. Parsed filename: {output_file}")
                logger.error(f"Stdout: {result.stdout[:500]}")
                logger.error(f"Stderr: {result.stderr[:500]}")
                with jobs_lock:
                    export_jobs[job_id]['status'] = 'failed'
                    export_jobs[job_id]['message'] = 'Export completed but file not found'
        else:
            with jobs_lock:
                export_jobs[job_id]['status'] = 'failed'
                export_jobs[job_id]['message'] = result.stderr or 'Export failed'

    except Exception as e:
        logger.error(f"Export error: {e}")
        with jobs_lock:
            export_jobs[job_id]['status'] = 'failed'
            export_jobs[job_id]['message'] = str(e)


def run_analysis_background(job_id, filepath, user_prompt, reduction_option, reduction_value):
    """Run Gemini analysis in background."""
    try:
        with jobs_lock:
            analysis_jobs[job_id]['status'] = 'running'
            analysis_jobs[job_id]['message'] = 'Loading data...'

        # Load data
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Apply data reduction
        with jobs_lock:
            analysis_jobs[job_id]['message'] = 'Reducing data...'

        processed_data = apply_data_reduction(data, reduction_option, reduction_value)

        # Run Gemini analysis
        with jobs_lock:
            analysis_jobs[job_id]['message'] = 'Analyzing with Gemini...'

        analysis_result = analyze_with_gemini(processed_data, user_prompt)

        with jobs_lock:
            analysis_jobs[job_id]['status'] = 'completed'
            analysis_jobs[job_id]['result'] = analysis_result
            analysis_jobs[job_id]['message'] = 'Analysis complete'

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        with jobs_lock:
            analysis_jobs[job_id]['status'] = 'failed'
            analysis_jobs[job_id]['message'] = str(e)


def apply_data_reduction(data, option, value):
    """Apply data reduction based on option."""
    if option == 'full':
        return data

    tickets = data.get('tickets', []) if isinstance(data, dict) else data
    metadata = data.get('export_metadata', {}) if isinstance(data, dict) else {}

    if option == 'key_fields':
        reduced = []
        for t in tickets:
            reduced.append({
                'id': t.get('id'),
                'subject': t.get('subject'),
                'status': t.get('status'),
                'priority': t.get('priority'),
                'created_at': t.get('created_at'),
                'organization_name': t.get('organization_name'),
                'comment_count': len(t.get('comments', []))
            })
        return {'export_metadata': metadata, 'tickets': reduced}

    elif option == 'priority':
        filtered = [t for t in tickets if t.get('priority', '').upper() == value.upper()]
        return {'export_metadata': metadata, 'tickets': filtered}

    elif option == 'status':
        filtered = [t for t in tickets if t.get('status', '').lower() == value.lower()]
        return {'export_metadata': metadata, 'tickets': filtered}

    elif option == 'limit':
        limited = tickets[:int(value)]
        return {'export_metadata': metadata, 'tickets': limited}

    return data


def analyze_with_gemini(data, user_prompt):
    """Call Gemini API for analysis."""
    try:
        import google.genai as genai
    except ImportError:
        return "Error: google-genai not installed"

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return "Error: GOOGLE_API_KEY not set"

    full_prompt = f"""You are analyzing Zendesk support tickets.

TICKETS DATA:
{json.dumps(data, indent=2)}

USER REQUEST:
{user_prompt}

Please provide a clear, well-formatted analysis addressing the user's request."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"Error calling Gemini: {str(e)}"


@app.route('/')
def index():
    return render_template('ticket_export_analyzer.html')


@app.route('/api/organizations', methods=['GET'])
def get_organizations():
    """Get organizations from both credential sets."""
    cred_set = request.args.get('credential_set', '1')
    orgs = get_organizations_from_zendesk(int(cred_set))
    return jsonify({'organizations': [{'id': o['id'], 'name': o['name']} for o in orgs]})


@app.route('/api/export', methods=['POST'])
def start_export():
    """Start ticket export job."""
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    org_id = data.get('organization_id')
    cred_sets = data.get('credential_sets', 1)
    include_history = data.get('include_history', False)  # Default to fast mode

    if not start_date or not end_date:
        return jsonify({'error': 'Dates required'}), 400

    job_id = str(uuid.uuid4())
    with jobs_lock:
        export_jobs[job_id] = {
            'status': 'starting',
            'message': 'Starting export...',
            'output_file': None
        }

    thread = threading.Thread(
        target=run_export_background,
        args=(job_id, start_date, end_date, org_id, cred_sets, include_history)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/export/status/<job_id>')
def export_status(job_id):
    """Check export job status."""
    with jobs_lock:
        job = export_jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job)


@app.route('/api/download/<job_id>')
def download_export(job_id):
    """Download exported file."""
    with jobs_lock:
        job = export_jobs.get(job_id)

    if not job or job['status'] != 'completed':
        return jsonify({'error': 'File not ready'}), 400

    return send_file(job['output_file'], as_attachment=True)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400

    file = request.files['file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'JSON only'}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Get file info
    with open(filepath, 'r') as f:
        data = json.load(f)

    tickets = data.get('tickets', []) if isinstance(data, dict) else data
    size_mb = os.path.getsize(filepath) / (1024 * 1024)

    return jsonify({
        'filename': filename,
        'filepath': filepath,
        'ticket_count': len(tickets),
        'size_mb': round(size_mb, 2)
    })


@app.route('/api/analyze', methods=['POST'])
def start_analysis():
    """Start analysis job."""
    data = request.get_json()
    filepath = data.get('filepath')
    prompt = data.get('prompt')
    reduction_option = data.get('reduction_option', 'full')
    reduction_value = data.get('reduction_value')

    if not filepath or not prompt:
        return jsonify({'error': 'Filepath and prompt required'}), 400

    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 400

    job_id = str(uuid.uuid4())
    with jobs_lock:
        analysis_jobs[job_id] = {
            'status': 'starting',
            'message': 'Starting analysis...',
            'result': None
        }

    thread = threading.Thread(target=run_analysis_background, args=(job_id, filepath, prompt, reduction_option, reduction_value))
    thread.daemon = True
    thread.start()

    return jsonify({'job_id': job_id})


@app.route('/api/analyze/status/<job_id>')
def analysis_status(job_id):
    """Check analysis job status."""
    with jobs_lock:
        job = analysis_jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    return jsonify(job)


if __name__ == '__main__':
    print("\nZendesk Ticket Export & Analyzer")
    print("Open http://localhost:5000\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
