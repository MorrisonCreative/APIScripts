"""
Zendesk Ticket Exporter

Export Zendesk tickets by organization, timeframe, or custom priority field.
Supports multiple credential sets, full event history, flexible filtering, and
multiple output formats (JSON, CSV).

Usage:
    python zendesk_exporter.py [OPTIONS]

Examples:
    # Export by organization
    python zendesk_exporter.py --organization-id 12345

    # Export by date range
    python zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31

    # Filter by priority
    python zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 --priorities P1,P2

    # Export to CSV format
    python zendesk_exporter.py --start-date 2024-01-01 --end-date 2024-01-31 --format csv

    # Use second credential set
    python zendesk_exporter.py --credential-set 2 --organization-id 67890
"""

import requests
import json
import csv
import os
import sys
import logging
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Custom field configuration
PRIORITY_FIELD_ID = "360047533253"
PRIORITY_FIELD_NAME = "Ticket Priority"
VALID_PRIORITIES = ["P1", "P2", "P3", "P4"]

# Date field options
VALID_DATE_FIELDS = ["created", "updated", "solved"]
DEFAULT_DATE_FIELD = "created"
DEFAULT_FETCH_FULL_HISTORY = True


def validate_and_parse_date(date_string):
    """
    Parse and validate date string to YYYY-MM-DD format.

    Accepts ISO 8601 (2024-01-15T10:30:00Z) or simple format (2024-01-15).

    Args:
        date_string (str): Date string to parse

    Returns:
        str: Date in YYYY-MM-DD format, or None if input is empty

    Raises:
        ValueError: If date format is invalid
    """
    if not date_string:
        return None

    try:
        # ISO 8601 format (e.g., 2024-01-15T10:30:00Z)
        parsed = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Simple YYYY-MM-DD format
            parsed = datetime.strptime(date_string, "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_string}. Use YYYY-MM-DD or ISO 8601 format.")


def validate_priorities(priority_string):
    """
    Validate and parse comma-separated priority values.

    Args:
        priority_string (str): Comma-separated priorities (e.g., "P1,P2,P3")

    Returns:
        list: List of uppercase priority values, or None if input is empty

    Raises:
        ValueError: If any priority value is invalid
    """
    if not priority_string:
        return None

    # Parse and normalize to uppercase
    priorities = [p.strip().upper() for p in priority_string.split(",")]

    # Check for invalid values
    invalid = [p for p in priorities if p not in VALID_PRIORITIES]
    if invalid:
        raise ValueError(f"Invalid priority values: {invalid}. Valid values: {VALID_PRIORITIES}")

    return priorities


def validate_date_range(start_date, end_date):
    """
    Ensure start date is before or equal to end date.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format

    Returns:
        bool: True if valid

    Raises:
        ValueError: If start date is after end date
    """
    if not start_date or not end_date:
        return True

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if start > end:
        raise ValueError(f"Start date ({start_date}) must be before or equal to end date ({end_date})")

    return True


def validate_date_field(field):
    """
    Validate date field name.

    Args:
        field (str): Date field name to validate

    Returns:
        bool: True if valid

    Raises:
        ValueError: If field is not one of: created, updated, solved
    """
    if field not in VALID_DATE_FIELDS:
        raise ValueError(f"Invalid date field: {field}. Valid values: {VALID_DATE_FIELDS}")
    return True


