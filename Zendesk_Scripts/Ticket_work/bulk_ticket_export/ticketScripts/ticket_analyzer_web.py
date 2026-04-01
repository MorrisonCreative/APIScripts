"""
Zendesk Ticket Analyzer Web Interface

A web-based interface for analyzing Zendesk tickets with AI-powered summaries.
Users can select export parameters, upload ticket JSON files, and get summaries
from Google Gemini for each ticket.

Requirements:
    pip install flask google-generativeai python-dotenv

Environment Variables:
    GEMINI_API_KEY - Google Gemini API key for AI summaries
"""

import os
import json
import logging
import subprocess
import time
import threading
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.urandom(24)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    logging.warning("GEMINI_API_KEY not set. AI summaries will not be available.")
    model = None

# Job tracking for async exports
export_jobs = {}
export_jobs_lock = threading.Lock()


def format_ticket_for_summary(ticket):
    """
    Format ticket data into a readable text for AI summarization.

    Args:
        ticket (dict): Ticket dictionary from Zendesk

    Returns:
        str: Formatted ticket text
    """
    text_parts = [
        f"Ticket ID: {ticket.get('id')}",
        f"Subject: {ticket.get('subject', 'N/A')}",
        f"Status: {ticket.get('status', 'N/A')}",
        f"Priority: {ticket.get('priority', 'N/A')}",
        f"Created: {ticket.get('created_at', 'N/A')}",
        f"Updated: {ticket.get('updated_at', 'N/A')}",
        f"\nDescription:\n{ticket.get('description', 'N/A')}",
    ]

    # Add custom priority if available
    custom_fields = ticket.get('custom_fields', [])
    for field in custom_fields:
        if field.get('id') == 360047533253:  # Ticket Priority field
            text_parts.append(f"Ticket Priority: {field.get('value', 'N/A')}")
            break

    # Add tags
    tags = ticket.get('tags', [])
    if tags:
        text_parts.append(f"Tags: {', '.join(tags)}")

    # Add comments if available
    comments = ticket.get('comments', [])
    if comments and len(comments) > 0:
        text_parts.append(f"\nComments ({len(comments)} total):")
        # Include first few comments for context
        for i, comment in enumerate(comments[:3]):
            author_id = comment.get('author_id', 'Unknown')
            body = comment.get('body', '')
            text_parts.append(f"\nComment {i+1} (Author {author_id}):\n{body[:500]}")

    return "\n".join(text_parts)


def generate_ticket_summary(ticket):
    """
    Generate AI summary for a ticket using Gemini.

    Args:
        ticket (dict): Ticket dictionary from Zendesk

    Returns:
        str: AI-generated summary or error message
    """
    if not model:
        return "AI summaries not available (GEMINI_API_KEY not set)"

    try:
        ticket_text = format_ticket_for_summary(ticket)

        prompt = f"""Analyze this Zendesk support ticket and provide a concise summary (2-3 sentences) covering:
1. The main issue or request
2. Current status and any resolution
3. Key action items or next steps

Ticket Information:
{ticket_text}

Summary:"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        logging.error(f"Error generating summary for ticket {ticket.get('id')}: {e}")
        return f"Error generating summary: {str(e)}"


def parse_ticket_file(file_path):
    """
    Parse ticket JSON file and extract metadata and tickets.

    Args:
        file_path (str): Path to JSON file

    Returns:
        tuple: (metadata dict, tickets list)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Check if this is the new format with metadata
    if isinstance(data, dict) and 'export_metadata' in data:
        return data.get('export_metadata', {}), data.get('tickets', [])
    else:
        # Legacy format - just tickets array
        return {}, data if isinstance(data, list) else []


def extract_ticket_priority(ticket):
    """
    Extract ticket priority from custom fields.

    Args:
        ticket (dict): Ticket dictionary

    Returns:
        str: Priority value (P1, P2, P3, P4) or 'N/A'
    """
    custom_fields = ticket.get('custom_fields', [])
    for field in custom_fields:
        if field.get('id') == 360047533253:
            value = field.get('value', '')
            return value.upper() if value else 'N/A'
    return 'N/A'


