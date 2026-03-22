import datetime
import os
import unittest

import sendgrid
from sendgrid.helpers.endpoints.ip.unassigned import unassigned


class UnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.path = '{}{}'.format(
            os.path.abspath(
                os.path.dirname(__file__)), '/..')
        cls.sg = sendgrid.SendGridAPIClient()
        cls.devnull = open(os.devnull, 'w')

    def test_api_key_init(self):
        self.assertEqual(self.sg.api_key, os.environ.get('SENDGRID_API_KEY'))
        my_sendgrid = sendgrid.SendGridAPIClient(api_key="THISISMYKEY")
        self.assertEqual(my_sendgrid.api_key, "THISISMYKEY")

    def test_api_key_setter(self):
        sg_api_key_setter = sendgrid.SendGridAPIClient(api_key="THISISMYKEY")
        self.assertEqual(sg_api_key_setter.api_key, "THISISMYKEY")
        # Use api_key setter to change api key
        sg_api_key_setter.api_key = "THISISMYNEWAPIKEY"
        self.assertEqual(sg_api_key_setter.api_key, "THISISMYNEWAPIKEY")

    def test_impersonate_subuser_init(self):
        temp_subuser = 'abcxyz@this.is.a.test.subuser'
        sg_impersonate = sendgrid.SendGridAPIClient(
            impersonate_subuser=temp_subuser)
        self.assertEqual(sg_impersonate.impersonate_subuser, temp_subuser)

    def test_useragent(self):
        useragent = '{}{}{}'.format('sendgrid/', sendgrid.__version__, ';python')
        self.assertEqual(self.sg.useragent, useragent)

    def test_host(self):
        self.assertEqual(self.sg.host, 'https://api.sendgrid.com')

    def test_get_default_headers(self):
        headers = self.sg._default_headers
        self.assertIn('Authorization', headers)
        self.assertIn('User-Agent', headers)
        self.assertIn('Accept', headers)
        self.assertNotIn('On-Behalf-Of', headers)

        self.sg.impersonate_subuser = 'ladida@testsubuser.sendgrid'
        headers = self.sg._default_headers
        self.assertIn('Authorization', headers)
        self.assertIn('User-Agent', headers)
        self.assertIn('Accept', headers)
        self.assertIn('On-Behalf-Of', headers)

    def test_reset_request_headers(self):
        addl_headers = {
            'blah': 'test value',
            'blah2x': 'another test value',
        }
        self.sg.client.request_headers.update(addl_headers)
        self.assertIn('blah', self.sg.client.request_headers)
        self.assertIn('blah2x', self.sg.client.request_headers)

        self.sg.reset_request_headers()
        self.assertNotIn('blah', self.sg.client.request_headers)
        self.assertNotIn('blah2x', self.sg.client.request_headers)

        for k, v in self.sg._default_headers.items():
            self.assertEqual(v, self.sg.client.request_headers[k])

    def test_access_settings_activity_get(self):
        params = {'limit': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.access_settings.activity.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_access_settings_whitelist_post(self):
        data = {
            "ips": [
                {
                    "ip": "192.168.1.1"
                },
                {
                    "ip": "192.*.*.*"
                },
                {
                    "ip": "192.168.1.3/32"
                }
            ]
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.access_settings.whitelist.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_access_settings_whitelist_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.access_settings.whitelist.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_access_settings_whitelist_delete(self):
        data = {
            "ids": [
                1,
                2,
                3
            ]
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.access_settings.whitelist.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_access_settings_whitelist__rule_id__get(self):
        rule_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.access_settings.whitelist._(rule_id).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_access_settings_whitelist__rule_id__delete(self):
        rule_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.access_settings.whitelist._(rule_id).delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_alerts_post(self):
        data = {
            "email_to": "example@example.com",
            "frequency": "daily",
            "type": "stats_notification"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.alerts.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_alerts_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.alerts.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_alerts__alert_id__patch(self):
        data = {
            "email_to": "example@example.com"
        }
        alert_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.alerts._(alert_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_alerts__alert_id__get(self):
        alert_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.alerts._(alert_id).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_alerts__alert_id__delete(self):
        alert_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.alerts._(alert_id).delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_api_keys_post(self):
        data = {
            "name": "My API Key",
            "sample": "data",
            "scopes": [
                "mail.send",
                "alerts.create",
                "alerts.read"
            ]
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.api_keys.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_api_keys_get(self):
        params = {'limit': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.api_keys.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_api_keys__api_key_id__put(self):
        data = {
            "name": "A New Hope",
            "scopes": [
                "user.profile.read",
                "user.profile.update"
            ]
        }
        api_key_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.api_keys._(api_key_id).put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_api_keys__api_key_id__patch(self):
        data = {
            "name": "A New Hope"
        }
        api_key_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.api_keys._(api_key_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_api_keys__api_key_id__get(self):
        api_key_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.api_keys._(api_key_id).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_api_keys__api_key_id__delete(self):
        api_key_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.api_keys._(api_key_id).delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_asm_groups_post(self):
        data = {
            "description": "Suggestions for products our users might like.",
            "is_default": True,
            "name": "Product Suggestions"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.asm.groups.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_asm_groups_get(self):
        params = {'id': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.groups.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_groups__group_id__patch(self):
        data = {
            "description": "Suggestions for items our users might like.",
            "id": 103,
            "name": "Item Suggestions"
        }
        group_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.asm.groups._(group_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_asm_groups__group_id__get(self):
        group_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.groups._(group_id).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_groups__group_id__delete(self):
        group_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.asm.groups._(group_id).delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_asm_groups__group_id__suppressions_post(self):
        data = {
            "recipient_emails": [
                "test1@example.com",
                "test2@example.com"
            ]
        }
        group_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.asm.groups._(group_id).suppressions.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_asm_groups__group_id__suppressions_get(self):
        group_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.groups._(group_id).suppressions.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_groups__group_id__suppressions_search_post(self):
        data = {
            "recipient_emails": [
                "exists1@example.com",
                "exists2@example.com",
                "doesnotexists@example.com"
            ]
        }
        group_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.groups._(
            group_id).suppressions.search.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_groups__group_id__suppressions__email__delete(self):
        group_id = "test_url_param"
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.asm.groups._(group_id).suppressions._(
            email).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_asm_suppressions_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.suppressions.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_suppressions_global_post(self):
        data = {
            "recipient_emails": [
                "test1@example.com",
                "test2@example.com"
            ]
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.asm.suppressions._("global").post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_asm_suppressions_global__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.suppressions._("global")._(
            email).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_asm_suppressions_global__email__delete(self):
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.asm.suppressions._("global")._(
            email).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_asm_suppressions__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.asm.suppressions._(email).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_browsers_stats_get(self):
        params = {'end_date': '2016-04-01', 'aggregated_by': 'day',
                  'browsers': 'test_string', 'limit': 'test_string',
                  'offset': 'test_string', 'start_date': '2016-01-01'}
        headers = {'X-Mock': 200}
        response = self.sg.client.browsers.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns_post(self):
        data = {
            "categories": [
                "spring line"
            ],
            "custom_unsubscribe_url": "",
            "html_content": "<html><head><title></title></head><body>"
                            "<p>Check out our spring line!</p></body></html>",
            "ip_pool": "marketing",
            "list_ids": [
                110,
                124
            ],
            "plain_content": "Check out our spring line!",
            "segment_ids": [
                110
            ],
            "sender_id": 124451,
            "subject": "New Products for Spring!",
            "suppression_group_id": 42,
            "title": "March Newsletter"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.campaigns.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_campaigns_get(self):
        params = {'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.campaigns.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns__campaign_id__patch(self):
        data = {
            "categories": [
                "summer line"
            ],
            "html_content": "<html><head><title></title></head><body><p>"
                            "Check out our summer line!</p></body></html>",
            "plain_content": "Check out our summer line!",
            "subject": "New Products for Summer!",
            "title": "May Newsletter"
        }
        campaign_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.campaigns._(campaign_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns__campaign_id__get(self):
        campaign_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.campaigns._(campaign_id).get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns__campaign_id__delete(self):
        campaign_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.campaigns._(campaign_id).delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_campaigns__campaign_id__schedules_patch(self):
        data = {
            "send_at": 1489451436
        }
        campaign_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.campaigns._(campaign_id).schedules.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns__campaign_id__schedules_post(self):
        data = {
            "send_at": 1489771528
        }
        campaign_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.campaigns._(campaign_id).schedules.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_campaigns__campaign_id__schedules_get(self):
        campaign_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.campaigns._(campaign_id).schedules.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_campaigns__campaign_id__schedules_delete(self):
        campaign_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.campaigns._(campaign_id).schedules.delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_campaigns__campaign_id__schedules_now_post(self):
        campaign_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.campaigns._(campaign_id).schedules.now.post(
            request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_campaigns__campaign_id__schedules_test_post(self):
        data = {
            "to": "your.email@example.com"
        }
        campaign_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.campaigns._(campaign_id).schedules.test.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_categories_get(self):
        params = {'category': 'test_string', 'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.categories.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_categories_stats_get(self):
        params = {'end_date': '2016-04-01', 'aggregated_by': 'day',
                  'limit': 1, 'offset': 1, 'start_date': '2016-01-01',
                  'categories': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.categories.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_categories_stats_sums_get(self):
        params = {'end_date': '2016-04-01', 'aggregated_by': 'day',
                  'limit': 1, 'sort_by_metric': 'test_string', 'offset': 1,
                  'start_date': '2016-01-01', 'sort_by_direction': 'asc'}
        headers = {'X-Mock': 200}
        response = self.sg.client.categories.stats.sums.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_clients_stats_get(self):
        params = {'aggregated_by': 'day', 'start_date': '2016-01-01',
                  'end_date': '2016-04-01'}
        headers = {'X-Mock': 200}
        response = self.sg.client.clients.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_clients__client_type__stats_get(self):
        params = {'aggregated_by': 'day', 'start_date': '2016-01-01',
                  'end_date': '2016-04-01'}
        client_type = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.clients._(client_type).stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_custom_fields_post(self):
        data = {
            "name": "pet",
            "type": "text"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.custom_fields.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_custom_fields_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.custom_fields.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_custom_fields__custom_field_id__get(self):
        custom_field_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.custom_fields._(
            custom_field_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_custom_fields__custom_field_id__delete(self):
        custom_field_id = "test_url_param"
        headers = {'X-Mock': 202}
        response = self.sg.client.contactdb.custom_fields._(
            custom_field_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 202)

    def test_contactdb_lists_post(self):
        data = {
            "name": "your list name"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.lists.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_lists_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.lists.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_lists_delete(self):
        data = [
            1,
            2,
            3,
            4
        ]
        headers = {'X-Mock': 204}
        response = self.sg.client.contactdb.lists.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_contactdb_lists__list_id__patch(self):
        data = {
            "name": "newlistname"
        }
        params = {'list_id': 1}
        list_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.lists._(list_id).patch(
            request_body=data, query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_lists__list_id__get(self):
        params = {'list_id': 1}
        list_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.lists._(list_id).get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_lists__list_id__delete(self):
        params = {'delete_contacts': 'true'}
        list_id = "test_url_param"
        headers = {'X-Mock': 202}
        response = self.sg.client.contactdb.lists._(list_id).delete(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 202)

    def test_contactdb_lists__list_id__recipients_post(self):
        data = [
            "recipient_id1",
            "recipient_id2"
        ]
        list_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.lists._(list_id).recipients.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_lists__list_id__recipients_get(self):
        params = {'page': 1, 'page_size': 1}
        list_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.lists._(list_id).recipients.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_lists__list_id__recipients__recipient_id__post(self):
        list_id = "test_url_param"
        recipient_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.lists._(list_id).recipients._(
            recipient_id).post(request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_lists__list_id__recipients__recipient_id__delete(self):
        params = {'recipient_id': 1, 'list_id': 1}
        list_id = "test_url_param"
        recipient_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.contactdb.lists._(list_id).recipients._(
            recipient_id).delete(query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_contactdb_recipients_patch(self):
        data = [
            {
                "email": "jones@example.com",
                "first_name": "Guy",
                "last_name": "Jones"
            }
        ]
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.recipients.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_recipients_post(self):
        data = [
            {
                "age": 25,
                "email": "example@example.com",
                "first_name": "",
                "last_name": "User"
            },
            {
                "age": 25,
                "email": "example2@example.com",
                "first_name": "Example",
                "last_name": "User"
            }
        ]
        headers = {'X-Mock': 201}
        response = self.sg.client.contactdb.recipients.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_contactdb_recipients_get(self):
        params = {'page': 1, 'page_size': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients_delete(self):
        data = [
            "recipient_id1",
            "recipient_id2"
        ]
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients_billable_count_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients.billable_count.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients_count_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients.count.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients_search_get(self):
        params = {'{field_name}': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients.search.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients__recipient_id__get(self):
        recipient_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients._(
            recipient_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_recipients__recipient_id__delete(self):
        recipient_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.contactdb.recipients._(
            recipient_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_contactdb_recipients__recipient_id__lists_get(self):
        recipient_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.recipients._(
            recipient_id).lists.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_reserved_fields_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.reserved_fields.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_segments_post(self):
        data = {
            "conditions": [
                {
                    "and_or": "",
                    "field": "last_name",
                    "operator": "eq",
                    "value": "Miller"
                },
                {
                    "and_or": "and",
                    "field": "last_clicked",
                    "operator": "gt",
                    "value": "01/02/2015"
                },
                {
                    "and_or": "or",
                    "field": "clicks.campaign_identifier",
                    "operator": "eq",
                    "value": "513"
                }
            ],
            "list_id": 4,
            "name": "Last Name Miller"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.segments.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_segments_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.segments.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_segments__segment_id__patch(self):
        data = {
            "conditions": [
                {
                    "and_or": "",
                    "field": "last_name",
                    "operator": "eq",
                    "value": "Miller"
                }
            ],
            "list_id": 5,
            "name": "The Millers"
        }
        params = {'segment_id': 'test_string'}
        segment_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.segments._(segment_id).patch(
            request_body=data, query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_segments__segment_id__get(self):
        params = {'segment_id': 1}
        segment_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.segments._(segment_id).get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_contactdb_segments__segment_id__delete(self):
        params = {'delete_contacts': 'true'}
        segment_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.contactdb.segments._(segment_id).delete(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_contactdb_segments__segment_id__recipients_get(self):
        params = {'page': 1, 'page_size': 1}
        segment_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.contactdb.segments._(
            segment_id).recipients.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_devices_stats_get(self):
        params = {
            'aggregated_by': 'day',
            'limit': 1,
            'start_date': '2016-01-01',
            'end_date': '2016-04-01',
            'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.devices.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_geo_stats_get(self):
        params = {
            'end_date': '2016-04-01',
            'country': 'US',
            'aggregated_by': 'day',
            'limit': 1,
            'offset': 1,
            'start_date': '2016-01-01'}
        headers = {'X-Mock': 200}
        response = self.sg.client.geo.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_get(self):
        params = {
            'subuser': 'test_string',
            'ip': 'test_string',
            'limit': 1,
            'exclude_whitelabels': 'true',
            'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.get(
            query_params=params, request_headers=headers)
        data = response.body
        unused = unassigned(data)
        self.assertEqual(type(unused), list)
        self.assertEqual(response.status_code, 200)

    def test_ips_assigned_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.assigned.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_pools_post(self):
        data = {
            "name": "marketing"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.pools.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_pools_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.pools.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_pools__pool_name__put(self):
        data = {
            "name": "new_pool_name"
        }
        pool_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.pools._(pool_name).put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_pools__pool_name__get(self):
        pool_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.pools._(
            pool_name).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_pools__pool_name__delete(self):
        pool_name = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.ips.pools._(
            pool_name).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_ips_pools__pool_name__ips_post(self):
        data = {
            "ip": "0.0.0.0"
        }
        pool_name = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.ips.pools._(pool_name).ips.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_ips_pools__pool_name__ips__ip__delete(self):
        pool_name = "test_url_param"
        ip = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.ips.pools._(pool_name).ips._(
            ip).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_ips_warmup_post(self):
        data = {
            "ip": "0.0.0.0"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.warmup.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_warmup_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.warmup.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_warmup__ip_address__get(self):
        ip_address = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.ips.warmup._(
            ip_address).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_ips_warmup__ip_address__delete(self):
        ip_address = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.ips.warmup._(
            ip_address).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_ips__ip_address__get(self):
        ip_address = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.ips._(
            ip_address).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_batch_post(self):
        headers = {'X-Mock': 201}
        response = self.sg.client.mail.batch.post(request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_mail_batch__batch_id__get(self):
        batch_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.mail.batch._(
            batch_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_send_post(self):
        data = {
            "asm": {
                "group_id": 1,
                "groups_to_display": [
                    1,
                    2,
                    3
                ]
            },
            "attachments": [
                {
                    "content": "[BASE64 encoded content block here]",
                    "content_id": "ii_139db99fdb5c3704",
                    "disposition": "inline",
                    "filename": "file1.jpg",
                    "name": "file1",
                    "type": "jpg"
                }
            ],
            "batch_id": "[YOUR BATCH ID GOES HERE]",
            "categories": [
                "category1",
                "category2"
            ],
            "content": [
                {
                    "type": "text/html",
                    "value": "<html><p>Hello, world!</p><img "
                             "src=[CID GOES HERE]></img></html>"
                }
            ],
            "custom_args": {
                "New Argument 1": "New Value 1",
                "activationAttempt": "1",
                "customerAccountNumber": "[CUSTOMER ACCOUNT NUMBER GOES HERE]"
            },
            "from": {
                "email": "sam.smith@example.com",
                "name": "Sam Smith"
            },
            "headers": {},
            "ip_pool_name": "[YOUR POOL NAME GOES HERE]",
            "mail_settings": {
                "bcc": {
                    "email": "ben.doe@example.com",
                    "enable": True
                },
                "bypass_list_management": {
                    "enable": True
                },
                "footer": {
                    "enable": True,
                    "html": "<p>Thanks</br>The SendGrid Team</p>",
                    "text": "Thanks,/n The SendGrid Team"
                },
                "sandbox_mode": {
                    "enable": False
                },
                "spam_check": {
                    "enable": True,
                    "post_to_url": "http://example.com/compliance",
                    "threshold": 3
                }
            },
            "personalizations": [
                {
                    "bcc": [
                        {
                            "email": "sam.doe@example.com",
                            "name": "Sam Doe"
                        }
                    ],
                    "cc": [
                        {
                            "email": "jane.doe@example.com",
                            "name": "Jane Doe"
                        }
                    ],
                    "custom_args": {
                        "New Argument 1": "New Value 1",
                        "activationAttempt": "1",
                        "customerAccountNumber":
                            "[CUSTOMER ACCOUNT NUMBER GOES HERE]"
                    },
                    "headers": {
                        "X-Accept-Language": "en",
                        "X-Mailer": "MyApp"
                    },
                    "send_at": 1409348513,
                    "subject": "Hello, World!",
                    "substitutions": {
                        "id": "substitutions",
                        "type": "object"
                    },
                    "to": [
                        {
                            "email": "john.doe@example.com",
                            "name": "John Doe"
                        }
                    ]
                }
            ],
            "reply_to": {
                "email": "sam.smith@example.com",
                "name": "Sam Smith"
            },
            "sections": {
                "section": {
                    ":sectionName1": "section 1 text",
                    ":sectionName2": "section 2 text"
                }
            },
            "send_at": 1409348513,
            "subject": "Hello, World!",
            "template_id": "[YOUR TEMPLATE ID GOES HERE]",
            "tracking_settings": {
                "click_tracking": {
                    "enable": True,
                    "enable_text": True
                },
                "ganalytics": {
                    "enable": True,
                    "utm_campaign": "[NAME OF YOUR REFERRER SOURCE]",
                    "utm_content": "[USE THIS SPACE TO DIFFERENTIATE "
                                   "YOUR EMAIL FROM ADS]",
                    "utm_medium": "[NAME OF YOUR MARKETING MEDIUM e.g. email]",
                    "utm_name": "[NAME OF YOUR CAMPAIGN]",
                    "utm_term": "[IDENTIFY PAID KEYWORDS HERE]"
                },
                "open_tracking": {
                    "enable": True,
                    "substitution_tag": "%opentrack"
                },
                "subscription_tracking": {
                    "enable": True,
                    "html": "If you would like to unsubscribe and stop "
                            "receiving these emails <% clickhere %>.",
                    "substitution_tag": "<%click here%>",
                    "text": "If you would like to unsubscribe and stop "
                            "receiving these emails <% click here %>."
                }
            }
        }
        headers = {'X-Mock': 202}
        response = self.sg.client.mail.send.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 202)

    def test_mail_settings_get(self):
        params = {'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_address_whitelist_patch(self):
        data = {
            "enabled": True,
            "list": [
                "email1@example.com",
                "example.com"
            ]
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.address_whitelist.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_address_whitelist_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.address_whitelist.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_bcc_patch(self):
        data = {
            "email": "email@example.com",
            "enabled": False
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.bcc.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_bcc_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.bcc.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_bounce_purge_patch(self):
        data = {
            "enabled": True,
            "hard_bounces": 5,
            "soft_bounces": 5
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.bounce_purge.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_bounce_purge_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.bounce_purge.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_footer_patch(self):
        data = {
            "enabled": True,
            "html_content": "...",
            "plain_content": "..."
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.footer.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_footer_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.footer.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_forward_bounce_patch(self):
        data = {
            "email": "example@example.com",
            "enabled": True
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.forward_bounce.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_forward_bounce_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.forward_bounce.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_forward_spam_patch(self):
        data = {
            "email": "",
            "enabled": False
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.forward_spam.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_forward_spam_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.forward_spam.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_plain_content_patch(self):
        data = {
            "enabled": False
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.plain_content.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_plain_content_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.plain_content.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_spam_check_patch(self):
        data = {
            "enabled": True,
            "max_score": 5,
            "url": "url"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.spam_check.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_spam_check_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.spam_check.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_template_patch(self):
        data = {
            "enabled": True,
            "html_content": "<% body %>"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.template.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mail_settings_template_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.mail_settings.template.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_mailbox_providers_stats_get(self):
        params = {
            'end_date': '2016-04-01',
            'mailbox_providers': 'test_string',
            'aggregated_by': 'day',
            'limit': 1,
            'offset': 1,
            'start_date': '2016-01-01'}
        headers = {'X-Mock': 200}
        response = self.sg.client.mailbox_providers.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_partner_settings_get(self):
        params = {'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.partner_settings.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_partner_settings_new_relic_patch(self):
        data = {
            "enable_subuser_statistics": True,
            "enabled": True,
            "license_key": ""
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.partner_settings.new_relic.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_partner_settings_new_relic_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.partner_settings.new_relic.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_scopes_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.scopes.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_senders_post(self):
        data = {
            "address": "123 Elm St.",
            "address_2": "Apt. 456",
            "city": "Denver",
            "country": "United States",
            "from": {
                "email": "from@example.com",
                "name": "Example INC"
            },
            "nickname": "My Sender ID",
            "reply_to": {
                "email": "replyto@example.com",
                "name": "Example INC"
            },
            "state": "Colorado",
            "zip": "80202"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.senders.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_senders_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.senders.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_senders__sender_id__patch(self):
        data = {
            "address": "123 Elm St.",
            "address_2": "Apt. 456",
            "city": "Denver",
            "country": "United States",
            "from": {
                "email": "from@example.com",
                "name": "Example INC"
            },
            "nickname": "My Sender ID",
            "reply_to": {
                "email": "replyto@example.com",
                "name": "Example INC"
            },
            "state": "Colorado",
            "zip": "80202"
        }
        sender_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.senders._(sender_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_senders__sender_id__get(self):
        sender_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.senders._(
            sender_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_senders__sender_id__delete(self):
        sender_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.senders._(
            sender_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_senders__sender_id__resend_verification_post(self):
        sender_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.senders._(
            sender_id).resend_verification.post(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_stats_get(self):
        params = {
            'aggregated_by': 'day',
            'limit': 1,
            'start_date': '2016-01-01',
            'end_date': '2016-04-01',
            'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_post(self):
        data = {
            "email": "John@example.com",
            "ips": [
                "1.1.1.1",
                "2.2.2.2"
            ],
            "password": "johns_password",
            "username": "John@example.com"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_get(self):
        params = {'username': 'test_string', 'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_reputations_get(self):
        params = {'usernames': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.reputations.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_stats_get(self):
        params = {
            'end_date': '2016-04-01',
            'aggregated_by': 'day',
            'limit': 1,
            'offset': 1,
            'start_date': '2016-01-01',
            'subusers': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_stats_monthly_get(self):
        params = {
            'subuser': 'test_string',
            'limit': 1,
            'sort_by_metric': 'test_string',
            'offset': 1,
            'date': 'test_string',
            'sort_by_direction': 'asc'}
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.stats.monthly.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers_stats_sums_get(self):
        params = {
            'end_date': '2016-04-01',
            'aggregated_by': 'day',
            'limit': 1,
            'sort_by_metric': 'test_string',
            'offset': 1,
            'start_date': '2016-01-01',
            'sort_by_direction': 'asc'}
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers.stats.sums.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers__subuser_name__patch(self):
        data = {
            "disabled": False
        }
        subuser_name = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.subusers._(subuser_name).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_subusers__subuser_name__delete(self):
        subuser_name = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.subusers._(
            subuser_name).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_subusers__subuser_name__ips_put(self):
        data = [
            "127.0.0.1"
        ]
        subuser_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers._(subuser_name).ips.put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers__subuser_name__monitor_put(self):
        data = {
            "email": "example@example.com",
            "frequency": 500
        }
        subuser_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers._(subuser_name).monitor.put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers__subuser_name__monitor_post(self):
        data = {
            "email": "example@example.com",
            "frequency": 50000
        }
        subuser_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers._(subuser_name).monitor.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers__subuser_name__monitor_get(self):
        subuser_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers._(
            subuser_name).monitor.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_subusers__subuser_name__monitor_delete(self):
        subuser_name = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.subusers._(
            subuser_name).monitor.delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_subusers__subuser_name__stats_monthly_get(self):
        params = {
            'date': 'test_string',
            'sort_by_direction': 'asc',
            'limit': 1,
            'sort_by_metric': 'test_string',
            'offset': 1}
        subuser_name = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.subusers._(subuser_name).stats.monthly.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_blocks_get(self):
        params = {'start_time': 1, 'limit': 1, 'end_time': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.blocks.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_blocks_delete(self):
        data = {
            "delete_all": False,
            "emails": [
                "example1@example.com",
                "example2@example.com"
            ]
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.blocks.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_blocks__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.blocks._(
            email).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_blocks__email__delete(self):
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.blocks._(
            email).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_bounces_get(self):
        params = {'start_time': 1, 'end_time': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.bounces.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_bounces_delete(self):
        data = {
            "delete_all": True,
            "emails": [
                "example@example.com",
                "example2@example.com"
            ]
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.bounces.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_bounces__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.bounces._(
            email).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_bounces__email__delete(self):
        params = {'email_address': 'example@example.com'}
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.bounces._(email).delete(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_invalid_emails_get(self):
        params = {'start_time': 1, 'limit': 1, 'end_time': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.invalid_emails.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_invalid_emails_delete(self):
        data = {
            "delete_all": False,
            "emails": [
                "example1@example.com",
                "example2@example.com"
            ]
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.invalid_emails.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_invalid_emails__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.invalid_emails._(
            email).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_invalid_emails__email__delete(self):
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.invalid_emails._(
            email).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_spam_report__email__get(self):
        email = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.spam_reports._(
            email).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_spam_report__email__delete(self):
        email = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.spam_reports._(
            email).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_spam_reports_get(self):
        params = {'start_time': 1, 'limit': 1, 'end_time': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.spam_reports.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_suppression_spam_reports_delete(self):
        data = {
            "delete_all": False,
            "emails": [
                "example1@example.com",
                "example2@example.com"
            ]
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.suppression.spam_reports.delete(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_suppression_unsubscribes_get(self):
        params = {'start_time': 1, 'limit': 1, 'end_time': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.suppression.unsubscribes.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates_post(self):
        data = {
            "name": "example_name"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.templates.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_templates_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.templates.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates__template_id__patch(self):
        data = {
            "name": "new_example_name"
        }
        template_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.templates._(template_id).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates__template_id__get(self):
        template_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.templates._(
            template_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates__template_id__delete(self):
        template_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.templates._(
            template_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_templates__template_id__versions_post(self):
        data = {
            "active": 1,
            "html_content": "<%body%>",
            "name": "example_version_name",
            "plain_content": "<%body%>",
            "subject": "<%subject%>",
            "template_id": "ddb96bbc-9b92-425e-8979-99464621b543"
        }
        template_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.templates._(template_id).versions.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_templates__template_id__versions__version_id__patch(self):
        data = {
            "active": 1,
            "html_content": "<%body%>",
            "name": "updated_example_name",
            "plain_content": "<%body%>",
            "subject": "<%subject%>"
        }
        template_id = "test_url_param"
        version_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.templates._(template_id).versions._(
            version_id).patch(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates__template_id__versions__version_id__get(self):
        template_id = "test_url_param"
        version_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.templates._(template_id).versions._(
            version_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_templates__template_id__versions__version_id__delete(self):
        template_id = "test_url_param"
        version_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.templates._(template_id).versions._(
            version_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_templates__template_id__versions__version_id__activate_post(self):
        template_id = "test_url_param"
        version_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.templates._(template_id).versions._(
            version_id).activate.post(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_get(self):
        params = {'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_click_patch(self):
        data = {
            "enabled": True
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.click.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_click_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.click.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_google_analytics_patch(self):
        data = {
            "enabled": True,
            "utm_campaign": "website",
            "utm_content": "",
            "utm_medium": "email",
            "utm_source": "sendgrid.com",
            "utm_term": ""
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.google_analytics.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_google_analytics_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.google_analytics.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_open_patch(self):
        data = {
            "enabled": True
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.open.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_open_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.open.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_subscription_patch(self):
        data = {
            "enabled": True,
            "html_content": "html content",
            "landing": "landing page html",
            "plain_content": "text content",
            "replace": "replacement tag",
            "url": "url"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.subscription.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_tracking_settings_subscription_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.tracking_settings.subscription.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_account_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.account.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_credits_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.credits.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_email_put(self):
        data = {
            "email": "example@example.com"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.email.put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_email_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.email.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_password_put(self):
        data = {
            "new_password": "new_password",
            "old_password": "old_password"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.password.put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_profile_patch(self):
        data = {
            "city": "Orange",
            "first_name": "Example",
            "last_name": "User"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.profile.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_profile_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.profile.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_scheduled_sends_post(self):
        data = {
            "batch_id": "YOUR_BATCH_ID",
            "status": "pause"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.user.scheduled_sends.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_user_scheduled_sends_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.scheduled_sends.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_scheduled_sends__batch_id__patch(self):
        data = {
            "status": "pause"
        }
        batch_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.user.scheduled_sends._(
            batch_id).patch(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_user_scheduled_sends__batch_id__get(self):
        batch_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.user.scheduled_sends._(
            batch_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_scheduled_sends__batch_id__delete(self):
        batch_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.user.scheduled_sends._(
            batch_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_user_settings_enforced_tls_patch(self):
        data = {
            "require_tls": True,
            "require_valid_cert": False
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.settings.enforced_tls.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_settings_enforced_tls_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.settings.enforced_tls.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_username_put(self):
        data = {
            "username": "test_username"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.username.put(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_username_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.username.get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_event_settings_patch(self):
        data = {
            "bounce": True,
            "click": True,
            "deferred": True,
            "delivered": True,
            "dropped": True,
            "enabled": True,
            "group_resubscribe": True,
            "group_unsubscribe": True,
            "open": True,
            "processed": True,
            "spam_report": True,
            "unsubscribe": True,
            "url": "url"
        }
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.event.settings.patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_event_settings_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.event.settings.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_event_test_post(self):
        data = {
            "url": "url"
        }
        headers = {'X-Mock': 204}
        response = self.sg.client.user.webhooks.event.test.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_user_webhooks_parse_settings_post(self):
        data = {
            "hostname": "myhostname.com",
            "send_raw": False,
            "spam_check": True,
            "url": "http://email.myhosthame.com"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.user.webhooks.parse.settings.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_user_webhooks_parse_settings_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.parse.settings.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_parse_settings__hostname__patch(self):
        data = {
            "send_raw": True,
            "spam_check": False,
            "url": "http://newdomain.com/parse"
        }
        hostname = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.parse.settings._(
            hostname).patch(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_parse_settings__hostname__get(self):
        hostname = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.parse.settings._(
            hostname).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_user_webhooks_parse_settings__hostname__delete(self):
        hostname = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.user.webhooks.parse.settings._(
            hostname).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_user_webhooks_parse_stats_get(self):
        params = {
            'aggregated_by': 'day',
            'limit': 'test_string',
            'start_date': '2016-01-01',
            'end_date': '2016-04-01',
            'offset': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.user.webhooks.parse.stats.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains_post(self):
        data = {
            "automatic_security": False,
            "custom_spf": True,
            "default": True,
            "domain": "example.com",
            "ips": [
                "192.168.1.1",
                "192.168.1.2"
            ],
            "subdomain": "news",
            "username": "john@example.com"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.whitelabel.domains.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_whitelabel_domains_get(self):
        params = {
            'username': 'test_string',
            'domain': 'test_string',
            'exclude_subusers': 'true',
            'limit': 1,
            'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains_default_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains.default.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains_subuser_get(self):
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains.subuser.get(
            request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains_subuser_delete(self):
        headers = {'X-Mock': 204}
        response = self.sg.client.whitelabel.domains.subuser.delete(
            request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_whitelabel_domains__domain_id__patch(self):
        data = {
            "custom_spf": True,
            "default": False
        }
        domain_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains._(
            domain_id).patch(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains__domain_id__get(self):
        domain_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains._(
            domain_id).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains__domain_id__delete(self):
        domain_id = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.whitelabel.domains._(
            domain_id).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_whitelabel_domains__domain_id__subuser_post(self):
        data = {
            "username": "jane@example.com"
        }
        domain_id = "test_url_param"
        headers = {'X-Mock': 201}
        response = self.sg.client.whitelabel.domains._(
            domain_id).subuser.post(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_whitelabel_domains__id__ips_post(self):
        data = {
            "ip": "192.168.0.1"
        }
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains._(
            id_).ips.post(request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains__id__ips__ip__delete(self):
        id_ = "test_url_param"
        ip = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains._(
            id_).ips._(ip).delete(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_domains__id__validate_post(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.domains._(
            id_).validate.post(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_ips_post(self):
        data = {
            "domain": "example.com",
            "ip": "192.168.1.1",
            "subdomain": "email"
        }
        headers = {'X-Mock': 201}
        response = self.sg.client.whitelabel.ips.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_whitelabel_ips_get(self):
        params = {'ip': 'test_string', 'limit': 1, 'offset': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.ips.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_ips__id__get(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.ips._(
            id_).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_ips__id__delete(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.whitelabel.ips._(
            id_).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_whitelabel_ips__id__validate_post(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.ips._(
            id_).validate.post(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links_post(self):
        data = {
            "default": True,
            "domain": "example.com",
            "subdomain": "mail"
        }
        params = {'limit': 1, 'offset': 1}
        headers = {'X-Mock': 201}
        response = self.sg.client.whitelabel.links.post(
            request_body=data, query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 201)

    def test_whitelabel_links_get(self):
        params = {'limit': 1}
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links_default_get(self):
        params = {'domain': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links.default.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links_subuser_get(self):
        params = {'username': 'test_string'}
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links.subuser.get(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links_subuser_delete(self):
        params = {'username': 'test_string'}
        headers = {'X-Mock': 204}
        response = self.sg.client.whitelabel.links.subuser.delete(
            query_params=params, request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_whitelabel_links__id__patch(self):
        data = {
            "default": True
        }
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links._(id_).patch(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links__id__get(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links._(
            id_).get(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links__id__delete(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 204}
        response = self.sg.client.whitelabel.links._(
            id_).delete(request_headers=headers)
        self.assertEqual(response.status_code, 204)

    def test_whitelabel_links__id__validate_post(self):
        id_ = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links._(
            id_).validate.post(request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_whitelabel_links__link_id__subuser_post(self):
        data = {
            "username": "jane@example.com"
        }
        link_id = "test_url_param"
        headers = {'X-Mock': 200}
        response = self.sg.client.whitelabel.links._(link_id).subuser.post(
            request_body=data, request_headers=headers)
        self.assertEqual(response.status_code, 200)

    def test_license_year(self):
        LICENSE_FILE = 'LICENSE'
        copyright_line = ''
        with open(LICENSE_FILE, 'r') as f:
            for line in f:
                if line.startswith('Copyright'):
                    copyright_line = line.strip()
                    break
        self.assertEqual(
            'Copyright (C) %s, Twilio SendGrid, Inc. <help@twilio.com>' % datetime.datetime.now().year,
            copyright_line)
