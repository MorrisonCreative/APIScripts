#!/usr/bin/env python3
"""
Simple Zendesk Organization ID Exporter
Exports all organization IDs from Zendesk to a CSV file.
"""

import requests
import csv
import os
from requests.auth import HTTPBasicAuth

# Configuration - set these as environment variables or modify directly
ZENDESK_SUBDOMAIN = os.getenv('ZENDESK_SUBDOMAIN', 'your-subdomain')
ZENDESK_EMAIL = os.getenv('ZENDESK_EMAIL', 'your-email@example.com')
ZENDESK_API_TOKEN = os.getenv('ZENDESK_API_TOKEN', 'your-api-token')

# Output file
OUTPUT_FILE = 'zendesk_org_ids.csv'


def fetch_all_organizations():
    """Fetch all organizations from Zendesk API with pagination."""
    base_url = f'https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/organizations.json'
    auth = HTTPBasicAuth(f'{ZENDESK_EMAIL}/token', ZENDESK_API_TOKEN)

    all_org_ids = []
    url = base_url

    print("Fetching organizations from Zendesk...")

    while url:
        response = requests.get(url, auth=auth)

        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break

        data = response.json()
        organizations = data.get('organizations', [])

        # Extract org IDs
        for org in organizations:
            all_org_ids.append(org['id'])

        print(f"Fetched {len(organizations)} organizations... (Total: {len(all_org_ids)})")

        # Get next page URL
        url = data.get('next_page')

    return all_org_ids


def export_to_csv(org_ids, filename):
    """Export organization IDs to CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['organization_id'])  # Header

        for org_id in org_ids:
            writer.writerow([org_id])

    print(f"\n✓ Exported {len(org_ids)} organization IDs to {filename}")


def main():
    """Main execution function."""
    # Validate configuration
    if ZENDESK_SUBDOMAIN == 'your-subdomain' or ZENDESK_EMAIL == 'your-email@example.com':
        print("Please set your Zendesk credentials:")
        print("  export ZENDESK_SUBDOMAIN='your-subdomain'")
        print("  export ZENDESK_EMAIL='your-email@example.com'")
        print("  export ZENDESK_API_TOKEN='your-api-token'")
        return

    try:
        # Fetch organizations
        org_ids = fetch_all_organizations()

        if not org_ids:
            print("No organizations found or error occurred.")
            return

        # Export to CSV
        export_to_csv(org_ids, OUTPUT_FILE)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main()
