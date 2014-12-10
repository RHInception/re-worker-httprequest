# Copyright (C) 2014 SEE AUTHORS FILE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Unittests.
"""

import os
import pika
import mock
import requests

from contextlib import nested

from . import TestCase

from replugin import httprequestworker


MQ_CONF = {
    'server': '127.0.0.1',
    'port': 5672,
    'vhost': '/',
    'user': 'guest',
    'password': 'guest',
}


class TestHTTPRequestWorker(TestCase):

    def setUp(self):
        """
        Set up some reusable mocks.
        """
        TestCase.setUp(self)

        self.channel = mock.MagicMock('pika.spec.Channel')

        self.channel.basic_consume = mock.Mock('basic_consume')
        self.channel.basic_ack = mock.Mock('basic_ack')
        self.channel.basic_publish = mock.Mock('basic_publish')

        self.basic_deliver = mock.MagicMock()
        self.basic_deliver.delivery_tag = 123

        self.properties = mock.MagicMock(
            'pika.spec.BasicProperties',
            correlation_id=123,
            reply_to='me')

        self.logger = mock.MagicMock('logging.Logger').__call__()
        self.app_logger = mock.MagicMock('logging.Logger').__call__()
        self.connection = mock.MagicMock('pika.SelectConnection')

    def tearDown(self):
        """
        After every test.
        """
        TestCase.tearDown(self)
        self.channel.reset_mock()
        self.channel.basic_consume.reset_mock()
        self.channel.basic_ack.reset_mock()
        self.channel.basic_publish.reset_mock()

        self.basic_deliver.reset_mock()
        self.properties.reset_mock()

        self.logger.reset_mock()
        self.app_logger.reset_mock()
        self.connection.reset_mock()

    def test_bad_command(self):
        """
        If a bad command is sent the worker should fail.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send')):

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "this is not a thing",
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_check_code(self):
        """
        Verify _check_code properly equates input.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send')):

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            assert worker._check_code(200, {'code': 200}) is True
            assert worker._check_code('404', {'code': 404}) is True
            assert worker._check_code(500, {'code': '500'}) is True
            # Verify raising when there is not a match
            self.assertRaises(
                httprequestworker.HTTPRequestWorkerError,
                worker._check_code,
                200,
                {'code': 404})

    def test_request_get(self):
        """
        Verify request_get works as it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.get')) as (_, _, _, _get):

            fake_response = requests.Response()
            fake_response.status_code = 200
            _get.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Get",
                    "url": "http://127.0.0.1",
                    "code": 200,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _get.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'

    def test_request_get_failure(self):
        """
        Verify request_get fails properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.get')) as (_, _, _, _get):

            fake_response = requests.Response()
            fake_response.status_code = 400
            _get.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Get",
                    "url": "http://127.0.0.1",
                    "code": 200,
                },
            }

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _get.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

            # Test for failed connections
            _.get.reset_mock()
            self.app_logger.error.reset_mock()
            worker.send.reset_mock()
            _get.side_effect = requests.ConnectionError

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _get.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_request_delete(self):
        """
        Verify request_delete works as it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.delete')) as (_, _, _, _delete):

            fake_response = requests.Response()
            fake_response.status_code = 410
            _delete.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Delete",
                    "url": "http://127.0.0.1",
                    "code": 410,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _delete.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'

    def test_request_delete_failure(self):
        """
        Verify request_delete fails properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.delete')) as (_, _, _, _delete):

            fake_response = requests.Response()
            fake_response.status_code = 400
            _delete.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Delete",
                    "url": "http://127.0.0.1",
                    "code": 200,
                },
            }

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _delete.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

            # Test for failed connections
            _delete.reset_mock()
            self.app_logger.error.reset_mock()
            worker.send.reset_mock()
            _delete.side_effect = requests.ConnectionError

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _delete.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_request_put(self):
        """
        Verify request_put works as it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.put')) as (_, _, _, _put):

            fake_response = requests.Response()
            fake_response.status_code = 201
            _put.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Put",
                    "url": "http://127.0.0.1",
                    "contenttype": "application/json",
                    "content": '{"test": "data"}',
                    "code": 201,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _put.called_once_with(
                'http://127.0.0.1',
                data='{"test": "data"}',
                headers={"content-type": "application/json"})
            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'

    def test_request_put_failure(self):
        """
        Verify request_put fails properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.delete')) as (_, _, _, _put):

            fake_response = requests.Response()
            fake_response.status_code = 400
            _put.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Put",
                    "url": "http://127.0.0.1",
                    "contenttype": "application/json",
                    "content": '{"test": "data"}',
                    "code": 201,
                },
            }

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _put.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

            # Test for failed connections
            _put.reset_mock()
            self.app_logger.error.reset_mock()
            worker.send.reset_mock()
            _put.side_effect = requests.ConnectionError

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _put.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

    def test_request_post(self):
        """
        Verify request_post works as it should.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.post')) as (_, _, _, _post):

            fake_response = requests.Response()
            fake_response.status_code = 200
            _post.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Post",
                    "url": "http://127.0.0.1",
                    "contenttype": "application/json",
                    "content": '{"test": "data"}',
                    "code": 200,
                },
            }

            # Execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _post.called_once_with(
                'http://127.0.0.1',
                data='{"test": "data"}',
                headers={"content-type": "application/json"})
            assert self.app_logger.error.call_count == 0
            assert worker.send.call_args[0][2]['status'] == 'completed'

    def test_request_post_failure(self):
        """
        Verify request_post fails properly.
        """
        with nested(
                mock.patch('pika.SelectConnection'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.notify'),
                mock.patch('replugin.httprequestworker.HTTPRequestWorker.send'),
                mock.patch('requests.delete')) as (_, _, _, _post):

            fake_response = requests.Response()
            fake_response.status_code = 400
            _post.return_value = fake_response

            worker = httprequestworker.HTTPRequestWorker(
                MQ_CONF,
                logger=self.app_logger,
                config_file='conf/example.json')

            worker._on_open(self.connection)
            worker._on_channel_open(self.channel)

            body = {
                "parameters": {
                    "command": "httprequest",
                    "subcommand": "Post",
                    "url": "http://127.0.0.1",
                    "contenttype": "application/json",
                    "content": '{"test": "data"}',
                    "code": 200,
                },
            }

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _post.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'

            # Test for failed connections
            _post.reset_mock()
            self.app_logger.error.reset_mock()
            worker.send.reset_mock()
            _post.side_effect = requests.ConnectionError

            # execute the call
            worker.process(
                self.channel,
                self.basic_deliver,
                self.properties,
                body,
                self.logger)

            assert _post.called_once_with('http://127.0.0.1')
            assert self.app_logger.error.call_count == 1
            assert worker.send.call_args[0][2]['status'] == 'failed'
