#!/usr/bin/env python3
"""
Gemini Ticket Analyzer - Interactive Analysis Tool

Loads an exported ticket JSON file and analyzes it with Gemini AI
using a custom user-provided prompt.

Features:
    - Interactive file selection and prompt input
    - Data reduction options for large files (key fields, filtering, limiting)
    - Automatic token estimation and warnings
    - Optional result saving

Usage:
    python3 gemini_ticket_analyzer.py

Environment Variables Required:
    - GOOGLE_API_KEY (for Gemini AI)
"""

import json
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_file_path():
    """
    Prompt user for the ticket JSON file path.

    Returns:
        Path: Validated file path
    """
    while True:
        print("\n" + "=" * 80)
        print("TICKET FILE SELECTION")
        print("=" * 80)
        file_path_input = input("\nEnter the path to your exported tickets JSON file: ").strip()

        # Remove quotes if user included them
        file_path_input = file_path_input.strip('"').strip("'")

        # Convert to Path object and resolve
        file_path = Path(file_path_input).expanduser().resolve()

        if not file_path.exists():
            print(f"\n❌ Error: File not found at '{file_path}'")
            retry = input("Would you like to try again? (y/n): ").strip().lower()
            if retry != 'y':
                print("Exiting...")
                sys.exit(0)
            continue

        if not file_path.is_file():
            print(f"\n❌ Error: '{file_path}' is not a file")
            retry = input("Would you like to try again? (y/n): ").strip().lower()
            if retry != 'y':
                print("Exiting...")
                sys.exit(0)
            continue

        if file_path.suffix.lower() != '.json':
            print(f"\n⚠️  Warning: File does not have a .json extension")
            confirm = input("Continue anyway? (y/n): ").strip().lower()
            if confirm != 'y':
                continue

        return file_path


