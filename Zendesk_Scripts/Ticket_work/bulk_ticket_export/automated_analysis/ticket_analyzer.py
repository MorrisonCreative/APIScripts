#!/usr/bin/env python3
"""
Automated Zendesk Ticket Analysis and Email Reporting

Exports tickets from last 7 days, analyzes with LLM (Claude or Gemini), and emails results.

Usage:
    python3 ticket_analyzer.py --llm claude [--dry-run] [--priorities P1]
    python3 ticket_analyzer.py --llm gemini [--dry-run] [--priorities P1,P2]

Environment Variables Required:
    - ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN (for export)
    - ANTHROPIC_API_KEY (for Claude) or GOOGLE_API_KEY (for Gemini)
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
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "exported_tickets.json")


def calculate_date_range():
    """Calculate date range for last 7 days."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


def run_export(start_date, end_date, priorities=None):
    """
    Execute zendesk_exporter.py with proper arguments.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        priorities (str): Comma-separated priorities (e.g., "P1" or "P1,P2")

    Returns:
        str: Path to exported JSON file

    Raises:
        RuntimeError: If export fails
    """
    logger.info(f"Running ticket export for {start_date} to {end_date}")
    if priorities:
        logger.info(f"Filtering for priorities: {priorities}")

    cmd = [
        "python3",
        EXPORTER_SCRIPT,
        "--start-date", start_date,
        "--end-date", end_date,
        "--format", "json",
        "--output", OUTPUT_FILE
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
        logger.info("Export completed successfully")
        logger.debug(result.stdout)
        return OUTPUT_FILE
    except subprocess.CalledProcessError as e:
        logger.error(f"Export failed: {e.stderr}")
        raise RuntimeError(f"Failed to export tickets: {e.stderr}")


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


def analyze_with_claude(ticket_data):
    """
    Analyze tickets using Claude API.

    Args:
        ticket_data (dict): Ticket data from JSON export

    Returns:
        str: Analysis text from Claude
    """
    logger.info("Analyzing tickets with Claude")

    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip3 install anthropic")

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Create analysis prompt
    prompt = f"""You are analyzing Zendesk support tickets from the last 7 days.

TICKETS DATA:
{json.dumps(ticket_data, indent=2)}

Please provide:
1. Total ticket count
2. For each ticket, provide:
   - Ticket ID and subject
   - Status and priority
   - Response time (time from creation to first response, if available in comments)
   - Time to resolution (if resolved)
   - Brief 1-2 sentence summary of the issue
3. Identify themes or patterns across all tickets:
   - Common issue types
   - Customer segments or organizations affected
   - Notable trends or concerns

Format the response clearly for email delivery. Use clear headings and bullet points."""

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        analysis = message.content[0].text
        logger.info("Claude analysis completed")
        return analysis

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise RuntimeError(f"Failed to analyze with Claude: {e}")


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
        import google.generativeai as genai
    except ImportError:
        raise ImportError("google-generativeai package not installed. Run: pip3 install google-generativeai")

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    # Create analysis prompt
    prompt = f"""You are analyzing Zendesk support tickets from the last 7 days.

TICKETS DATA:
{json.dumps(ticket_data, indent=2)}

Please provide:
1. Total ticket count
2. For each ticket, provide:
   - Ticket ID and subject
   - Status and priority
   - Response time (time from creation to first response, if available in comments)
   - Time to resolution (if resolved)
   - Brief 1-2 sentence summary of the issue
3. Identify themes or patterns across all tickets:
   - Common issue types
   - Customer segments or organizations affected
   - Notable trends or concerns

Format the response clearly for email delivery. Use clear headings and bullet points."""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('models/gemini-2.5-flash')

        response = model.generate_content(prompt)
        analysis = response.text

        logger.info("Gemini analysis completed")
        return analysis

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise RuntimeError(f"Failed to analyze with Gemini: {e}")


def send_email(subject, body, dry_run=False):
    """
    Send email via Gmail SMTP.

    Args:
        subject (str): Email subject
        body (str): Email body (plain text)
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
    msg = MIMEMultipart()
    msg['From'] = email_from
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    # Convert plain text to HTML with basic formatting
    html_body = f"""<html>
<head></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
<pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{body}</pre>
</body>
</html>"""

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
        description='Automated Zendesk Ticket Analysis and Email Reporting'
    )
    parser.add_argument(
        '--llm',
        choices=['claude', 'gemini'],
        required=True,
        help='LLM to use for analysis'
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

        # Step 2: Run ticket export
        json_path = run_export(start_date, end_date, priorities=args.priorities)

        # Step 3: Load ticket data
        ticket_data = load_ticket_data(json_path)

        # Step 4: Analyze with selected LLM
        if args.llm == 'claude':
            analysis = analyze_with_claude(ticket_data)
        elif args.llm == 'gemini':
            analysis = analyze_with_gemini(ticket_data)
        else:
            raise ValueError(f"Unknown LLM: {args.llm}")

        # Step 5: Send email
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
