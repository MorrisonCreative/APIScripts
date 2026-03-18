
import unittest
from unittest.mock import patch, MagicMock
import requests
import json
import os
import sys


from zendesk_exporter import (
    ZendeskAPIClient,
    validate_and_parse_date,
    validate_priorities,
    validate_date_range,
    validate_date_field,
    build_search_query,
    generate_filename,
    detect_credential_sets,
    normalize_credential_set,
    load_credentials,
    flatten_ticket_for_csv,
    export_to_csv,
    calculate_priority_breakdown,
    log_export_summary
)

class TestZendeskAPIClient(unittest.TestCase):

    def setUp(self):
        self.subdomain = "testcompany"
        self.email = "test@example.com"
        self.api_token = "test_token"
        self.client = ZendeskAPIClient(self.subdomain, self.email, self.api_token)

    def test_init(self):
        self.assertEqual(self.client.base_url, "https://testcompany.zendesk.com/api/v2")
        self.assertEqual(self.client.auth, ("test@example.com/token", "test_token"))

    @patch('requests.get')
    def test_get_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.client.get("/test.json", params={"param": "value"})

        mock_get.assert_called_once_with(
            "https://testcompany.zendesk.com/api/v2/test.json",
            auth=("test@example.com/token", "test_token"),
            params={"param": "value"}
        )
        mock_response.raise_for_status.assert_called_once()
        self.assertEqual(result, {"key": "value"})

    @patch('requests.get')
    def test_get_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.client.get("/nonexistent.json")

        mock_response.raise_for_status.assert_called_once()

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_organization_single_page(self, mock_get):
        organization_id = "12345"
        mock_get.return_value = {
            "results": [{"id": 1, "subject": "Ticket 1"}]
        }

        tickets = self.client.search_tickets_by_organization(organization_id)

        mock_get.assert_called_once_with(
            "/search.json",
            params={"query": f"type:ticket organization_id:{organization_id}", "per_page": 100, "page": 1}
        )
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]["id"], 1)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_organization_no_results(self, mock_get):
        organization_id = "99999"
        mock_get.return_value = {
            "results": []
        }

        tickets = self.client.search_tickets_by_organization(organization_id)

        mock_get.assert_called_once()
        self.assertEqual(len(tickets), 0)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_organization_exactly_page_size(self, mock_get):
        organization_id = "55555"
        # Exactly 100 results (full page) - will fetch page 2 which returns empty
        mock_get.side_effect = [
            {"results": [{"id": i, "subject": f"Ticket {i}"} for i in range(1, 101)]},
            {"results": []}  # Page 2 is empty
        ]

        tickets = self.client.search_tickets_by_organization(organization_id)

        # Should call twice: once for page 1 (100 items), once for page 2 (0 items)
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(tickets), 100)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_organization_multi_page(self, mock_get):
        organization_id = "67890"

        # First page response (full page = 100 results)
        mock_get.side_effect = [
            {
                "results": [{"id": i, "subject": f"Ticket {i}"} for i in range(1, 101)]
            },
            # Second page response (partial page)
            {
                "results": [{"id": 101, "subject": "Ticket 101"}, {"id": 102, "subject": "Ticket 102"}]
            }
        ]

        tickets = self.client.search_tickets_by_organization(organization_id)

        self.assertEqual(mock_get.call_count, 2)
        mock_get.assert_any_call(
            "/search.json",
            params={"query": f"type:ticket organization_id:{organization_id}", "per_page": 100, "page": 1}
        )
        mock_get.assert_any_call(
            "/search.json",
            params={"query": f"type:ticket organization_id:{organization_id}", "per_page": 100, "page": 2}
        )
        self.assertEqual(len(tickets), 102)
        self.assertEqual(tickets[0]["id"], 1)
        self.assertEqual(tickets[-1]["id"], 102)

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_audits_single_page(self, mock_get):
        ticket_id = 123
        mock_get.return_value = {
            "audits": [{"id": 1, "created_at": "2024-01-01"}],
            "next_page": None
        }

        audits = self.client.get_ticket_audits(ticket_id)

        mock_get.assert_called_once_with(f"/tickets/{ticket_id}/audits.json", params=None)
        self.assertEqual(len(audits), 1)
        self.assertEqual(audits[0]["id"], 1)

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_audits_multi_page(self, mock_get):
        ticket_id = 456
        base_url = "https://testcompany.zendesk.com/api/v2"

        mock_get.side_effect = [
            {
                "audits": [{"id": 1, "created_at": "2024-01-01"}],
                "next_page": f"{base_url}/tickets/{ticket_id}/audits.json?page=2"
            },
            {
                "audits": [{"id": 2, "created_at": "2024-01-02"}],
                "next_page": None
            }
        ]

        audits = self.client.get_ticket_audits(ticket_id)

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(audits), 2)
        self.assertEqual(audits[0]["id"], 1)
        self.assertEqual(audits[1]["id"], 2)

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_comments_single_page(self, mock_get):
        ticket_id = 789
        mock_get.return_value = {
            "comments": [{"id": 1, "body": "Test comment"}],
            "next_page": None
        }

        comments = self.client.get_ticket_comments(ticket_id)

        mock_get.assert_called_once_with(f"/tickets/{ticket_id}/comments.json", params=None)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["body"], "Test comment")

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_comments_multi_page(self, mock_get):
        ticket_id = 999
        base_url = "https://testcompany.zendesk.com/api/v2"

        mock_get.side_effect = [
            {
                "comments": [{"id": 1, "body": "Comment 1"}],
                "next_page": f"{base_url}/tickets/{ticket_id}/comments.json?page=2"
            },
            {
                "comments": [{"id": 2, "body": "Comment 2"}],
                "next_page": None
            }
        ]

        comments = self.client.get_ticket_comments(ticket_id)

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(comments), 2)

    @patch('time.sleep')
    @patch.object(ZendeskAPIClient, 'get_ticket_comments')
    @patch.object(ZendeskAPIClient, 'get_ticket_audits')
    def test_enrich_tickets_with_history(self, mock_audits, mock_comments, mock_sleep):
        mock_audits.return_value = [{"id": 1, "created_at": "2024-01-01"}]
        mock_comments.return_value = [{"id": 1, "body": "Test comment"}]

        tickets = [
            {"id": 100, "subject": "Test Ticket 1"},
            {"id": 200, "subject": "Test Ticket 2"}
        ]

        enriched = self.client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=True)

        self.assertEqual(len(enriched), 2)
        self.assertIn("audits", enriched[0])
        self.assertIn("comments", enriched[0])
        self.assertEqual(mock_audits.call_count, 2)
        self.assertEqual(mock_comments.call_count, 2)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('time.sleep')
    @patch.object(ZendeskAPIClient, 'get_ticket_audits')
    def test_enrich_tickets_audits_only(self, mock_audits, mock_sleep):
        mock_audits.return_value = [{"id": 1}]

        tickets = [{"id": 100, "subject": "Test"}]
        enriched = self.client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=False)

        self.assertIn("audits", enriched[0])
        self.assertNotIn("comments", enriched[0])
        mock_audits.assert_called_once()

    @patch('time.sleep')
    @patch.object(ZendeskAPIClient, 'get_ticket_audits')
    def test_enrich_tickets_handles_http_errors(self, mock_audits, mock_sleep):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_audits.side_effect = requests.exceptions.HTTPError(response=mock_response)

        tickets = [{"id": 100, "subject": "Test"}]
        enriched = self.client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=False)

        # Should still return the ticket even if enrichment fails
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["id"], 100)

    @patch('time.sleep')
    @patch.object(ZendeskAPIClient, 'get_ticket_audits')
    def test_enrich_tickets_handles_generic_errors(self, mock_audits, mock_sleep):
        mock_audits.side_effect = Exception("Unexpected error")

        tickets = [{"id": 200, "subject": "Test 2"}]
        enriched = self.client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=False)

        # Should still return the ticket even if enrichment fails with generic exception
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["id"], 200)

    @patch('time.sleep')
    @patch.object(ZendeskAPIClient, 'get_ticket_comments')
    @patch.object(ZendeskAPIClient, 'get_ticket_audits')
    def test_enrich_tickets_with_empty_audits_and_comments(self, mock_audits, mock_comments, mock_sleep):
        mock_audits.return_value = []
        mock_comments.return_value = []

        tickets = [{"id": 300, "subject": "Empty History"}]
        enriched = self.client.enrich_tickets_with_history(tickets, include_audits=True, include_comments=True)

        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["audits"], [])
        self.assertEqual(enriched[0]["comments"], [])

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_audits_empty(self, mock_get):
        ticket_id = 999
        mock_get.return_value = {
            "audits": [],
            "next_page": None
        }

        audits = self.client.get_ticket_audits(ticket_id)

        self.assertEqual(len(audits), 0)

    @patch.object(ZendeskAPIClient, 'get')
    def test_get_ticket_comments_empty(self, mock_get):
        ticket_id = 888
        mock_get.return_value = {
            "comments": [],
            "next_page": None
        }

        comments = self.client.get_ticket_comments(ticket_id)

        self.assertEqual(len(comments), 0)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_timeframe_basic(self, mock_get):
        mock_get.return_value = {
            "results": [{"id": 1, "subject": "Ticket 1"}]
        }

        tickets = self.client.search_tickets_by_timeframe("2024-01-01", "2024-01-31")

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertIn("type:ticket", call_args[1]["params"]["query"])
        self.assertIn("created>=2024-01-01", call_args[1]["params"]["query"])
        self.assertIn("created<=2024-01-31", call_args[1]["params"]["query"])
        self.assertEqual(len(tickets), 1)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_timeframe_with_priorities(self, mock_get):
        mock_get.return_value = {"results": []}

        self.client.search_tickets_by_timeframe(
            "2024-01-01", "2024-01-31",
            ticket_priorities=["P1", "P2"]
        )

        call_args = mock_get.call_args
        query = call_args[1]["params"]["query"]
        self.assertIn("custom_field_360047533253:P1", query)
        self.assertIn("custom_field_360047533253:P2", query)

    @patch.object(ZendeskAPIClient, 'get')
    def test_search_tickets_by_timeframe_with_org(self, mock_get):
        mock_get.return_value = {"results": []}

        self.client.search_tickets_by_timeframe(
            "2024-01-01", "2024-01-31",
            organization_id="12345"
        )

        call_args = mock_get.call_args
        query = call_args[1]["params"]["query"]
        self.assertIn("organization_id:12345", query)