def load_ticket_data(file_path):
    """
    Load and parse the exported ticket JSON file.

    Args:
        file_path (Path): Path to JSON file

    Returns:
        dict: Parsed JSON data
    """
    logger.info(f"Loading ticket data from {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Try to get ticket count from metadata
        if isinstance(data, dict):
            ticket_count = data.get('export_metadata', {}).get('total_tickets')
            if ticket_count is None:
                # Try to count tickets directly
                ticket_count = len(data.get('tickets', []))
        elif isinstance(data, list):
            ticket_count = len(data)
        else:
            ticket_count = 0

        # Estimate data size
        data_str = json.dumps(data)
        data_size_mb = len(data_str) / (1024 * 1024)
        estimated_tokens = len(data_str) / 4  # Rough estimate: 4 chars per token

        logger.info(f"Loaded data with {ticket_count} tickets")
        print(f"\n✅ Successfully loaded {ticket_count} tickets from file")
        print(f"   Data size: {data_size_mb:.2f} MB (~{estimated_tokens:,.0f} tokens estimated)")

        # Warn if data is very large
        if estimated_tokens > 800000:
            print(f"\n⚠️  WARNING: Data may exceed Gemini's token limit (1M tokens)")
            print(f"   Consider using data reduction options")

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        print(f"\n❌ Error: Invalid JSON file - {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load ticket data: {e}")
        print(f"\n❌ Error loading file: {e}")
        sys.exit(1)


def get_data_reduction_choice(ticket_data):
    """
    Ask user if they want to reduce the data size before sending to Gemini.

    Args:
        ticket_data (dict): Full ticket data

    Returns:
        dict: Potentially filtered/reduced ticket data
    """
    print("\n" + "=" * 80)
    print("DATA REDUCTION OPTIONS")
    print("=" * 80)
    print("\nWould you like to reduce the data before sending to Gemini?")
    print("(Recommended for files > 800K tokens)")
    print("\nOptions:")
    print("  1. Send full data (may fail if too large)")
    print("  2. Extract key fields only (ID, subject, status, priority, comments)")
    print("  3. Filter by priority (e.g., P1, P2)")
    print("  4. Filter by status (e.g., open, pending)")
    print("  5. Limit number of tickets")

    choice = input("\nEnter option (1-5): ").strip()

    if choice == '1':
        return ticket_data

    elif choice == '2':
        return extract_key_fields(ticket_data)

    elif choice == '3':
        priority = input("Enter priority to filter (e.g., P1, P2): ").strip().upper()
        return filter_by_priority(ticket_data, priority)

    elif choice == '4':
        status = input("Enter status to filter (e.g., open, pending, solved): ").strip().lower()
        return filter_by_status(ticket_data, status)

    elif choice == '5':
        limit = input("Enter maximum number of tickets: ").strip()
        try:
            limit = int(limit)
            return limit_tickets(ticket_data, limit)
        except ValueError:
            print("Invalid number, using full data")
            return ticket_data

    else:
        print("Invalid choice, using full data")
        return ticket_data


def extract_key_fields(ticket_data):
    """
    Extract only essential fields from tickets to reduce size.

    Args:
        ticket_data (dict): Full ticket data

    Returns:
        dict: Reduced ticket data with key fields only
    """
    print("\n🔄 Extracting key fields from tickets...")

    if isinstance(ticket_data, dict):
        tickets = ticket_data.get('tickets', [])
        metadata = ticket_data.get('export_metadata', {})
    else:
        tickets = ticket_data if isinstance(ticket_data, list) else []
        metadata = {}

    reduced_tickets = []
    for ticket in tickets:
        reduced_ticket = {
            'id': ticket.get('id'),
            'subject': ticket.get('subject'),
            'status': ticket.get('status'),
            'priority': ticket.get('priority'),
            'created_at': ticket.get('created_at'),
            'updated_at': ticket.get('updated_at'),
            'organization_name': ticket.get('organization_name'),
            'assignee_name': ticket.get('assignee_name'),
            'tags': ticket.get('tags', []),
            'comment_count': len(ticket.get('comments', [])),
            'first_comment': ticket.get('comments', [{}])[0].get('body', '') if ticket.get('comments') else ''
        }
        reduced_tickets.append(reduced_ticket)

    reduced_data = {
        'export_metadata': metadata,
        'tickets': reduced_tickets
    }

    # Calculate reduction
    original_size = len(json.dumps(ticket_data))
    reduced_size = len(json.dumps(reduced_data))
    reduction_pct = ((original_size - reduced_size) / original_size) * 100

    print(f"✅ Reduced data size by {reduction_pct:.1f}%")
    print(f"   New size: {reduced_size / (1024 * 1024):.2f} MB (~{reduced_size / 4:,.0f} tokens estimated)")

    return reduced_data


def filter_by_priority(ticket_data, priority):
    """Filter tickets by priority."""
    print(f"\n🔄 Filtering tickets by priority: {priority}...")

    if isinstance(ticket_data, dict):
        tickets = ticket_data.get('tickets', [])
        metadata = ticket_data.get('export_metadata', {})
    else:
        tickets = ticket_data if isinstance(ticket_data, list) else []
        metadata = {}

    filtered_tickets = [t for t in tickets if t.get('priority', '').upper() == priority]

    filtered_data = {
        'export_metadata': metadata,
        'tickets': filtered_tickets
    }

    print(f"✅ Filtered to {len(filtered_tickets)} tickets with priority {priority}")
    return filtered_data


def filter_by_status(ticket_data, status):
    """Filter tickets by status."""
    print(f"\n🔄 Filtering tickets by status: {status}...")

    if isinstance(ticket_data, dict):
        tickets = ticket_data.get('tickets', [])
        metadata = ticket_data.get('export_metadata', {})
    else:
        tickets = ticket_data if isinstance(ticket_data, list) else []
        metadata = {}

    filtered_tickets = [t for t in tickets if t.get('status', '').lower() == status]

    filtered_data = {
        'export_metadata': metadata,
        'tickets': filtered_tickets
    }

    print(f"✅ Filtered to {len(filtered_tickets)} tickets with status {status}")
    return filtered_data


def limit_tickets(ticket_data, limit):
    """Limit number of tickets."""
    print(f"\n🔄 Limiting to first {limit} tickets...")

    if isinstance(ticket_data, dict):
        tickets = ticket_data.get('tickets', [])
        metadata = ticket_data.get('export_metadata', {})
    else:
        tickets = ticket_data if isinstance(ticket_data, list) else []
        metadata = {}

    limited_tickets = tickets[:limit]

    limited_data = {
        'export_metadata': metadata,
        'tickets': limited_tickets
    }

    print(f"✅ Limited to {len(limited_tickets)} tickets")
    return limited_data


def get_analysis_prompt():
    """
    Prompt user for their custom analysis prompt.

    Returns:
        str: User's analysis prompt
    """
    print("\n" + "=" * 80)
    print("ANALYSIS PROMPT")
    print("=" * 80)
    print("\nEnter your analysis prompt (what would you like Gemini to analyze?)")
    print("Press Ctrl+D (Mac/Linux) or Ctrl+Z (Windows) when finished")
    print("\nExample prompts:")
    print("  - Summarize the main issues and their current status")
    print("  - Identify common themes and patterns across tickets")
    print("  - List all P1 tickets with their resolution times")
    print("  - Analyze response times and suggest improvements")
    print("\n" + "-" * 80)

    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass

    prompt = '\n'.join(lines).strip()

    if not prompt:
        print("\n❌ Error: Prompt cannot be empty")
        retry = input("Would you like to try again? (y/n): ").strip().lower()
        if retry == 'y':
            return get_analysis_prompt()
        else:
            print("Exiting...")
            sys.exit(0)

    print(f"\n✅ Prompt received ({len(prompt)} characters)")
    return prompt


def analyze_with_gemini(ticket_data, user_prompt):
    """
    Analyze tickets using Google Gemini API with custom prompt.

    Args:
        ticket_data (dict): Ticket data from JSON export
        user_prompt (str): User's custom analysis prompt

    Returns:
        str: Analysis text from Gemini
    """
    logger.info("Analyzing tickets with Gemini")
    print("\n" + "=" * 80)
    print("GEMINI ANALYSIS IN PROGRESS")
    print("=" * 80)
    print("\nSending data to Gemini AI... (this may take a moment)")

    try:
        import google.genai as genai
    except ImportError:
        print("\n❌ Error: google-genai package not installed")
        print("Install it with: pip3 install google-genai")
        sys.exit(1)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        print("\n❌ Error: GOOGLE_API_KEY environment variable not set")
        print("Set it with: export GOOGLE_API_KEY='your-api-key'")
        sys.exit(1)

    # Create the full prompt with context
    full_prompt = f"""You are analyzing Zendesk support tickets.

TICKETS DATA:
{json.dumps(ticket_data, indent=2)}

USER REQUEST:
{user_prompt}

Please provide a clear, well-formatted analysis addressing the user's request."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=full_prompt
        )
        analysis = response.text

        logger.info("Gemini analysis completed")
        print("\n✅ Analysis complete!")
        return analysis

    except Exception as e:
        error_str = str(e)
        logger.error(f"Gemini API error: {e}")

        # Check if it's a token limit error
        if 'token' in error_str.lower() and ('limit' in error_str.lower() or 'exceeds' in error_str.lower()):
            print(f"\n❌ Error: Data exceeds Gemini's token limit")
            print(f"\n💡 Solutions:")
            print(f"   1. Restart and choose option 2 to extract key fields only")
            print(f"   2. Filter by priority (option 3) or status (option 4)")
            print(f"   3. Limit the number of tickets (option 5)")
            print(f"   4. Split your data into smaller files")
            print(f"\nOriginal error: {e}")
        else:
            print(f"\n❌ Error calling Gemini API: {e}")

        sys.exit(1)


def save_analysis(analysis, file_path):
    """
    Optionally save analysis to a file.

    Args:
        analysis (str): Analysis text from Gemini
        file_path (Path): Original input file path
    """
    print("\n" + "=" * 80)
    save_choice = input("\nWould you like to save the analysis to a file? (y/n): ").strip().lower()

    if save_choice == 'y':
        # Suggest output filename based on input
        suggested_name = file_path.stem + "_analysis.txt"
        suggested_path = file_path.parent / suggested_name

        output_path_input = input(f"\nEnter output file path (default: {suggested_path}): ").strip()

        if not output_path_input:
            output_path = suggested_path
        else:
            output_path = Path(output_path_input.strip('"').strip("'")).expanduser().resolve()

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(analysis)
            print(f"\n✅ Analysis saved to: {output_path}")
        except Exception as e:
            print(f"\n❌ Error saving file: {e}")


def main():
    """Main execution function."""
    print("\n" + "=" * 80)
    print("GEMINI TICKET ANALYZER")
    print("Interactive Ticket Analysis Tool")
    print("=" * 80)

    try:
        # Step 1: Get file path from user
        file_path = get_file_path()

        # Step 2: Load ticket data
        ticket_data = load_ticket_data(file_path)

        # Step 3: Ask about data reduction
        processed_data = get_data_reduction_choice(ticket_data)

        # Step 4: Get analysis prompt from user
        user_prompt = get_analysis_prompt()

        # Step 5: Analyze with Gemini
        analysis = analyze_with_gemini(processed_data, user_prompt)

        # Step 6: Display results
        print("\n" + "=" * 80)
        print("ANALYSIS RESULTS")
        print("=" * 80)
        print("\n" + analysis)
        print("\n" + "=" * 80)

        # Step 7: Optionally save results
        save_analysis(analysis, file_path)

        print("\n✅ Process completed successfully!")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Process failed: {e}")
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