def detect_credential_sets():
    """
    Detect which Zendesk credential sets are available.

    Returns:
        dict: Information about available credential sets
    """
    set1 = {
        'subdomain': os.getenv('ZENDESK_SUBDOMAIN'),
        'email': os.getenv('ZENDESK_EMAIL'),
        'api_token': os.getenv('ZENDESK_API_TOKEN')
    }

    set2 = {
        'subdomain': os.getenv('ZENDESK_SUBDOMAIN_2'),
        'email': os.getenv('ZENDESK_EMAIL_2'),
        'api_token': os.getenv('ZENDESK_API_TOKEN_2')
    }

    set1_complete = all(set1.values())
    set2_complete = all(set2.values())

    return {
        'set1': {
            'available': set1_complete,
            'subdomain': set1['subdomain'] if set1_complete else None,
            'email': set1['email'] if set1_complete else None
        },
        'set2': {
            'available': set2_complete,
            'subdomain': set2['subdomain'] if set2_complete else None,
            'email': set2['email'] if set2_complete else None
        }
    }


def run_export_in_background(job_id, start_date, end_date, organization_id=None, priorities=None, credential_set=None, include_history=False):
    """
    Run export in background thread and update job status.

    Args:
        job_id (str): Unique job identifier
        start_date (str): Start date YYYY-MM-DD
        end_date (str): End date YYYY-MM-DD
        organization_id (str, optional): Organization ID
        priorities (list, optional): List of priorities
        credential_set (int, optional): Credential set to use
        include_history (bool, optional): Include full audit/comment history
    """
    try:
        logging.info(f"Background export started for job {job_id}")

        # Update status to running
        with export_jobs_lock:
            export_jobs[job_id]['status'] = 'running'
            export_jobs[job_id]['message'] = 'Export in progress...'

        # Run the export
        success, message, output_file = run_zendesk_export(
            start_date, end_date, organization_id, priorities, credential_set, include_history
        )

        # Update job status
        with export_jobs_lock:
            if success:
                export_jobs[job_id]['status'] = 'completed'
                export_jobs[job_id]['message'] = message
                export_jobs[job_id]['output_file'] = output_file
            else:
                export_jobs[job_id]['status'] = 'failed'
                export_jobs[job_id]['message'] = message

        logging.info(f"Background export completed for job {job_id}: {success}")

    except Exception as e:
        logging.error(f"Background export error for job {job_id}: {e}", exc_info=True)
        with export_jobs_lock:
            export_jobs[job_id]['status'] = 'failed'
            export_jobs[job_id]['message'] = f'Unexpected error: {str(e)}'