class TestValidationFunctions(unittest.TestCase):

    def test_validate_and_parse_date_valid_formats(self):
        self.assertEqual(validate_and_parse_date("2024-01-15"), "2024-01-15")
        self.assertEqual(validate_and_parse_date("2024-12-31"), "2024-12-31")

    def test_validate_and_parse_date_iso_format(self):
        result = validate_and_parse_date("2024-01-15T10:30:00Z")
        self.assertEqual(result, "2024-01-15")

    def test_validate_and_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            validate_and_parse_date("01/15/2024")
        with self.assertRaises(ValueError):
            validate_and_parse_date("invalid")

    def test_validate_and_parse_date_none(self):
        self.assertIsNone(validate_and_parse_date(None))
        self.assertIsNone(validate_and_parse_date(""))

    def test_validate_priorities_single(self):
        self.assertEqual(validate_priorities("P1"), ["P1"])
        self.assertEqual(validate_priorities("p2"), ["P2"])

    def test_validate_priorities_multiple(self):
        result = validate_priorities("P1,P2,P3")
        self.assertEqual(result, ["P1", "P2", "P3"])

    def test_validate_priorities_case_insensitive(self):
        result = validate_priorities("p1,P2,p3")
        self.assertEqual(result, ["P1", "P2", "P3"])

    def test_validate_priorities_invalid(self):
        with self.assertRaises(ValueError):
            validate_priorities("P5")
        with self.assertRaises(ValueError):
            validate_priorities("P1,HIGH")

    def test_validate_priorities_none(self):
        self.assertIsNone(validate_priorities(None))
        self.assertIsNone(validate_priorities(""))

    def test_validate_date_range_valid(self):
        self.assertTrue(validate_date_range("2024-01-01", "2024-12-31"))
        self.assertTrue(validate_date_range("2024-01-01", "2024-01-01"))

    def test_validate_date_range_invalid(self):
        with self.assertRaises(ValueError):
            validate_date_range("2024-12-31", "2024-01-01")

    def test_validate_date_field_valid(self):
        self.assertTrue(validate_date_field("created"))
        self.assertTrue(validate_date_field("updated"))
        self.assertTrue(validate_date_field("solved"))

    def test_validate_date_field_invalid(self):
        with self.assertRaises(ValueError):
            validate_date_field("invalid")


