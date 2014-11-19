#!/usr/bin/env python

import requests
import logging
import celery

import salt.client

log = logging.getLogger(__name__)


class SaltRemedy(object):
    def __init__(self, hostname, username, password, location=None):
        self.hostname = hostname
        self.username = username
        self.password = password

        self.location = location
        self.acked = {}

    def __get_events(self):
        '''

        '''
        req = requests.get(self.hostname + '/events',
                           auth=(self.username, self.password))

        if req.status_code != 200:
            log.error('Sensu API responded with status {0}'.format(
                req.status_code)
                )
            return False

        return req.json()

    def proc(self):
        '''

        TODO: Validate remedy location
        '''
        client = salt.client.LocalClient()

        for event in self.__get_events():
            eventId = '|-'.join([event['client']['name'],
                                 event['check']['name']])

            if self.acked.get(eventId, False):
                self.acked[eventId] = event
            else:
                if self.location:
                    remedy = '{0}/{1}'.format(self.location,
                                              event['check']['name'])

                    res = client.cmd(event['client']['name'],
                                     'state.sls',
                                     [remedy])
                else:
                    res = client.cmd(event['client']['name'],
                                     'state.sls',
                                     [event['check']['name']])

                if isinstance(res[event['client']['name']], list):
                    raise Exception('Unable to execute remedy: {0}'.format(
                        res[event['client']['name']][0]))
                else:
                    for i in res[event['client']['name']].items():
                        action = i[-1]

                        # TODO: Email operator when a remedy fails
                        if action['result']:
                            print "Remedy, run"
                        else:
                            print action['name'], " failed to execute: `{0}`".format(action['comment'])

                # Acknowledge that we tried fixing the issue
                self.acked[eventId] = event


if __name__ == '__main__':

    sensu = SaltRemedy('http://localhost:4567', 'admin', 'mypass', 'remedy')
    sensu.proc()