def build_search_query(organization_id=None, start_date=None, end_date=None,
                      date_field="created", ticket_priorities=None):
    """
    Build Zendesk search query string with multiple filter options.

    Constructs a query using Zendesk's search API syntax with support for:
    - Organization filtering
    - Date range filtering
    - Custom field priority filtering

    Args:
        organization_id (str, optional): Organization ID to filter by
        start_date (str, optional): Start date in YYYY-MM-DD format
        end_date (str, optional): End date in YYYY-MM-DD format
        date_field (str, optional): Date field to filter on (created, updated, solved)
        ticket_priorities (list, optional): List of priority values (P1, P2, P3, P4)

    Returns:
        str: Zendesk search query string

    Example:
        >>> build_search_query(start_date="2024-01-01", end_date="2024-01-31",
        ...                    ticket_priorities=["P1", "P2"])
        'type:ticket created>=2024-01-01 created<=2024-01-31 (custom_field_360047533253:P1 custom_field_360047533253:P2)'
    """
    query_parts = ["type:ticket"]

    # Add organization filter
    if organization_id:
        query_parts.append(f"organization_id:{organization_id}")

    # Add date range filter
    if start_date and end_date:
        query_parts.append(f"{date_field}>={start_date}")
        query_parts.append(f"{date_field}<={end_date}")

    # Add custom field priority filter (uses OR logic for multiple priorities)
    if ticket_priorities:
        priority_queries = [f"custom_field_{PRIORITY_FIELD_ID}:{p}" for p in ticket_priorities]
        query_parts.append(f"({' '.join(priority_queries)})")

    return " ".join(query_parts)


