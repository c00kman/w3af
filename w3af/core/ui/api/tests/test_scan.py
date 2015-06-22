"""
test_scan.py

Copyright 2015 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""
import json
import requests

from w3af.core.ui.api.tests.utils.api_unittest import APIUnitTest
from w3af.core.ui.api.tests.utils.test_profile import (get_test_profile,
                                                       get_expected_vuln_names,
                                                       get_expected_vuln_urls)


class APIScanTest(APIUnitTest):

    def test_start_simple_scan(self):
        profile, target_url = get_test_profile()
        data = {'scan_profile': profile,
                'target_urls': [target_url]}
        response = requests.post('%s/scans/' % self.api_url,
                                 data=json.dumps(data),
                                 headers=self.headers)

        self.assertEqual(response.json(), {u'message': u'Success',
                                           u'href': u'/scans/0',
                                           u'id': 0})
        self.assertEqual(response.status_code, 201)

        #
        # Wait until the scan is in Running state
        #
        response = self.wait_until_running()

        self.assertEqual(response.status_code, 200, response.text)
        list_response = {u'items': [{u'href': u'/scans/0',
                                     u'id': 0,
                                     u'status': u'Running',
                                     u'errors': False,
                                     u'target_urls': [target_url]}]}
        self.assertEqual(response.json(), list_response)

        #
        # Get the detailed status
        #
        response = requests.get('%s/scans/0/status' % self.api_url)
        self.assertEqual(response.status_code, 200, response.text)

        json_data = response.json()
        self.assertEqual(json_data['is_running'], True)
        self.assertEqual(json_data['is_paused'], False)
        self.assertEqual(json_data['exception'], None)

        #
        # Wait until the scanner finishes and assert the vulnerabilities
        #
        self.wait_until_finish()

        response = requests.get('%s/kb/' % self.api_url)
        self.assertEqual(response.status_code, 200, response.text)

        vuln_summaries = response.json()['items']
        names = set([v['name'] for v in vuln_summaries])
        urls = set([v['url'] for v in vuln_summaries])

        self.assertEqual(4, len(vuln_summaries))
        self.assertEqual(names, set(get_expected_vuln_names()))
        self.assertEqual(urls, set(get_expected_vuln_urls(target_url)))

        #
        # Make sure I can access the vulnerability details
        #
        response = requests.get('%s/kb/0' % self.api_url)
        self.assertEqual(response.status_code, 200, response.text)

        vuln_info = response.json()
        self.assertEqual(vuln_info['plugin_name'], 'sqli')
        self.assertEqual(vuln_info['href'], '/kb/0')
        self.assertEqual(vuln_info['id'], 0)
        self.assertEqual(vuln_info['fix_effort'], 50)
        self.assertEqual(vuln_info['cwe_ids'], ['89'])
        self.assertEqual(vuln_info['severity'], 'High')
        self.assertEqual(vuln_info['tags'], [u'web', u'sql', u'injection',
                                             u'database', u'error'])

        #
        # Get the scan log
        #
        response = requests.get('%s/scans/0/log' % self.api_url)
        self.assertEqual(response.status_code, 200, response.text)

        log_data = response.json()
        self.assertGreater(len(log_data['entries']), 100)
        self.assertEqual(log_data['more'], False)
        self.assertEqual(log_data['next'], None)

        zero_entry = log_data['entries'][0]
        self.assertEqual(zero_entry['message'], u'Called w3afCore.start()')
        self.assertEqual(zero_entry['severity'], None)
        self.assertEqual(zero_entry['type'], 'debug')
        self.assertIsNotNone(zero_entry['time'])

        #
        # Clear the scan results
        #
        response = requests.delete('%s/scans/0' % self.api_url)
        self.assertEqual(response.json(), {u'message': u'Success'})

    def test_stop(self):
        profile, target_url = get_test_profile()
        data = {'scan_profile': profile,
                'target_urls': [target_url]}
        response = requests.post('%s/scans/' % self.api_url,
                                 data=json.dumps(data),
                                 headers=self.headers)

        self.assertEqual(response.json(), {u'message': u'Success',
                                           u'href': u'/scans/0',
                                           u'id': 0})
        self.assertEqual(response.status_code, 201)

        #
        # Wait until the scan is in Running state
        #
        self.wait_until_running()

        #
        # Now stop the scan
        #
        response = requests.get('%s/scans/0/stop' % self.api_url)
        self.assertEqual(response.json(), {u'message': u'Stopping scan'})

        # Wait for it...
        self.wait_until_finish()

        # Assert that we identify the logs associated with stopping the core
        response = requests.get('%s/scans/0/log' % self.api_url)
        self.assertEqual(response.status_code, 200, response.text)

        log_data = response.json()['entries']
        for entry in log_data:
            if 'The user stopped the scan' in entry['message']:
                break
        else:
            self.assertTrue(False, 'Stop not found in log')