def run_zendesk_export(start_date, end_date, organization_id=None, priorities=None, credential_set=None, include_history=False):
    """
    Run the zendesk_exporter.py script to generate a ticket export.

    Args:
        start_date (str): Start date YYYY-MM-DD
        end_date (str): End date YYYY-MM-DD
        organization_id (str, optional): Organization ID
        priorities (list, optional): List of priorities (e.g., ['P1', 'P2'])
        credential_set (int, optional): Which credential set to use (1 or 2)
        include_history (bool, optional): Include full audit/comment history (default: False for speed)

    Returns:
        tuple: (success, result_message, output_file)
    """
    try:
        # Get absolute path to zendesk_exporter.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        exporter_path = os.path.join(script_dir, 'zendesk_exporter.py')

        if not os.path.exists(exporter_path):
            return False, f"zendesk_exporter.py not found at {exporter_path}", None

        # Build command
        cmd = [
            'python3',
            exporter_path,
            '--start-date', start_date,
            '--end-date', end_date,
            '--format', 'json'
        ]

        if organization_id:
            cmd.extend(['--organization-id', str(organization_id)])

        if priorities:
            cmd.extend(['--priorities', ','.join(priorities)])

        if credential_set:
            cmd.extend(['--credential-set', str(credential_set)])

        # Skip full history by default for speed (can be 2 API calls per ticket!)
        if not include_history:
            cmd.append('--no-history')
            logging.info("Skipping full history fetch for faster export")

        # Run the export with increased timeout and in the script directory
        logging.info(f"Running export command: {' '.join(cmd)}")
        logging.info(f"Working directory: {script_dir}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout (increased from 10)
            cwd=script_dir  # Run in the script directory
        )

        logging.info(f"Export process completed with return code: {result.returncode}")

        if result.returncode == 0:
            # Log stdout for debugging
            logging.info(f"Export stdout: {result.stdout[:500]}...")

            # Parse output to find generated filename
            output_lines = result.stdout.split('\n')
            generated_file = None

            for line in output_lines:
                if 'Using generated filename:' in line:
                    generated_file = line.split('Using generated filename:')[1].strip()
                    logging.info(f"Found generated filename from log: {generated_file}")
                elif 'Exported' in line and 'tickets to' in line:
                    parts = line.split('tickets to')
                    if len(parts) > 1:
                        generated_file = parts[1].strip()
                        logging.info(f"Found filename from export message: {generated_file}")

            # If we found a filename, check if it's absolute or relative
            if generated_file:
                if not os.path.isabs(generated_file):
                    # Make it absolute relative to script directory
                    generated_file = os.path.join(script_dir, generated_file)

                if os.path.exists(generated_file):
                    logging.info(f"Found export file at: {generated_file}")
                    return True, "Export completed successfully", generated_file
                else:
                    logging.warning(f"Generated file not found at: {generated_file}")

            # Try to find any .json file created recently in the script directory
            logging.info("Searching for recently created JSON files...")
            json_files = []
            for file in os.listdir(script_dir):
                if file.endswith('.json') and file.startswith('tickets_'):
                    filepath = os.path.join(script_dir, file)
                    # Check if file was created in the last 60 seconds
                    if time.time() - os.path.getmtime(filepath) < 60:
                        json_files.append((filepath, os.path.getmtime(filepath)))

            if json_files:
                # Get the most recently created file
                most_recent = sorted(json_files, key=lambda x: x[1], reverse=True)[0][0]
                logging.info(f"Found recent export file: {most_recent}")
                return True, "Export completed successfully", most_recent

            # Log output for debugging
            logging.error(f"Could not find output file. Full stdout:\n{result.stdout}")
            return False, f"Export completed but could not find output file. Check logs.", None
        else:
            error_msg = result.stderr or result.stdout
            logging.error(f"Export failed with stderr: {result.stderr}")
            logging.error(f"Export failed with stdout: {result.stdout}")
            return False, f"Export failed: {error_msg}", None

    except subprocess.TimeoutExpired:
        logging.error("Export timed out after 30 minutes")
        return False, "Export timed out (> 30 minutes). Try a smaller date range or fewer tickets.", None
    except Exception as e:
        logging.error(f"Error running export: {e}", exc_info=True)
        return False, f"Error running export: {str(e)}", None


@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html')


@app.route('/api/credentials', methods=['GET'])
def get_credentials():
    """
    Get available Zendesk credential sets.

    Returns:
        JSON response with credential set information
    """
    try:
        creds = detect_credential_sets()
        return jsonify({
            'success': True,
            'credentials': creds
        })
    except Exception as e:
        logging.error(f"Error checking credentials: {e}")
        return jsonify({'error': f'Error checking credentials: {str(e)}'}), 500


