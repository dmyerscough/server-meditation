#!/usr/bin/env python

import threading
import logging
import redis
import zmq
import os

import salt.client


class MeditationWorker(threading.Thread):
    def __init__(self, server, redis_server, redis_port, base, location):
        threading.Thread.__init__(self)

        # Meditation Server
        self.server = server

        # Redis server details
        self.redis_server = redis_server
        self.redis_port = redis_port

        # Salt base and state file locations
        self.base = base
        self.location = location

        # Python logging
        self.log = logging.getLogger('MeditationWorker')
        self.log.setLevel(logging.INFO)

        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.INFO)

        self.format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.ch.setFormatter(self.format)
        self.log.addHandler(self.ch)


    def run(self):
        '''
        Start Meditation work to start processing monitoring events
        '''
        summary = {'success': {}, 'fail': {}}

        _job_cache = redis.StrictRedis(host=self.redis_server,
                                       port=self.redis_port)

        context = zmq.Context()
        client = salt.client.LocalClient()

        worker = context.socket(zmq.PULL)
        worker.connect('tcp://' + self.server + ':5557')

        poller = zmq.Poller()
        poller.register(worker, zmq.POLLIN)

        while True:
            socks = dict(poller.poll())

            if socks.get(worker) == zmq.POLLIN:
                event = worker.recv_json()
                self.log.info('Got event: {0}'.format(event))

                eventId = '|-'.join([event['client']['name'],
                                     event['check']['name']])

                if not _job_cache.get(eventId):
                    state_file = os.path.join(self.base,
                                              self.location,
                                              event['check']['name'])

                    if os.path.isfile(state_file + '.sls'):
                        self.log.info('Locking event into redis & executing Salt remediation')
                        _job_cache.set(eventId, True)

                        state = [os.path.join(self.location,
                                              event['check']['name'])]

                        res = client.cmd(event['client']['name'],
                                         'state.sls',
                                         state)
                        self.log.info('Salt response: {0}'.format(res))

                        if isinstance(res[event['client']['name']], dict):
                            self.log.info('{0} remediation was executed'.format(state))

                            for i in res[event['client']['name']].items():
                                action = i[-1]

                                self.log.info('Salt response: {0}'.format(action))
                                if action['result']:
                                    summary['success'].update({action['name']:
                                                               action['comment']})
                                else:
                                    summary['fail'].update({action['name']:
                                                            action['comment']})

                        # We can remove our lock when Sensu has performed a check
                        _job_cache.expire(eventId, (event['check']['interval'] * 2))

                        self.log.info('{0} event will expire from redis in {1} seconds'.format(eventId, (event['check']['interval'] * 2)))
                    else:
                        self.log.info('{0}.sls remediation does not exist'.format(state))
