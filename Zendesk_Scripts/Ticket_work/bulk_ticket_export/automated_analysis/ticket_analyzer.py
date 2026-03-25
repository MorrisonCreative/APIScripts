#!/usr/bin/env python3
"""
Automated Zendesk Ticket Analysis and Email Reporting

Exports tickets from last 7 days using BOTH credential sets, analyzes with
Gemini AI, and emails results.

Usage:
    python3 ticket_analyzer.py [--dry-run] [--priorities P1]
    python3 ticket_analyzer.py [--dry-run] [--priorities P1,P2]

Environment Variables Required:
    - ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN (credential set 1)
    - ZENDESK_SUBDOMAIN_2, ZENDESK_EMAIL_2, ZENDESK_API_TOKEN_2 (credential set 2)
    - GOOGLE_API_KEY (for Gemini AI)
    - EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO (for Gmail SMTP)
"""

import subprocess
import json
import os
import sys
import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Auto-detect script directory (works on any machine)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXPORTER_SCRIPT = os.path.join(SCRIPT_DIR, "zendesk_exporter.py")
OUTPUT_FILE_SET1 = os.path.join(SCRIPT_DIR, "exported_tickets_set1.json")
OUTPUT_FILE_SET2 = os.path.join(SCRIPT_DIR, "exported_tickets_set2.json")
OUTPUT_FILE_COMBINED = os.path.join(SCRIPT_DIR, "exported_tickets.json")


def calculate_date_range():
    """Calculate date range for last 7 days."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def run_export(start_date, end_date, priorities=None, credential_set=1):
    """
    Execute zendesk_exporter.py with proper arguments.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        priorities (str): Comma-separated priorities (e.g., "P1" or "P1,P2")
        credential_set (int): Which credential set to use (1 or 2)

    Returns:
        str: Path to exported JSON file

    Raises:
        RuntimeError: If export fails
    """
    output_file = OUTPUT_FILE_SET1 if credential_set == 1 else OUTPUT_FILE_SET2

    logger.info(f"Running ticket export for credential set {credential_set}")
    logger.info(f"Date range: {start_date} to {end_date}")
    if priorities:
        logger.info(f"Filtering for priorities: {priorities}")

    cmd = [
        "python3",
        EXPORTER_SCRIPT,
        "--start-date", start_date,
        "--end-date", end_date,
        "--format", "json",
        "--output", output_file,
        "--credential-set", str(credential_set)
    ]

    # Add priorities filter if specified
    if priorities:
        cmd.extend(["--priorities", priorities])

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR
        )
        logger.info(f"Export completed successfully for credential set {credential_set}")
        logger.debug(result.stdout)
        return output_file
    except subprocess.CalledProcessError as e:
        logger.error(f"Export failed for credential set {credential_set}: {e.stderr}")
        raise RuntimeError(f"Failed to export tickets for credential set {credential_set}: {e.stderr}")


def load_ticket_data(json_path):
    """
    Load and parse the exported ticket JSON file.

    Args:
        json_path (str): Path to JSON file

    Returns:
        dict: Parsed JSON data
    """
    logger.info(f"Loading ticket data from {json_path}")

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        ticket_count = data.get('export_metadata', {}).get('total_tickets', 0)
        logger.info(f"Loaded {ticket_count} tickets")
        return data
    except Exception as e:
        logger.error(f"Failed to load ticket data: {e}")
        raise


def merge_ticket_data(data_set1, data_set2):
    """
    Merge ticket data from two credential sets.

    Args:
        data_set1 (dict): Ticket data from credential set 1
        data_set2 (dict): Ticket data from credential set 2

    Returns:
        dict: Combined ticket data
    """
    logger.info("Merging ticket data from both credential sets")

    # Combine tickets from both sets
    tickets_set1 = data_set1.get('tickets', [])
    tickets_set2 = data_set2.get('tickets', [])
    all_tickets = tickets_set1 + tickets_set2

    # Get metadata from set 1 as base
    metadata = data_set1.get('export_metadata', {}).copy()

    # Update metadata with combined information
    metadata['total_tickets'] = len(all_tickets)
    metadata['credential_sets'] = [1, 2]
    metadata['set1_tickets'] = len(tickets_set1)
    metadata['set2_tickets'] = len(tickets_set2)

    # Merge priority breakdowns if available
    if 'priority_breakdown' in data_set1.get('export_metadata', {}) and \
       'priority_breakdown' in data_set2.get('export_metadata', {}):
        breakdown1 = data_set1['export_metadata']['priority_breakdown']
        breakdown2 = data_set2['export_metadata']['priority_breakdown']
        combined_breakdown = {}
        for key in set(breakdown1.keys()) | set(breakdown2.keys()):
            combined_breakdown[key] = breakdown1.get(key, 0) + breakdown2.get(key, 0)
        metadata['priority_breakdown'] = combined_breakdown

    combined_data = {
        'export_metadata': metadata,
        'tickets': all_tickets
    }

    logger.info(f"Combined data: {len(tickets_set1)} tickets from set 1 + {len(tickets_set2)} tickets from set 2 = {len(all_tickets)} total")

    # Save combined data to file for reference
    try:
        with open(OUTPUT_FILE_COMBINED, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Saved combined ticket data to {OUTPUT_FILE_COMBINED}")
    except Exception as e:
        logger.warning(f"Failed to save combined data: {e}")

    return combined_data


def analyze_with_gemini(ticket_data):
    """
    Analyze tickets using Google Gemini API.

    Args:
        ticket_data (dict): Ticket data from JSON export

    Returns:
        str: Analysis text from Gemini
    """
    logger.info("Analyzing tickets with Gemini")

    try:
        import google.genai as genai
    except ImportError:
        raise ImportError("google-genai package not installed. Run: pip3 install google-genai")

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    # Create analysis prompt
    metadata = ticket_data.get('export_metadata', {})
    set1_count = metadata.get('set1_tickets', 0)
    set2_count = metadata.get('set2_tickets', 0)

    prompt = f"""You are analyzing Zendesk support tickets from the last 7 days.