class TestQueryBuilder(unittest.TestCase):

    def test_build_query_organization_only(self):
        query = build_search_query(organization_id="12345")
        self.assertIn("type:ticket", query)
        self.assertIn("organization_id:12345", query)

    def test_build_query_timeframe_only(self):
        query = build_search_query(start_date="2024-01-01", end_date="2024-01-31")
        self.assertIn("type:ticket", query)
        self.assertIn("created>=2024-01-01", query)
        self.assertIn("created<=2024-01-31", query)

    def test_build_query_with_date_field(self):
        query = build_search_query(
            start_date="2024-01-01",
            end_date="2024-01-31",
            date_field="updated"
        )
        self.assertIn("updated>=2024-01-01", query)
        self.assertIn("updated<=2024-01-31", query)

    def test_build_query_with_priorities(self):
        query = build_search_query(
            start_date="2024-01-01",
            end_date="2024-01-31",
            ticket_priorities=["P1", "P2"]
        )
        self.assertIn("custom_field_360047533253:P1", query)
        self.assertIn("custom_field_360047533253:P2", query)

    def test_build_query_combined(self):
        query = build_search_query(
            organization_id="12345",
            start_date="2024-01-01",
            end_date="2024-01-31",
            date_field="created",
            ticket_priorities=["P1"]
        )
        self.assertIn("type:ticket", query)
        self.assertIn("organization_id:12345", query)
        self.assertIn("created>=2024-01-01", query)
        self.assertIn("created<=2024-01-31", query)
        self.assertIn("custom_field_360047533253:P1", query)


