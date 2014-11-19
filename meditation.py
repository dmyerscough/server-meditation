#!/usr/bin/env python

import requests
import logging
import smtplib
import celery
import redis

import salt.client

log = logging.getLogger(__name__)


class Meditation(object):
    def __init__(self,
                 hostname,
                 username,
                 password,
                 redis,
                 redis_port=6379,
                 location=None):

        self.hostname = hostname
        self.username = username
        self.password = password

        self.redis = redis
        self.redis_port = redis_port

        self.location = location

    def __get_events(self):
        '''
        Grab Sensu Events
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
        Parse the current Sensu events and have Salt run remediation actions
        against problematic hosts

        TODO: Validate remedy location
              Read from configuration to set email address etc
        '''
        _jobs = redis.StrictRedis(host=self.redis, port=self.redis_port)
        client = salt.client.LocalClient()

        status = {'success': {}, 'fail': {}}

        for event in self.__get_events():
            eventId = '|-'.join([event['client']['name'],
                                 event['check']['name']])

            # Dont even run the check if we have already run remediation
            if not _jobs.get(eventId):
                if self.location:
                    state = '/'.join([self.location, event['check']['name']])
                else:
                    state = event['check']['name']

                res = client.cmd(event['client']['name'], 'state.sls', [state])

                if isinstance(res[event['client']['name']], dict):
                    for i in res[event['client']['name']].items():
                        action = i[-1]

                        if action['result']:
                            status['success'].update({action['name']:
                                                      action['comment']})
                        else:
                            status['fail'].update({action['name']:
                                                   action['comment']})

                    # Acknowledge that we tried to fix the issue. We should not
                    # attempt to run the state again until sensu has rechecked
                    # the service again
                    _jobs.set(eventId, True)
                    _jobs.expire(eventId, (event['check']['interval'] * 2))

                    msg = 'Subject: Meditation {0} was executed\n \
                           The following states were successfully run: X\n\n \
                           The following states failed to run: X\n\n'.format(event['check']['name'])

                    mail = smtplib.SMTP('localhost')
                    mail.sendmail('damian@mirulabs.com', 'Damian.Myerscough@gmail.com', msg)


if __name__ == '__main__':

    sensu = Meditation('http://localhost:4567', 'admin', 'mypass', 'localhost', location='remedy')
    sensu.proc()
