#!/usr/bin/env python

import threading
import requests
import logging
import redis
import time
import zmq
import sys
import os


class MeditationServer(threading.Thread):
    def __init__(self, sensu, username, password, interval=10, listen='127.0.0.1'):
        threading.Thread.__init__(self)

        # Sensu Connection Details
        self.hostname = sensu
        self.username = username
        self.password = password
        self.interval = interval

        self.listen = listen

        # Python logging
        self.log = logging.getLogger('MeditationServer')
        self.log.setLevel(logging.INFO)

        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.INFO)

        self.format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.ch.setFormatter(self.format)
        self.log.addHandler(self.ch)

    def __query_sensu(self):
        '''
        Query RESTful API endpoint
        '''
        req = requests.get('/'.join([self.hostname, 'events']),
                           auth=(self.username, self.password))

        if req.status_code != 200:
            log.info('Sensu API responded with a status code {0}'.format(
                req.status_code)
            )
            return False

        return req.json()

    def run(self):
        '''
        Start Meditation server, publish Sensu critical events to
        worker nodes
        '''
        context = zmq.Context()

        server = context.socket(zmq.PUSH)
        server.bind('tcp://' + self.listen + ':5557')

        while True:
            self.log.info('Waiting for event')
            for event in self.__query_sensu():
                self.log.info('Go event {0}'.format(event))
                server.send_json(event)

            time.sleep(self.interval)

        return True