class TestFilenameGeneration(unittest.TestCase):

    def test_generate_filename_timeframe_only(self):
        filename = generate_filename(start_date="2024-01-01", end_date="2024-12-31")
        self.assertIn("tickets_2024-01-01_to_2024-12-31", filename)
        self.assertTrue(filename.endswith(".json"))

    def test_generate_filename_with_priorities(self):
        filename = generate_filename(
            start_date="2024-01-01",
            end_date="2024-12-31",
            priorities=["P1", "P2"]
        )
        self.assertIn("2024-01-01_to_2024-12-31", filename)
        self.assertIn("P1-P2", filename)

    def test_generate_filename_with_org(self):
        filename = generate_filename(organization_id="12345")
        self.assertIn("org_12345", filename)

    def test_generate_filename_combined(self):
        filename = generate_filename(
            start_date="2024-01-01",
            end_date="2024-01-31",
            priorities=["P1"],
            organization_id="12345"
        )
        self.assertIn("2024-01-01_to_2024-01-31", filename)
        self.assertIn("P1", filename)
        self.assertIn("org_12345", filename)

    def test_generate_filename_csv_format(self):
        filename = generate_filename(start_date="2024-01-01", end_date="2024-01-31", file_format="csv")
        self.assertTrue(filename.endswith(".csv"))

    def test_generate_filename_json_format(self):
        filename = generate_filename(start_date="2024-01-01", end_date="2024-01-31", file_format="json")
        self.assertTrue(filename.endswith(".json"))


