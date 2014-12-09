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
    subcommands = ()
    dynamic = []

    # Subcommand methods
    # TODO: Implement

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
            if subcommand == '':
                cmd_method = lambda: "Implement me"
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
