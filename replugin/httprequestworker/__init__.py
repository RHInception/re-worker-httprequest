# -*- coding: utf-8 -*-
# Copyright © 2014 SEE AUTHORS FILE
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
HTTP Request worker.
"""

import base64
import requests

from reworker.worker import Worker


class HTTPRequestWorkerError(Exception):
    """
    Base exception class for HTTPRequestWorker errors.
    """
    pass


class HTTPRequestWorker(Worker):
    """
    Worker which provides HTTP Request functionality.
    """

    #: allowed subcommands
    subcommands = ('Get', 'Delete', 'Put', 'Post')
    dynamic = []

    # Subcommand methods
    def request_get(self, body, corr_id, output):
        """
        Executes an HTTP GET request.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            url = params['url']
            response = requests.get(url)
            self._check_code(response.status_code, params)
            return 'URL returned %s as expected.' % response.status_code
        except requests.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to URL %s. Error: %s' % (url, ce))
            raise HTTPRequestWorkerError(
                'Could not connect to the requested URL.')
        except KeyError, ke:
            raise HTTPRequestWorkerError(
                'Missing input %s' % ke)

    def request_delete(self, body, corr_id, output):
        """
        Executes an HTTP DELETE request.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            url = params['url']
            response = requests.delete(url)
            self._check_code(response.status_code, params)
            return 'URL returned %s as expected.' % response.status_code
        except requests.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to URL %s. Error: %s' % (url, ce))
            raise HTTPRequestWorkerError(
                'Could not connect to the requested URL.')
        except KeyError, ke:
            raise HTTPRequestWorkerError(
                'Missing input %s' % ke)

    def request_put(self, body, corr_id, output):
        """
        Executes an HTTP PUT request.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            url = params['url']
            content_type = params['contenttype']
            content = params['content']

            if params.get('b64encoded', False):
                content = base64.decodestring(params['content'])

            headers = {'content-type': content_type}
            response = requests.put(url, data=content, headers=headers)
            self._check_code(response.status_code, params)
            return 'URL returned %s as expected.' % response.status_code
        except requests.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to URL %s. Error: %s' % (url, ce))
            raise HTTPRequestWorkerError(
                'Could not connect to the requested URL.')
        except KeyError, ke:
            raise HTTPRequestWorkerError(
                'Missing input %s' % ke)

    def request_post(self, body, corr_id, output):
        """
        Executes an HTTP POST request.

        Parameters:

        * body: The message body structure
        * corr_id: The correlation id of the message
        * output: The output object back to the user
        """
        # Get needed variables
        params = body.get('parameters', {})

        try:
            url = params['url']
            content_type = params['contenttype']
            content = params['content']

            if params.get('b64encoded', False):
                content = base64.decodestring(params['content'])

            headers = {'content-type': content_type}
            response = requests.post(url, data=content, headers=headers)
            self._check_code(response.status_code, params)
            return 'URL returned %s as expected.' % response.status_code
        except requests.ConnectionError, ce:
            self.app_logger.warn(
                'Unable to connect to URL %s. Error: %s' % (url, ce))
            raise HTTPRequestWorkerError(
                'Could not connect to the requested URL.')
        except KeyError, ke:
            raise HTTPRequestWorkerError(
                'Missing input %s' % ke)

    def _check_code(self, response_code, params):
        """
        Raises an HTTPRequestWorkerError if the expectation isn't met.\

        Parameters:
        * response_code: The response code that came back from the request
        * params: The parameters passed into the the subcommand method
        """
        expected_code = int(params.get('code', 200))
        response_code = int(response_code)
        if response_code != expected_code:
            self.app_logger.debug('%s != %s' % (response_code, expected_code))
            raise HTTPRequestWorkerError(
                'Expected status %s but got %s' % (
                    expected_code, response_code))
        return True

    def process(self, channel, basic_deliver, properties, body, output):
        """
        Processes HTTPRequestWorker requests from the bus.

        *Keys Requires*:
            * subcommand: the subcommand to execute.
        """
        # Ack the original message
        self.ack(basic_deliver)
        corr_id = str(properties.correlation_id)
        # Notify we are starting
        self.send(
            properties.reply_to, corr_id, {'status': 'started'}, exchange='')

        try:
            try:
                subcommand = str(body['parameters']['subcommand'])
                if subcommand not in self.subcommands:
                    raise KeyError()
            except KeyError:
                raise HTTPRequestWorkerError(
                    'No valid subcommand given. Nothing to do!')

            cmd_method = None
            if subcommand == 'Get':
                cmd_method = self.request_get
            elif subcommand == 'Put':
                cmd_method = self.request_put
            elif subcommand == 'Post':
                cmd_method = self.request_post
            elif subcommand == 'Delete':
                cmd_method = self.request_delete
            else:
                self.app_logger.warn(
                    'Could not find the implementation of subcommand %s' % (
                        subcommand))
                raise HTTPRequestWorkerError('No subcommand implementation')

            result = cmd_method(body, corr_id, output)
            # Send results back
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'completed', 'data': result},
                exchange=''
            )
            # Notify on result. Not required but nice to do.
            self.notify(
                'HTTPRequestWorker Executed Successfully',
                'HTTPRequestWorker successfully executed %s. See logs.' % (
                    subcommand),
                'completed',
                corr_id)

            # Send out responses
            self.app_logger.info(
                'HTTPRequestWorker successfully executed %s for '
                'correlation_id %s. See logs.' % (
                    subcommand, corr_id))

        except HTTPRequestWorkerError, fwe:
            # If a HTTPRequestWorkerError happens send a failure log it.
            self.app_logger.error('Failure: %s' % fwe)
            self.send(
                properties.reply_to,
                corr_id,
                {'status': 'failed'},
                exchange=''
            )
            self.notify(
                'HTTPRequestWorker Failed',
                str(fwe),
                'failed',
                corr_id)
            output.error(str(fwe))


def main():  # pragma: no cover
    from reworker.worker import runner
    runner(HTTPRequestWorker)


if __name__ == '__main__':  # pragma nocover
    main()
