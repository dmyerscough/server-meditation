#!/usr/bin/env python

import configparser
import argparse

import server.mserver
import client.mworker

from multiprocessing import Process


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
    parser.add_argument('-b', '--base', dest='base', type=str,
                        help='Salt base', required=True)
    parser.add_argument('-l', '--location', dest='location', type=str,
                        default='', help='Salt state remedies')

    opts = parser.parse_args()

    try:
        config.read_file(open(opts.config, 'r'))
    except IOError, e:
        log.info('Unable to open {0}: {1}'.format(opts.config, e.strerror))
        sys.exit(1)

    server = server.mserver.MeditationServer(config['sensu']['server'],
                                             config['sensu']['username'],
                                             config['sensu']['password'],
                                             opts.interval)

    server.start()

    for i in range(opts.pool):
        client.mworker.MeditationWorker('127.0.0.1',
                                        config['redis']['server'],
                                        config['redis']['port'],
                                        opts.base,
                                        opts.location).start()

#        Process(target=worker, args=(config['redis']['server'],
#                                     config['redis']['port'],
#                                     salt_base,
#                                     opts.location)).start()
#
#    meditation = Process(target=server, args=(config['sensu']['server'],
#                                              config['sensu']['username'],
#                                              config['sensu']['password'],
#                                              opts.interval)).start()