NOTE: This data includes P1 tickets from TWO separate Zendesk instances:
- Credential Set 1: {set1_count} tickets: Standard Support Customers
- Credential Set 2: {set2_count} tickets: US-Only Support Customers
- Total: {metadata.get('total_tickets', 0)} tickets

TICKETS DATA:
{json.dumps(ticket_data, indent=2)}

Please provide:
1. Total ticket count
2. For each ticket, provide:
   - Ticket ID, Organization Name, and Subject
   - Status and Ticket Priority
   - Response time (time from creation to first response, if available in comments)
   - Total customer and agent public comments
   - Time to resolution (if resolved)
   - Brief 1-2 sentence summary of the issue and current status/next steps if available
3. Identify themes or patterns across all tickets and by instance:
   - Common issue types
   - Customer segments or organizations affected
   - Notable trends or concerns

Format the response clearly for email delivery. Use clear headings and bullet points."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        analysis = response.text

        logger.info("Gemini analysis completed")
        return analysis

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"Failed to analyze with Gemini: {e}")


def markdown_to_html(markdown_text):
    """
    Convert markdown text to HTML with proper formatting.

    Args:
        markdown_text (str): Markdown formatted text from Gemini

    Returns:
        str: HTML formatted text
    """
    try:
        import markdown

        # Convert markdown to HTML
        html_content = markdown.markdown(
            markdown_text,
            extensions=['extra', 'nl2br', 'sane_lists']
        )

        # Wrap in styled HTML
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        h1 {{
            border-bottom: 2px solid #eaecef;
            padding-bottom: 8px;
        }}
        h2 {{
            border-bottom: 1px solid #eaecef;
            padding-bottom: 6px;
        }}
        ul, ol {{
            padding-left: 24px;
        }}
        li {{
            margin: 4px 0;
        }}
        code {{
            background-color: #f6f8fa;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background-color: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        strong {{
            color: #2c3e50;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f6f8fa;
            font-weight: bold;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""

        return html_body

    except ImportError:
        logger.warning("markdown package not installed, using basic HTML conversion")
        # Fallback: basic manual conversion
        import html
        escaped = html.escape(markdown_text)

        # Basic conversions
        lines = escaped.split('\n')
        html_lines = []

        for line in lines:
            # Headers
            if line.startswith('### '):
                html_lines.append(f'<h3>{line[4:]}</h3>')
            elif line.startswith('## '):
                html_lines.append(f'<h2>{line[3:]}</h2>')
            elif line.startswith('# '):
                html_lines.append(f'<h1>{line[2:]}</h1>')
            # Bullet points
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                html_lines.append(f'<li>{line.strip()[2:]}</li>')
            # Numbered lists
            elif line.strip() and line.strip()[0].isdigit() and '. ' in line:
                content = line.strip().split('. ', 1)[1] if '. ' in line else line
                html_lines.append(f'<li>{content}</li>')
            else:
                html_lines.append(f'<p>{line}</p>' if line.strip() else '<br>')

        html_content = '\n'.join(html_lines)

        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            padding: 20px;
        }}
        h1, h2, h3 {{ color: #2c3e50; }}
        li {{ margin: 4px 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""


def send_email(subject, body, dry_run=False):
    """
    Send email via Gmail SMTP.

    Args:
        subject (str): Email subject
        body (str): Email body (markdown format from Gemini)
        dry_run (bool): If True, print email instead of sending
    """
    email_from = os.environ.get('EMAIL_FROM')
    email_password = os.environ.get('EMAIL_PASSWORD')
    email_to = os.environ.get('EMAIL_TO')

    if not all([email_from, email_password, email_to]):
        raise ValueError("Missing email environment variables: EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO")

    # Parse recipients (comma-separated)
    recipients = [email.strip() for email in email_to.split(',')]

    if dry_run:
        logger.info("=" * 80)
        logger.info("DRY RUN MODE - Email would be sent to:")
        logger.info(f"From: {email_from}")
        logger.info(f"To: {', '.join(recipients)}")
        logger.info(f"Subject: {subject}")
        logger.info("=" * 80)
        print("\n" + body)
        logger.info("=" * 80)
        return

    # Create email message
    msg = MIMEMultipart('alternative')
    msg['From'] = email_from
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    # Convert markdown to HTML
    html_body = markdown_to_html(body)

    # Attach both plain text and HTML versions
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        logger.info(f"Connecting to Gmail SMTP...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_from, email_password)

        logger.info(f"Sending email to {len(recipients)} recipient(s)...")
        server.send_message(msg)
        server.quit()

        logger.info("Email sent successfully!")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise RuntimeError(f"Email delivery failed: {e}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Automated Zendesk Ticket Analysis and Email Reporting (Gemini AI)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print analysis without sending email'
    )
    parser.add_argument(
        '--priorities',
        type=str,
        help='Filter by ticket priorities (e.g., "P1" or "P1,P2")'
    )

    args = parser.parse_args()

    try:
        # Step 1: Calculate date range
        start_date, end_date = calculate_date_range()
        logger.info(f"Analysis period: {start_date} to {end_date}")

        # Step 2: Run ticket export for credential set 1
        logger.info("=" * 80)
        logger.info("EXPORTING TICKETS FROM CREDENTIAL SET 1")
        logger.info("=" * 80)
        json_path_set1 = run_export(start_date, end_date, priorities=args.priorities, credential_set=1)

        # Step 3: Run ticket export for credential set 2
        logger.info("=" * 80)
        logger.info("EXPORTING TICKETS FROM CREDENTIAL SET 2")
        logger.info("=" * 80)
        json_path_set2 = run_export(start_date, end_date, priorities=args.priorities, credential_set=2)

        # Step 4: Load ticket data from both sets
        ticket_data_set1 = load_ticket_data(json_path_set1)
        ticket_data_set2 = load_ticket_data(json_path_set2)

        # Step 5: Merge ticket data from both sets
        logger.info("=" * 80)
        logger.info("MERGING TICKET DATA FROM BOTH CREDENTIAL SETS")
        logger.info("=" * 80)
        combined_ticket_data = merge_ticket_data(ticket_data_set1, ticket_data_set2)

        # Step 6: Analyze with Gemini
        analysis = analyze_with_gemini(combined_ticket_data)

        # Step 7: Send email
        priority_label = f" ({args.priorities} only)" if args.priorities else ""
        subject = f"Zendesk Ticket Analysis{priority_label} - {start_date} to {end_date}"
        send_email(subject, analysis, dry_run=args.dry_run)

        logger.info("Process completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Process failed: {e}")

        # Send error email if not in dry-run mode
        if not args.dry_run:
            try:
                error_subject = f"ERROR: Zendesk Ticket Analysis Failed"
                error_body = f"""The automated ticket analysis process failed with the following error:

{str(e)}

Please check the logs and investigate the issue.

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                send_email(error_subject, error_body)
            except:
                logger.error("Failed to send error notification email")

        return 1


if __name__ == "__main__":
    sys.exit(main())