def generate_filename(start_date=None, end_date=None, priorities=None, organization_id=None, file_format="json"):
    """
    Generate descriptive filename based on export parameters.

    Creates a filename that indicates the export scope and timestamp.

    Args:
        start_date (str, optional): Start date in YYYY-MM-DD format
        end_date (str, optional): End date in YYYY-MM-DD format
        priorities (list, optional): List of priority values
        organization_id (str, optional): Organization ID
        file_format (str, optional): File format extension (default: "json")

    Returns:
        str: Generated filename with appropriate extension

    Examples:
        - Date range only: tickets_2024-01-01_to_2024-01-31_20240315_143022.json
        - With priorities: tickets_2024-01-01_to_2024-01-31_P1-P2_20240315_143022.csv
        - Org only: tickets_org_123456_20240315_143022.json
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = ["tickets"]

    # Add date range to filename
    if start_date and end_date:
        parts.append(f"{start_date}_to_{end_date}")

    # Add priorities to filename
    if priorities:
        parts.append("-".join(priorities))

    # Add organization ID to filename
    if organization_id:
        parts.append(f"org_{organization_id}")

    # Always include timestamp
    parts.append(timestamp)

    return "_".join(parts) + f".{file_format}"


def flatten_ticket_for_csv(ticket):
    """
    Flatten ticket dictionary for CSV export.

    Extracts main ticket fields and custom field values into a flat structure.
    Note: Does not include full audit/comment history (use JSON for complete data).

    Args:
        ticket (dict): Ticket dictionary from Zendesk API

    Returns:
        dict: Flattened ticket data suitable for CSV
    """
    flattened = {
        'id': ticket.get('id'),
        'subject': ticket.get('subject', ''),
        'description': ticket.get('description', ''),
        'status': ticket.get('status'),
        'priority': ticket.get('priority'),
        'type': ticket.get('type'),
        'created_at': ticket.get('created_at'),
        'updated_at': ticket.get('updated_at'),
        'organization_id': ticket.get('organization_id'),
        'requester_id': ticket.get('requester_id'),
        'assignee_id': ticket.get('assignee_id'),
        'submitter_id': ticket.get('submitter_id'),
        'group_id': ticket.get('group_id'),
        'tags': ','.join(ticket.get('tags', [])) if ticket.get('tags') else '',
        'url': ticket.get('url'),
    }

    # Extract custom field for Ticket Priority (ID: 360047533253)
    custom_fields = ticket.get('custom_fields', [])
    for field in custom_fields:
        if field.get('id') == int(PRIORITY_FIELD_ID):
            flattened['ticket_priority'] = field.get('value', '')
            break
    else:
        flattened['ticket_priority'] = ''

    # Add counts if history was fetched
    if 'audits' in ticket:
        flattened['audit_count'] = len(ticket.get('audits', []))
    if 'comments' in ticket:
        flattened['comment_count'] = len(ticket.get('comments', []))

    return flattened


def export_to_csv(tickets, output_path):
    """
    Export tickets to CSV format.

    Creates a CSV file with flattened ticket data. Each ticket becomes one row.
    Note: Full audit and comment history is not included in CSV (use JSON for that).

    Args:
        tickets (list): List of ticket dictionaries
        output_path (str): Path to output CSV file

    Returns:
        None
    """
    if not tickets:
        logging.warning("No tickets to export to CSV")
        # Create empty CSV with headers
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'id', 'subject', 'description', 'status', 'priority', 'type',
                'created_at', 'updated_at', 'organization_id', 'requester_id',
                'assignee_id', 'submitter_id', 'group_id', 'tags', 'url',
                'ticket_priority', 'audit_count', 'comment_count'
            ])
            writer.writeheader()
        return

    # Flatten all tickets
    flattened_tickets = [flatten_ticket_for_csv(ticket) for ticket in tickets]

    # Get all unique field names (in case some tickets have extra fields)
    fieldnames = set()
    for ticket in flattened_tickets:
        fieldnames.update(ticket.keys())
    fieldnames = sorted(fieldnames)

    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened_tickets)

    logging.info(f"Exported {len(tickets)} tickets to CSV: {output_path}")


class ZendeskAPIClient:
    """
    Client for interacting with the Zendesk API.

    Provides methods for searching tickets, fetching audit history, comments,
    and enriching ticket data with full event history.

    Attributes:
        base_url (str): Base URL for Zendesk API (e.g., https://mycompany.zendesk.com/api/v2)
        auth (tuple): Authentication tuple for HTTP Basic Auth (email/token, api_token)
    """

    def __init__(self, subdomain, email, api_token):
        """
        Initialize Zendesk API client.

        Args:
            subdomain (str): Zendesk subdomain (e.g., "mycompany" for mycompany.zendesk.com)
            email (str): Email address associated with the API token
            api_token (str): Zendesk API token
        """
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2"
        self.auth = (f"{email}/token", api_token)
        logging.info(f"Initialized ZendeskAPIClient for subdomain: {subdomain}")

    def get(self, path, params=None):
        """
        Make authenticated GET request to Zendesk API.

        Args:
            path (str): API endpoint path (e.g., "/tickets.json")
            params (dict, optional): Query parameters

        Returns:
            dict: JSON response from API

        Raises:
            requests.exceptions.HTTPError: If API returns error status code
        """
        url = f"{self.base_url}{path}"
        logging.debug(f"Making GET request to: {url} with params: {params}")
        response = requests.get(url, auth=self.auth, params=params)
        response.raise_for_status()
        return response.json()

    def search_tickets_by_organization(self, organization_id):
        """
        Search for all tickets belonging to a specific organization.

        Uses Zendesk Search API with pagination to retrieve all matching tickets.

        Args:
            organization_id (str): Zendesk organization ID

        Returns:
            list: List of ticket dictionaries
        """
        all_tickets = []
        page_number = 1
        per_page = 100  # Maximum page size for Zendesk Search API

        logging.info(f"Starting to fetch tickets for organization ID: {organization_id}")

        while True:
            params = {
                "query": f"type:ticket organization_id:{organization_id}",
                "per_page": per_page,
                "page": page_number
            }

            logging.debug(f"Fetching page {page_number} with {per_page} items per page")
            response_data = self.get("/search.json", params=params)
            tickets = response_data.get("results", [])
            all_tickets.extend(tickets)
            logging.info(f"Fetched {len(tickets)} tickets on page {page_number}. Total tickets: {len(all_tickets)}")

            # Stop if no more tickets or last page (partial page indicates end)
            if not tickets or len(tickets) < per_page:
                break

            page_number += 1

        logging.info(f"Finished fetching all tickets for organization ID: {organization_id}. Total: {len(all_tickets)}")
        return all_tickets

    def get_ticket_audits(self, ticket_id):
        """
        Fetch all audit events for a ticket.

        Retrieves complete audit history including status changes, field updates,
        assignments, and other ticket modifications.

        Args:
            ticket_id (int): Zendesk ticket ID

        Returns:
            list: List of audit dictionaries with event history
        """
        all_audits = []
        url = f"/tickets/{ticket_id}/audits.json"

        logging.debug(f"Fetching audits for ticket ID: {ticket_id}")

        # Use cursor-based pagination
        while url:
            response_data = self.get(url, params=None)
            audits = response_data.get("audits", [])
            all_audits.extend(audits)

            # Get next page URL (cursor-based pagination)
            url = response_data.get("next_page")
            if url:
                # Convert full URL to relative path for API call
                url = url.replace(self.base_url, "")

        logging.debug(f"Fetched {len(all_audits)} audits for ticket ID: {ticket_id}")
        return all_audits

    def get_ticket_comments(self, ticket_id):
        """
        Fetch all comments for a ticket.

        Retrieves both public and private comments, including the initial description.

        Args:
            ticket_id (int): Zendesk ticket ID

        Returns:
            list: List of comment dictionaries
        """
        all_comments = []
        url = f"/tickets/{ticket_id}/comments.json"

        logging.debug(f"Fetching comments for ticket ID: {ticket_id}")

        # Use cursor-based pagination
        while url:
            response_data = self.get(url, params=None)
            comments = response_data.get("comments", [])
            all_comments.extend(comments)

            # Get next page URL (cursor-based pagination)
            url = response_data.get("next_page")
            if url:
                # Convert full URL to relative path for API call
                url = url.replace(self.base_url, "")

        logging.debug(f"Fetched {len(all_comments)} comments for ticket ID: {ticket_id}")
        return all_comments

    def enrich_tickets_with_history(self, tickets, include_audits=True, include_comments=True):
        """
        Enrich tickets with their full event history (audits and comments).

        Fetches additional data for each ticket:
        - Audits: Status changes, field updates, assignments
        - Comments: Public and private comments, including initial description

        Includes rate limiting and error handling to ensure robustness.

        Args:
            tickets (list): List of ticket dictionaries to enrich
            include_audits (bool): Whether to fetch audit history (default: True)
            include_comments (bool): Whether to fetch comments (default: True)

        Returns:
            list: List of enriched ticket dictionaries with added "audits" and "comments" keys

        Note:
            - Tickets are still included in output even if enrichment fails
            - Rate limited to 0.1s between requests to respect API quotas
            - Zendesk Enterprise has a limit of 700 requests per minute
        """
        enriched_tickets = []
        total = len(tickets)

        logging.info(f"Starting to enrich {total} tickets with event history...")

        for index, ticket in enumerate(tickets, 1):
            ticket_id = ticket.get("id")

            try:
                logging.info(f"Processing ticket {index}/{total}: ID {ticket_id}")

                # Fetch and attach audit history if requested
                if include_audits:
                    ticket["audits"] = self.get_ticket_audits(ticket_id)

                # Fetch and attach comments if requested
                if include_comments:
                    ticket["comments"] = self.get_ticket_comments(ticket_id)

                enriched_tickets.append(ticket)

                # Rate limiting to avoid hitting Zendesk API limits
                # 0.1 second delay = max 600 requests/minute (safely under 700 limit)
                time.sleep(0.1)

            except requests.exceptions.HTTPError as e:
                # Log HTTP errors but still include ticket without enrichment
                logging.warning(f"Failed to fetch history for ticket {ticket_id}: {e.response.status_code} - {e.response.text}")
                enriched_tickets.append(ticket)
            except Exception as e:
                # Log unexpected errors but still include ticket without enrichment
                logging.warning(f"Unexpected error fetching history for ticket {ticket_id}: {e}")
                enriched_tickets.append(ticket)

        logging.info(f"Finished enriching tickets with event history")
        return enriched_tickets

    def search_tickets_by_timeframe(self, start_date, end_date, date_field="created",
                                    ticket_priorities=None, organization_id=None):
        """
        Search tickets by date range with optional filters.

        Flexible search supporting:
        - Date range filtering (required)
        - Custom priority field filtering (optional)
        - Organization filtering (optional)

        Args:
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            date_field (str): Date field to filter on ("created", "updated", "solved")
            ticket_priorities (list, optional): List of priorities to filter (P1, P2, P3, P4)
            organization_id (str, optional): Organization ID to filter by

        Returns:
            list: List of ticket dictionaries matching the search criteria
        """
        # Build search query with all specified filters
        query = build_search_query(organization_id, start_date, end_date,
                                   date_field, ticket_priorities)

        all_tickets = []
        page_number = 1
        per_page = 100  # Maximum page size for Zendesk Search API

        logging.info(f"Starting ticket search with query: {query}")

        # Paginate through all results
        while True:
            params = {
                "query": query,
                "per_page": per_page,
                "page": page_number
            }

            logging.debug(f"Fetching page {page_number} with {per_page} items per page")
            response_data = self.get("/search.json", params=params)
            tickets = response_data.get("results", [])
            all_tickets.extend(tickets)
            logging.info(f"Fetched {len(tickets)} tickets on page {page_number}. Total tickets: {len(all_tickets)}")

            # Stop if no more tickets or last page (partial page indicates end)
            if not tickets or len(tickets) < per_page:
                break

            page_number += 1

        logging.info(f"Finished fetching tickets. Total: {len(all_tickets)}")
        return all_tickets


def detect_credential_sets():
    """
    Detect which credential sets are configured in environment variables.

    Checks for two possible sets of Zendesk credentials:
    - Set 1: ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN
    - Set 2: ZENDESK_SUBDOMAIN_2, ZENDESK_EMAIL_2, ZENDESK_API_TOKEN_2

    Returns:
        tuple: (set1_complete, set2_complete, set1_creds, set2_creds)
            - set1_complete (bool): True if all Set 1 variables are set
            - set2_complete (bool): True if all Set 2 variables are set
            - set1_creds (dict): Set 1 credentials (subdomain, email, api_token)
            - set2_creds (dict): Set 2 credentials (subdomain, email, api_token)
    """
    # Set 1 - Primary credentials
    set1 = {
        'subdomain': os.getenv('ZENDESK_SUBDOMAIN'),
        'email': os.getenv('ZENDESK_EMAIL'),
        'api_token': os.getenv('ZENDESK_API_TOKEN')
    }

    # Set 2 - Secondary credentials (with _2 suffix)
    set2 = {
        'subdomain': os.getenv('ZENDESK_SUBDOMAIN_2'),
        'email': os.getenv('ZENDESK_EMAIL_2'),
        'api_token': os.getenv('ZENDESK_API_TOKEN_2')
    }

    # Check if all three values are present for each set
    set1_complete = all(set1.values())
    set2_complete = all(set2.values())

    return set1_complete, set2_complete, set1, set2


def normalize_credential_set(value):
    """
    Normalize credential set value to integer 1 or 2.

    Accepts various input formats for user convenience:
    - Numeric: 1, 2, "1", "2"
    - Named: "primary", "secondary", "first", "second", "default", "alternate"

    Args:
        value (str or int): Credential set identifier

    Returns:
        int: 1 or 2, or None if value is None

    Raises:
        ValueError: If value cannot be normalized to 1 or 2
    """
    if value is None:
        return None

    # Normalize to lowercase string for comparison
    str_value = str(value).strip().lower()

    # Map various input formats to credential set numbers
    if str_value in ['1', 'primary', 'first', 'default']:
        return 1
    elif str_value in ['2', 'secondary', 'second', 'alternate']:
        return 2
    else:
        raise ValueError(f"Invalid credential set: {value}. Must be 1 or 2.")


def load_credentials(credential_set=None):
    """
    Load Zendesk credentials based on selected set or auto-detection.

    Supports intelligent credential loading:
    1. If only one set is configured, automatically uses it (backward compatible)
    2. If both sets are configured, requires explicit selection
    3. If neither set is configured, exits with error

    Args:
        credential_set (int, optional): Which credential set to use (1 or 2).
                                       If None, auto-detects based on what's configured.

    Returns:
        tuple: (subdomain, email, api_token, selected_set)
            - subdomain (str): Zendesk subdomain
            - email (str): Email for API authentication
            - api_token (str): API token
            - selected_set (int): Which credential set was used (1 or 2)

    Raises:
        SystemExit: If credentials are invalid, missing, or ambiguous
    """
    set1_complete, set2_complete, set1, set2 = detect_credential_sets()

    # Error Case 1: No credentials configured at all
    if not set1_complete and not set2_complete:
        logging.error("No Zendesk credentials configured. Please set:")
        logging.error("  ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN")
        logging.error("Or for second set:")
        logging.error("  ZENDESK_SUBDOMAIN_2, ZENDESK_EMAIL_2, ZENDESK_API_TOKEN_2")
        sys.exit(1)

    # Auto-selection logic (backward compatible)
    if credential_set is None:
        if set1_complete and not set2_complete:
            # Only Set 1 is complete - use it automatically
            credential_set = 1
            logging.info("Auto-selected credential set 1 (only complete set)")
        elif set2_complete and not set1_complete:
            # Only Set 2 is complete - use it automatically
            credential_set = 2
            logging.info("Auto-selected credential set 2 (only complete set)")
        elif set1_complete and set2_complete:
            # Error Case 2: Both sets are complete but user didn't specify which to use
            logging.error("Multiple credential sets detected. Please specify which to use:")
            logging.error("  --credential-set 1  (or set ZENDESK_CREDENTIAL_SET=1)")
            logging.error("  --credential-set 2  (or set ZENDESK_CREDENTIAL_SET=2)")
            sys.exit(1)

    # Load Set 1 credentials
    if credential_set == 1:
        if not set1_complete:
            # Error Case 3: Set 1 requested but incomplete
            missing = [k for k, v in set1.items() if not v]
            logging.error(f"Credential set 1 is incomplete. Missing: {missing}")
            logging.error("Required: ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN")
            sys.exit(1)
        return set1['subdomain'], set1['email'], set1['api_token'], 1

    # Load Set 2 credentials
    elif credential_set == 2:
        if not set2_complete:
            # Error Case 4: Set 2 requested but incomplete
            missing = [k for k, v in set2.items() if not v]
            logging.error(f"Credential set 2 is incomplete. Missing: {missing}")
            logging.error("Required: ZENDESK_SUBDOMAIN_2, ZENDESK_EMAIL_2, ZENDESK_API_TOKEN_2")
            sys.exit(1)
        return set2['subdomain'], set2['email'], set2['api_token'], 2

    # Error Case 5: Invalid credential set number (should not happen with proper validation)
    else:
        logging.error(f"Invalid credential set: {credential_set}")
        sys.exit(1)


def parse_arguments():
    """
    Parse command-line arguments for the Zendesk ticket exporter.

    Supports multiple export modes:
    - Organization-based: Use --organization-id
    - Timeframe-based: Use --start-date and --end-date
    - Combined: Use both organization and timeframe options

    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    import argparse
    parser = argparse.ArgumentParser(
        description='Export Zendesk tickets by organization, timeframe, or priority',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Export by organization
  %(prog)s --organization-id 12345

  # Export by date range with priorities
  %(prog)s --start-date 2024-01-01 --end-date 2024-01-31 --priorities P1,P2

  # Use second credential set
  %(prog)s --credential-set 2 --organization-id 67890

  # Export without full history (faster)
  %(prog)s --start-date 2024-01-01 --end-date 2024-01-31 --no-history
        '''
    )

    # Date range filtering
    parser.add_argument('--start-date',
                       help='Start date for timeframe export (YYYY-MM-DD)')
    parser.add_argument('--end-date',
                       help='End date for timeframe export (YYYY-MM-DD)')
    parser.add_argument('--date-field', default='created',
                       choices=['created', 'updated', 'solved'],
                       help='Date field to filter on (default: created)')

    # Priority filtering
    parser.add_argument('--priorities',
                       help='Comma-separated ticket priorities (P1,P2,P3,P4)')

    # Organization filtering
    parser.add_argument('--organization-id',
                       help='Zendesk organization ID to filter by')

    # Credential set selection
    parser.add_argument('--credential-set', type=int, choices=[1, 2],
                       help='Select which credential set to use (1 or 2)')

    # Export options
    parser.add_argument('--format', default='json', choices=['json', 'csv'],
                       help='Output file format (default: json)')
    parser.add_argument('--no-history', action='store_true',
                       help='Skip fetching audit history and comments (faster)')
    parser.add_argument('--output',
                       help='Output file path (default: auto-generated)')

    return parser.parse_args()


if __name__ == "__main__":
    from datetime import datetime

    # Parse command-line arguments
    args = parse_arguments()

    # Determine which credential set to use
    credential_set_arg = args.credential_set or os.getenv("ZENDESK_CREDENTIAL_SET")
    if credential_set_arg:
        try:
            credential_set = normalize_credential_set(credential_set_arg)
        except ValueError as e:
            logging.error(f"Credential set error: {e}")
            sys.exit(1)
    else:
        credential_set = None  # Auto-detect

    # Load credentials
    SUBDOMAIN, EMAIL, API_TOKEN, selected_set = load_credentials(credential_set)
    logging.info(f"Using credential set {selected_set}: {SUBDOMAIN} ({EMAIL})")

    # Get configuration from CLI args or env vars
    start_date = args.start_date or os.getenv("START_DATE")
    end_date = args.end_date or os.getenv("END_DATE")
    date_field = args.date_field or os.getenv("DATE_FIELD", DEFAULT_DATE_FIELD)
    priorities_str = args.priorities or os.getenv("TICKET_PRIORITIES")
    organization_id = args.organization_id or os.getenv("CUSTOMER_ORGANIZATION_ID")
    fetch_history = not args.no_history and os.getenv("FETCH_FULL_HISTORY", "true").lower() in ["true", "1", "yes"]
    output_format = args.format or os.getenv("OUTPUT_FORMAT", "json")
    output_path = args.output or os.getenv("OUTPUT_FILE_PATH")

    # Determine export mode
    has_timeframe = start_date or end_date
    has_organization = organization_id

    # Interactive prompts for missing required configuration
    try:
        # If neither mode is specified, prompt for which mode to use
        if not has_timeframe and not has_organization:
            mode_choice = input("Export mode: (1) By organization, (2) By timeframe, (3) Both: ").strip()

            if mode_choice == "1":
                organization_id = input("Enter the Customer Organization ID: ").strip()
                if not organization_id or not organization_id.isdigit():
                    logging.error("Invalid organization ID. Must be numeric.")
                    sys.exit(1)
                has_organization = True

            elif mode_choice == "2":
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()
                has_timeframe = True

            elif mode_choice == "3":
                organization_id = input("Enter the Customer Organization ID: ").strip()
                if not organization_id or not organization_id.isdigit():
                    logging.error("Invalid organization ID. Must be numeric.")
                    sys.exit(1)
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()
                has_timeframe = True
                has_organization = True

            else:
                logging.error("Invalid mode selection.")
                sys.exit(1)

        # If we have timeframe but missing dates, prompt for them
        if has_timeframe:
            if not start_date:
                start_date = input("Enter start date (YYYY-MM-DD): ").strip()
            if not end_date:
                end_date = input("Enter end date (YYYY-MM-DD): ").strip()

        # If we have organization but missing org ID, prompt for it
        if has_organization and not organization_id:
            organization_id = input("Enter the Customer Organization ID: ").strip()
            if not organization_id or not organization_id.isdigit():
                logging.error("Invalid organization ID. Must be numeric.")
                sys.exit(1)

        # Prompt for priority filter if using timeframe mode
        if has_timeframe and not priorities_str:
            priorities_input = input("Filter by priorities? (P1,P2,P3,P4 or press Enter for all): ").strip()
            if priorities_input:
                priorities_str = priorities_input

        # Prompt for fetch history if not specified
        if fetch_history is None:
            response = input("Fetch full event history (audits & comments)? [Y/n]: ").strip().lower()
            fetch_history = response != "n" and response != "no"

    except KeyboardInterrupt:
        logging.info("\nOperation cancelled by user.")
        sys.exit(0)

    # Validate inputs
    try:
        if has_timeframe:
            start_date = validate_and_parse_date(start_date)
            end_date = validate_and_parse_date(end_date)
            validate_date_range(start_date, end_date)
            validate_date_field(date_field)

        if priorities_str:
            priorities = validate_priorities(priorities_str)
        else:
            priorities = None

        if has_organization and organization_id and not organization_id.isdigit():
            raise ValueError(f"Invalid organization ID: {organization_id}. Must be numeric.")

    except ValueError as e:
        logging.error(f"Validation error: {e}")
        sys.exit(1)

    # Validate format and history combination
    if output_format == "csv" and fetch_history:
        logging.warning("CSV format does not include full audit/comment history. Only ticket metadata and counts will be exported.")
        logging.warning("For complete history, use JSON format (--format json)")

    # Generate output filename if not specified
    if not output_path:
        output_path = generate_filename(start_date, end_date, priorities, organization_id, output_format)
        logging.info(f"Using generated filename: {output_path}")

    # Initialize Zendesk API client
    client = ZendeskAPIClient(SUBDOMAIN, EMAIL, API_TOKEN)

    try:
        # Execute export based on mode
        if has_timeframe:
            # Timeframe mode (with optional organization filter)
            logging.info(f"Fetching tickets from {start_date} to {end_date} (date field: {date_field})...")
            if priorities:
                logging.info(f"Filtering by priorities: {', '.join(priorities)}")
            if organization_id:
                logging.info(f"Filtering by organization ID: {organization_id}")

            tickets = client.search_tickets_by_timeframe(
                start_date=start_date,
                end_date=end_date,
                date_field=date_field,
                ticket_priorities=priorities,
                organization_id=organization_id
            )
        else:
            # Organization-only mode (backward compatibility)
            logging.info(f"Fetching tickets for organization ID: {organization_id}...")
            tickets = client.search_tickets_by_organization(organization_id)

        logging.info(f"Found {len(tickets)} tickets.")

        # Enrich with full event history if requested
        if fetch_history:
            logging.info("Fetching full event history for each ticket (this may take a while)...")
            tickets = client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=True)
        else:
            logging.info("Skipping full event history. Only ticket metadata will be exported.")

        # Write to file based on format
        if output_format == "csv":
            # CSV export - tickets only (metadata not included in CSV)
            export_to_csv(tickets, output_path)
        else:
            # JSON export - with metadata if timeframe mode
            if has_timeframe:
                output_data = {
                    "export_metadata": {
                        "export_date": datetime.now().isoformat(),
                        "start_date": start_date,
                        "end_date": end_date,
                        "date_field": date_field,
                        "ticket_priorities": priorities,
                        "priority_field_id": PRIORITY_FIELD_ID if priorities else None,
                        "organization_id": organization_id,
                        "total_tickets": len(tickets),
                        "includes_history": fetch_history,
                        "format": "json"
                    },
                    "tickets": tickets
                }
            else:
                # Backward compatibility: output tickets directly for org-only mode
                output_data = tickets

            # Write JSON
            with open(output_path, "w", encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            logging.info(f"Exported {len(tickets)} tickets to {output_path}")

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP Error during Zendesk API request: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Connection Error during Zendesk API request: {e}")
        sys.exit(1)
    except requests.exceptions.Timeout as e:
        logging.error(f"Timeout Error during Zendesk API request: {e}")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"General Request Error during Zendesk API request: {e}")
        sys.exit(1)
    except IOError as e:
        logging.error(f"Error writing to output file {output_path}: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