@app.route('/api/export', methods=['POST'])
def create_export():
    """
    Start an asynchronous export job.

    Returns:
        JSON response with job_id for polling status
    """
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        organization_id = data.get('organization_id')
        priorities = data.get('priorities', [])
        credential_set = data.get('credential_set')
        include_history = data.get('include_history', False)  # Default to False for speed

        logging.info(f"Export request received: {start_date} to {end_date}, org={organization_id}, priorities={priorities}, history={include_history}")

        # Validate required fields
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400

        # Check credentials before running export
        creds = detect_credential_sets()
        if not creds['set1']['available'] and not creds['set2']['available']:
            return jsonify({'error': 'No Zendesk credentials configured. Please set environment variables.'}), 400

        # Create job
        job_id = str(uuid.uuid4())
        with export_jobs_lock:
            export_jobs[job_id] = {
                'status': 'starting',
                'message': 'Initializing export...',
                'output_file': None,
                'created_at': datetime.now().isoformat()
            }

        # Start export in background thread
        thread = threading.Thread(
            target=run_export_in_background,
            args=(job_id, start_date, end_date, organization_id, priorities, credential_set, include_history)
        )
        thread.daemon = True
        thread.start()

        logging.info(f"Started background export job {job_id}")

        return jsonify({
            'success': True,
            'job_id': job_id,
            'message': 'Export started in background. Use job_id to check status.'
        })

    except Exception as e:
        logging.error(f"Error creating export: {e}", exc_info=True)
        return jsonify({'error': f'Error creating export: {str(e)}'}), 500


@app.route('/api/export/status/<job_id>', methods=['GET'])
def get_export_status(job_id):
    """
    Check the status of an export job.

    Args:
        job_id (str): Job identifier

    Returns:
        JSON response with job status
    """
    with export_jobs_lock:
        job = export_jobs.get(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    response = {
        'job_id': job_id,
        'status': job['status'],
        'message': job['message']
    }

    # If completed, parse and return ticket data
    if job['status'] == 'completed' and job.get('output_file'):
        try:
            output_file = job['output_file']
            metadata, tickets = parse_ticket_file(output_file)

            # Extract basic ticket info
            ticket_list = []
            for ticket in tickets:
                ticket_list.append({
                    'id': ticket.get('id'),
                    'subject': ticket.get('subject', 'N/A'),
                    'status': ticket.get('status', 'N/A'),
                    'priority': ticket.get('priority', 'N/A'),
                    'ticket_priority': extract_ticket_priority(ticket),
                    'created_at': ticket.get('created_at', 'N/A'),
                    'updated_at': ticket.get('updated_at', 'N/A'),
                    'organization_id': ticket.get('organization_id'),
                })

            response['filename'] = os.path.basename(output_file)
            response['filepath'] = output_file
            response['metadata'] = metadata
            response['tickets'] = ticket_list
            response['total_tickets'] = len(tickets)

        except Exception as e:
            logging.error(f"Error parsing completed export: {e}")
            response['error'] = f'Export completed but failed to parse results: {str(e)}'

    return jsonify(response)


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Handle file upload and parse ticket data.

    Returns:
        JSON response with metadata and ticket list
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith('.json'):
        return jsonify({'error': 'Only JSON files are supported'}), 400

    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Parse ticket data
        metadata, tickets = parse_ticket_file(filepath)

        # Extract basic ticket info for display
        ticket_list = []
        for ticket in tickets:
            ticket_list.append({
                'id': ticket.get('id'),
                'subject': ticket.get('subject', 'N/A'),
                'status': ticket.get('status', 'N/A'),
                'priority': ticket.get('priority', 'N/A'),
                'ticket_priority': extract_ticket_priority(ticket),
                'created_at': ticket.get('created_at', 'N/A'),
                'updated_at': ticket.get('updated_at', 'N/A'),
                'organization_id': ticket.get('organization_id'),
            })

        # Store filepath in session for later use
        response_data = {
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'metadata': metadata,
            'tickets': ticket_list,
            'total_tickets': len(tickets)
        }

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error processing upload: {e}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500


@app.route('/api/summarize/<int:ticket_id>', methods=['POST'])
def summarize_ticket(ticket_id):
    """
    Generate AI summary for a specific ticket.

    Args:
        ticket_id (int): Zendesk ticket ID

    Returns:
        JSON response with summary
    """
    try:
        # Get filepath from request
        data = request.get_json()
        filepath = data.get('filepath')

        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'Invalid file path'}), 400

        # Load ticket data
        metadata, tickets = parse_ticket_file(filepath)

        # Find the specific ticket
        ticket = None
        for t in tickets:
            if t.get('id') == ticket_id:
                ticket = t
                break

        if not ticket:
            return jsonify({'error': f'Ticket {ticket_id} not found'}), 404

        # Generate summary
        summary = generate_ticket_summary(ticket)

        return jsonify({
            'success': True,
            'ticket_id': ticket_id,
            'summary': summary
        })

    except Exception as e:
        logging.error(f"Error summarizing ticket {ticket_id}: {e}")
        return jsonify({'error': f'Error generating summary: {str(e)}'}), 500


