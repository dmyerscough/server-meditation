#!/usr/bin/env python

import configparser
import argparse
import requests
import logging
import redis
import time
import zmq
import sys
import os

# Import logging before Salt otherwise Salt will overwirte our settings
logging.basicConfig(level=logging.INFO, format='[ %(asctime)-15s ] %(message)s')
log = logging.getLogger(__name__)

import salt.client
from multiprocessing import Process


def server(hostname, username, password, interval=10):
    '''
    Query Sensu API for current monitoring events
    '''
    context = zmq.Context()

    server = context.socket(zmq.PUSH)
    server.bind("tcp://127.0.0.1:5557")

    while True:
        req = requests.get(hostname + '/events', auth=(username, password))

        if req.status_code != 200:
            log.info('Sensu API responded with status {0}'.format(
                req.status_code)
            )

        for event in req.json():
            server.send_json(event)

        time.sleep(interval)

    return True


def worker(hostname, port, base, location):
    '''
    Pull events from the ZeroMQ server and run remediation against
    problematic events
    '''
    log.info('Connecting to redis {0}:{1}'.format(hostname, port))
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
            log.info('Got event: {0}'.format(event))

            eventId = '|-'.join([event['client']['name'],
                                 event['check']['name']])

            if not _jobs.get(eventId):
                state = os.path.join(base, location, event['check']['name'])

                if os.path.isfile(state + '.sls'):
                    log.info('Locking event into redis & executing Salt remediation')
                    _jobs.set(eventId, True)

                    res = client.cmd(event['client']['name'], 'state.sls', [os.path.join(location, event['check']['name'])])
                    log.info('Salt response: {0}'.format(res))

                    if isinstance(res[event['client']['name']], dict):
                        log.info('{0} remediation was executed'.format(state))
                        for i in res[event['client']['name']].items():
                            action = i[-1]

                            log.info('Salt response: {0}'.format(action))
                            if action['result']:
                                status['success'].update({action['name']:
                                                          action['comment']})
                            else:
                                status['fail'].update({action['name']:
                                                       action['comment']})

                    # We can remove our lock when Sensu has performed a check
                    _jobs.expire(eventId, (event['check']['interval'] * 2))

                    log.info('{0} event will expire from redis in {1} seconds'.format(eventId, (event['check']['interval'] * 2)))
                else:
                    log.info('{0}.sls remediation does not exist'.format(state))


if __name__ == '__main__':

    config = configparser.ConfigParser()
    parser = argparse.ArgumentParser(description='Meditation Self-healing Infrastructure')

    parser.add_argument('-c', '--config', dest='config', type=str,
                        help='Configuration File', required=True)
    parser.add_argument('-p', '--pool-size', dest='pool', type=int,
                        help='Number of workers', required=True)
    parser.add_argument('-i', '--interval', dest='interval', type=int,
                        default=10,
                        help='How frequently to check Sensu events')
    parser.add_argument('-m', '--salt-master-config', dest='salt', type=str,
                        default='/etc/salt/master',
                        help='Salt master configuration')
    parser.add_argument('-l', '--location', dest='location', type=str,
                        default='', help='Salt state remedies')

    opts = parser.parse_args()

    try:
        config.read_file(open(opts.config, 'r'))
    except IOError, e:
        log.info('Unable to open {0}: {1}'.format(opts.salt, e.strerror))
        sys.exit(1)

    try:
        file_roots = salt.config.master_config(opts.salt)['file_roots']['base']
    except IOError, e:
        log.info('Salt file_roots: {1}'.format(opts.salt, e.strerror))
        sys.exit(1)

    for _base in file_roots:
        if os.path.isdir(os.path.join(_base, opts.location)):
            salt_base = _base
            break
    
    for i in range(opts.pool):
        log.info('Starting worker: {0}'.format(i))
        Process(target=worker, args=(config['redis']['server'],
                                     config['redis']['port'],
                                     salt_base,
                                     opts.location)).start()

    meditation = Process(target=server, args=(config['sensu']['server'],
                                              config['sensu']['username'],
                                              config['sensu']['password'],
                                              opts.interval)).start()