class TestCSVExport(unittest.TestCase):

    def test_flatten_ticket_basic_fields(self):
        ticket = {
            'id': 12345,
            'subject': 'Test ticket',
            'status': 'open',
            'priority': 'high',
            'created_at': '2024-01-15T10:30:00Z'
        }
        flattened = flatten_ticket_for_csv(ticket)
        self.assertEqual(flattened['id'], 12345)
        self.assertEqual(flattened['subject'], 'Test ticket')
        self.assertEqual(flattened['status'], 'open')

    def test_flatten_ticket_with_custom_priority(self):
        ticket = {
            'id': 12345,
            'subject': 'Test',
            'custom_fields': [
                {'id': 360047533253, 'value': 'P1'}
            ]
        }
        flattened = flatten_ticket_for_csv(ticket)
        self.assertEqual(flattened['ticket_priority'], 'P1')

    def test_flatten_ticket_with_tags(self):
        ticket = {
            'id': 12345,
            'tags': ['urgent', 'customer', 'billing']
        }
        flattened = flatten_ticket_for_csv(ticket)
        self.assertEqual(flattened['tags'], 'urgent,customer,billing')

    def test_flatten_ticket_with_history_counts(self):
        ticket = {
            'id': 12345,
            'audits': [{'id': 1}, {'id': 2}, {'id': 3}],
            'comments': [{'id': 1}, {'id': 2}]
        }
        flattened = flatten_ticket_for_csv(ticket)
        self.assertEqual(flattened['audit_count'], 3)
        self.assertEqual(flattened['comment_count'], 2)

    def test_export_to_csv_creates_file(self):
        import tempfile
        import csv as csv_module

        tickets = [
            {'id': 1, 'subject': 'Ticket 1', 'status': 'open'},
            {'id': 2, 'subject': 'Ticket 2', 'status': 'closed'}
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            export_to_csv(tickets, temp_path)

            # Verify file was created and has content
            with open(temp_path, 'r', encoding='utf-8') as f:
                reader = csv_module.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]['id'], '1')
                self.assertEqual(rows[0]['subject'], 'Ticket 1')
        finally:
            os.remove(temp_path)

    def test_export_to_csv_empty_tickets(self):
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name

        try:
            export_to_csv([], temp_path)

            # Verify file was created with headers only
            with open(temp_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                self.assertEqual(len(lines), 1)  # Header only
        finally:
            os.remove(temp_path)


class TestCredentialManagement(unittest.TestCase):

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1'}, clear=True)
    def test_detect_credential_sets_set1_only(self):
        set1_complete, set2_complete, set1, set2 = detect_credential_sets()
        self.assertTrue(set1_complete)
        self.assertFalse(set2_complete)
        self.assertEqual(set1['subdomain'], 'test1')

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'}, clear=True)
    def test_detect_credential_sets_set2_only(self):
        set1_complete, set2_complete, set1, set2 = detect_credential_sets()
        self.assertFalse(set1_complete)
        self.assertTrue(set2_complete)
        self.assertEqual(set2['subdomain'], 'test2')

    @patch.dict(os.environ, {
        'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1',
        'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'
    }, clear=True)
    def test_detect_credential_sets_both(self):
        set1_complete, set2_complete, set1, set2 = detect_credential_sets()
        self.assertTrue(set1_complete)
        self.assertTrue(set2_complete)

    @patch.dict(os.environ, {}, clear=True)
    def test_detect_credential_sets_none(self):
        set1_complete, set2_complete, set1, set2 = detect_credential_sets()
        self.assertFalse(set1_complete)
        self.assertFalse(set2_complete)

    def test_normalize_credential_set_valid(self):
        self.assertEqual(normalize_credential_set(1), 1)
        self.assertEqual(normalize_credential_set('1'), 1)
        self.assertEqual(normalize_credential_set('primary'), 1)
        self.assertEqual(normalize_credential_set('first'), 1)
        self.assertEqual(normalize_credential_set(2), 2)
        self.assertEqual(normalize_credential_set('2'), 2)
        self.assertEqual(normalize_credential_set('secondary'), 2)
        self.assertIsNone(normalize_credential_set(None))

    def test_normalize_credential_set_invalid(self):
        with self.assertRaises(ValueError):
            normalize_credential_set('3')
        with self.assertRaises(ValueError):
            normalize_credential_set('invalid')

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1'}, clear=True)
    def test_load_credentials_auto_select_set1(self):
        subdomain, email, token, selected = load_credentials(None)
        self.assertEqual(subdomain, 'test1')
        self.assertEqual(email, 'test1@example.com')
        self.assertEqual(token, 'token1')
        self.assertEqual(selected, 1)

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'}, clear=True)
    def test_load_credentials_auto_select_set2(self):
        subdomain, email, token, selected = load_credentials(None)
        self.assertEqual(subdomain, 'test2')
        self.assertEqual(email, 'test2@example.com')
        self.assertEqual(token, 'token2')
        self.assertEqual(selected, 2)

    @patch.dict(os.environ, {
        'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1',
        'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'
    }, clear=True)
    def test_load_credentials_explicit_set1(self):
        subdomain, email, token, selected = load_credentials(1)
        self.assertEqual(subdomain, 'test1')
        self.assertEqual(selected, 1)

    @patch.dict(os.environ, {
        'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1',
        'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'
    }, clear=True)
    def test_load_credentials_explicit_set2(self):
        subdomain, email, token, selected = load_credentials(2)
        self.assertEqual(subdomain, 'test2')
        self.assertEqual(selected, 2)

    @patch.dict(os.environ, {
        'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com', 'ZENDESK_API_TOKEN': 'token1',
        'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com', 'ZENDESK_API_TOKEN_2': 'token2'
    }, clear=True)
    def test_load_credentials_both_no_selection(self):
        with self.assertRaises(SystemExit):
            load_credentials(None)

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN': 'test1', 'ZENDESK_EMAIL': 'test1@example.com'}, clear=True)
    def test_load_credentials_set1_incomplete(self):
        with self.assertRaises(SystemExit):
            load_credentials(1)

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN_2': 'test2', 'ZENDESK_EMAIL_2': 'test2@example.com'}, clear=True)
    def test_load_credentials_set2_incomplete(self):
        with self.assertRaises(SystemExit):
            load_credentials(2)

    @patch.dict(os.environ, {}, clear=True)
    def test_load_credentials_none_configured(self):
        with self.assertRaises(SystemExit):
            load_credentials(None)

    @patch.dict(os.environ, {'ZENDESK_SUBDOMAIN': 'original', 'ZENDESK_EMAIL': 'old@example.com', 'ZENDESK_API_TOKEN': 'oldtoken'}, clear=True)
    def test_backward_compatibility(self):
        # Test that existing single-set configs work unchanged
        subdomain, email, token, selected = load_credentials()
        self.assertEqual(subdomain, 'original')
        self.assertEqual(email, 'old@example.com')
        self.assertEqual(token, 'oldtoken')
        self.assertEqual(selected, 1)


class TestPriorityBreakdown(unittest.TestCase):
    """Test priority breakdown calculation and summary logging"""

    def test_calculate_priority_breakdown_all_priorities(self):
        """Test breakdown with all priority levels present"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 3, 'custom_fields': [{'id': 360047533253, 'value': 'P2'}]},
            {'id': 4, 'custom_fields': [{'id': 360047533253, 'value': 'P3'}]},
            {'id': 5, 'custom_fields': [{'id': 360047533253, 'value': 'P3'}]},
            {'id': 6, 'custom_fields': [{'id': 360047533253, 'value': 'P3'}]},
            {'id': 7, 'custom_fields': [{'id': 360047533253, 'value': 'P4'}]},
        ]

        breakdown = calculate_priority_breakdown(tickets)

        self.assertEqual(breakdown['P1'], 2)
        self.assertEqual(breakdown['P2'], 1)
        self.assertEqual(breakdown['P3'], 3)
        self.assertEqual(breakdown['P4'], 1)
        self.assertEqual(breakdown['unassigned'], 0)

    def test_calculate_priority_breakdown_with_unassigned(self):
        """Test breakdown with tickets missing priority field"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': [{'id': 999999999, 'value': 'other'}]},  # Different field
            {'id': 3, 'custom_fields': []},  # No custom fields
            {'id': 4, 'custom_fields': [{'id': 360047533253, 'value': ''}]},  # Empty value
            {'id': 5, 'custom_fields': [{'id': 360047533253, 'value': 'P2'}]},
        ]

        breakdown = calculate_priority_breakdown(tickets)

        self.assertEqual(breakdown['P1'], 1)
        self.assertEqual(breakdown['P2'], 1)
        self.assertEqual(breakdown['P3'], 0)
        self.assertEqual(breakdown['P4'], 0)
        self.assertEqual(breakdown['unassigned'], 3)

    def test_calculate_priority_breakdown_empty_tickets(self):
        """Test breakdown with no tickets"""
        tickets = []

        breakdown = calculate_priority_breakdown(tickets)

        self.assertEqual(breakdown['P1'], 0)
        self.assertEqual(breakdown['P2'], 0)
        self.assertEqual(breakdown['P3'], 0)
        self.assertEqual(breakdown['P4'], 0)
        self.assertEqual(breakdown['unassigned'], 0)

    def test_calculate_priority_breakdown_case_sensitive(self):
        """Test that priority values match exactly (case-sensitive)"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': [{'id': 360047533253, 'value': 'p1'}]},  # lowercase
            {'id': 3, 'custom_fields': [{'id': 360047533253, 'value': 'P2'}]},
        ]

        breakdown = calculate_priority_breakdown(tickets)

        self.assertEqual(breakdown['P1'], 1)  # Only exact match counts
        self.assertEqual(breakdown['P2'], 1)
        self.assertEqual(breakdown['unassigned'], 1)  # lowercase 'p1' is unassigned

    def test_calculate_priority_breakdown_only_p1(self):
        """Test breakdown with only P1 tickets"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 3, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
        ]

        breakdown = calculate_priority_breakdown(tickets)

        self.assertEqual(breakdown['P1'], 3)
        self.assertEqual(breakdown['P2'], 0)
        self.assertEqual(breakdown['P3'], 0)
        self.assertEqual(breakdown['P4'], 0)
        self.assertEqual(breakdown['unassigned'], 0)

    def test_log_export_summary_with_tickets(self):
        """Test that summary logging doesn't crash with various breakdowns"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': [{'id': 360047533253, 'value': 'P2'}]},
        ]
        breakdown = {'P1': 1, 'P2': 1, 'P3': 0, 'P4': 0, 'unassigned': 0}

        # Should not raise any exceptions
        try:
            log_export_summary(tickets, breakdown)
        except Exception as e:
            self.fail(f"log_export_summary raised an exception: {e}")

    def test_log_export_summary_empty(self):
        """Test summary logging with no tickets"""
        tickets = []
        breakdown = {'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0, 'unassigned': 0}

        # Should not raise any exceptions
        try:
            log_export_summary(tickets, breakdown)
        except Exception as e:
            self.fail(f"log_export_summary raised an exception: {e}")

    def test_log_export_summary_with_unassigned(self):
        """Test summary logging with unassigned tickets"""
        tickets = [
            {'id': 1, 'custom_fields': [{'id': 360047533253, 'value': 'P1'}]},
            {'id': 2, 'custom_fields': []},
            {'id': 3, 'custom_fields': []},
        ]
        breakdown = {'P1': 1, 'P2': 0, 'P3': 0, 'P4': 0, 'unassigned': 2}

        # Should not raise any exceptions
        try:
            log_export_summary(tickets, breakdown)
        except Exception as e:
            self.fail(f"log_export_summary raised an exception: {e}")


if __name__ == '__main__':
    unittest.main()