@app.route('/api/summarize_all', methods=['POST'])
def summarize_all_tickets():
    """
    Generate AI summaries for all tickets in the file.

    Returns:
        JSON response with summaries for all tickets
    """
    try:
        # Get filepath from request
        data = request.get_json()
        filepath = data.get('filepath')

        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'Invalid file path'}), 400

        # Load ticket data
        metadata, tickets = parse_ticket_file(filepath)

        # Generate summaries for all tickets
        summaries = {}
        for i, ticket in enumerate(tickets):
            ticket_id = ticket.get('id')
            logging.info(f"Generating summary for ticket {i+1}/{len(tickets)}: {ticket_id}")
            summaries[ticket_id] = generate_ticket_summary(ticket)

        return jsonify({
            'success': True,
            'summaries': summaries,
            'total': len(summaries)
        })

    except Exception as e:
        logging.error(f"Error summarizing all tickets: {e}")
        return jsonify({'error': f'Error generating summaries: {str(e)}'}), 500


@app.route('/api/export_summary', methods=['POST'])
def export_summary():
    """
    Export ticket summaries to JSON file.

    Returns:
        JSON file download
    """
    try:
        data = request.get_json()
        filepath = data.get('filepath')
        summaries = data.get('summaries', {})

        if not filepath or not os.path.exists(filepath):
            return jsonify({'error': 'Invalid file path'}), 400

        # Load ticket data
        metadata, tickets = parse_ticket_file(filepath)

        # Create export data with summaries
        export_data = {
            'export_date': datetime.now().isoformat(),
            'source_file': os.path.basename(filepath),
            'metadata': metadata,
            'tickets_with_summaries': []
        }

        for ticket in tickets:
            ticket_id = str(ticket.get('id'))
            export_data['tickets_with_summaries'].append({
                'id': ticket.get('id'),
                'subject': ticket.get('subject'),
                'status': ticket.get('status'),
                'priority': ticket.get('priority'),
                'ticket_priority': extract_ticket_priority(ticket),
                'created_at': ticket.get('created_at'),
                'updated_at': ticket.get('updated_at'),
                'url': ticket.get('url'),
                'ai_summary': summaries.get(ticket_id, 'Not generated'),
                'full_ticket': ticket
            })

        # Save export file
        export_filename = f"ticket_summaries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        export_path = os.path.join(app.config['UPLOAD_FOLDER'], export_filename)

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=4, ensure_ascii=False)

        return send_file(export_path, as_attachment=True, download_name=export_filename)

    except Exception as e:
        logging.error(f"Error exporting summary: {e}")
        return jsonify({'error': f'Error exporting summary: {str(e)}'}), 500


if __name__ == '__main__':
    # Check for Gemini API key
    if not GEMINI_API_KEY:
        print("\nWARNING: GEMINI_API_KEY environment variable not set!")
        print("AI summaries will not be available.")
        print("Set your Gemini API key: export GEMINI_API_KEY='your-key-here'\n")

    # Run Flask app
    print("\nStarting Zendesk Ticket Analyzer Web Interface...")
    print("Open http://localhost:5000 in your browser\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
