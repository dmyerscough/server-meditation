#!/usr/bin/env python

import configparser
import argparse
import requests
import logging
import redis
import time
import zmq
import sys

# Import logging before Salt otherwise Salt will overwirte our settings
logging.basicConfig(level=logging.INFO,
                    format='[ %(asctime)-15s ] %(message)s')
log = logging.getLogger(__name__)

import salt.client
from multiprocessing import Process


def server(hostname, username, password, interval=20):
    '''
    Query Sensu API for current monitoring events
    '''
    context = zmq.Context()

    server = context.socket(zmq.PUSH)
    server.bind("tcp://127.0.0.1:5557")

    while True:
        req = requests.get(hostname + '/events', auth=(username, password))

        if req.status_code != 200:
            log.info('Sensu API responded with status {0}'.format(req.status_code))

        for event in req.json():
            server.send_json(event)

        time.sleep(interval)

    return True


def worker(hostname, port=6379, location=None):
    '''
    Pull events from the ZeroMQ server and run remediation against
    problematic events
    '''
    _jobs = redis.StrictRedis(host=hostname, port=port)

    context = zmq.Context()
    client = salt.client.LocalClient()

    status = {'success': {}, 'fail': {}}

    worker = context.socket(zmq.PULL)
    worker.connect("tcp://127.0.0.1:5557")

    poller = zmq.Poller()
    poller.register(worker, zmq.POLLIN)

    while True:
        socks = dict(poller.poll())

        if socks.get(worker) == zmq.POLLIN:
            event = worker.recv_json()
            log.info('Got Event')

            eventId = '|-'.join([event['client']['name'], event['check']['name']])

            if not _jobs.get(eventId):
                if location:
                    state = '/'.join([location, event['check']['name']])
                else:
                    state = event['check']['name']

                # Ensure the Salt command is not executed more than once
                _jobs.set(eventId, True)
                log.info('Locking event into Redis & Executing Salt Remedy')

                res = client.cmd(event['client']['name'], 'state.sls', [state])

                if isinstance(res[event['client']['name']], dict):
                    log.info('{0} remedy was executed'.format(state))
                    for i in res[event['client']['name']].items():
                        action = i[-1]

                        if action['result']:
                            status['success'].update({action['name']:
                                                      action['comment']})
                        else:
                            status['fail'].update({action['name']:
                                                   action['comment']})

                # We can remove our lock when Sensu has performed a check
                _jobs.expire(eventId, (event['check']['interval'] * 2))


if __name__ == '__main__':

    config = configparser.ConfigParser()
    parser = argparse.ArgumentParser(description='Meditation Self-healing Infrastructure')

    parser.add_argument('-c', '--config', dest='config', type=str,
                        help='Configuration File', required=True)
    parser.add_argument('-p', '--pool-size', dest='pool', type=int,
                        help='Number of workers', required=True)

    parser.add_argument('-s', '--states', dest='location', type=str,
                        help='Salt state remedies')

    opts = parser.parse_args()

    try:
        config.read_file(open(opts.config, 'r'))
    except IOError, e:
        print 'Unable to open {0}: {1}'.format(opts.config, e.strerror)
        sys.exit(1)

    for i in range(opts.pool):
        print 'Starting worker: {0}'.format(i)
        if opts.location:
            Process(target=worker, args=(config['redis']['server'], config['redis']['port'], opts.location)).start()
        else:
            Process(target=worker, args=(config['redis']['server'], config['redis']['port'])).start()

    meditation = Process(target=server, args=(config['sensu']['server'], config['sensu']['username'], config['sensu']['password'])).start()
