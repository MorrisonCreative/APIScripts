#!/usr/bin/env python3
"""
Simple script to export all end users from Zendesk
"""

import requests
import json

# Zendesk Configuration
ZENDESK_SUBDOMAIN = "<SUBDOMAIN>"  # Replace with your Zendesk subdomain
ZENDESK_EMAIL = "<EMAIL>"  # Replace with your Zendesk email
ZENDESK_API_TOKEN = "<TOKEN>"  # Replace with your API token

# API endpoint
BASE_URL = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com"
ENDPOINT = "/api/v2/users.json?role=end-user"

def export_end_users():
    """Export all end users from Zendesk"""
    all_users = []
    url = BASE_URL + ENDPOINT

    print("Fetching end users from Zendesk...")

    while url:
        # Make API request
        response = requests.get(
            url,
            auth=(f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN)
        )

        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break

        data = response.json()
        users = data.get('users', [])
        all_users.extend(users)

        print(f"Fetched {len(users)} users... (Total: {len(all_users)})")

        # Get next page URL (Zendesk uses cursor-based pagination)
        url = data.get('next_page')

    # Save to JSON file
    output_file = "zendesk_end_users.json"
    with open(output_file, 'w') as f:
        json.dump(all_users, f, indent=2)

    print(f"\n✓ Successfully exported {len(all_users)} end users to {output_file}")

if __name__ == "__main__":
    export_end_users()
