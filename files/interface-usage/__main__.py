#!/usr/bin/env python3

import argparse
import json
import os
import time

from lib.log import *
from lib import log
from lib.api import RestGraphqlApi


def parse_arguments():
    """Get commandline arguments."""
    parser = argparse.ArgumentParser(
        description='Collect and aggregate interface statistics.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--log-file', default=log.LOGFILE)
    parser.add_argument('--generate-meta-file', action='store_true')
    parser.add_argument('--meta-file',
                        default='/var/www/128technology/t128-interface-usage/t128-interface-usage-meta.json')
    parser.add_argument('--buckets-file',
                        default='/var/lib/128technology/t128-interface-usage-buckets.json')
    parser.add_argument('--usages-file',
                        default='/var/www/128technology/t128-interface-usage/t128-interface-usages.json')
    parser.add_argument('--base-interfaces',
                        help='Populate interfaces list (also for ordering)')
    parser.add_argument('--blacklisted-interfaces',
                        default='ha_sync,ha_fabric')
    parser.add_argument('--blacklisted-routers', default='')
    args = parser.parse_args()
    return args


def read_buckets(filename):
    try:
        with open(filename) as fd:
            return json.load(fd)
    except FileNotFoundError:
        return {}


def write_meta(filename, meta):
    with open(filename, 'w') as fd:
        return json.dump(meta, fd)


def write_buckets(filename, buckets):
    with open(filename, 'w') as fd:
        return json.dump(buckets, fd)


def write_usages(filename, first_ts, interfaces, usages):
    with open(filename, 'w') as fd:
        os.chmod(filename, 0o444)
        return json.dump({
            'created': int(time.time()),
            'first_ts': first_ts,
            'interfaces': interfaces,
            'usages': usages,
        }, fd)


def get_meta_data(filename, api):
    fields = ['description', 'location']
    meta = {}
    for router in api.get_routers():
        meta[router['name']]=[v for k,v in router.items() if k in fields]
    write_meta(filename, meta)


def main():
    args = parse_arguments()
    log.DEBUG = args.debug
    log.LOGFILE = args.log_file
    blacklisted_interfaces = args.blacklisted_interfaces.split(',')
    blacklisted_routers = args.blacklisted_routers.split(',')
    api = RestGraphqlApi(args.host)

    # run script in meta file generator mode
    if args.generate_meta_file:
        get_meta_data(args.meta_file, api)
        return

    # Iterate over all routers and retrieve interface usage stats
    interfaces = []
    if args.base_interfaces:
        interfaces = args.base_interfaces.split(',')
    buckets = read_buckets(args.buckets_file)
    usages = []

    first_ts = int(time.time())
    for r in api.get_interfaces()['data']['allRouters']['nodes']:
        router = r['name']
        if router in blacklisted_routers:
             continue

        for n in r['nodes']['nodes']:
            node = n['name']
            node_usage = {}
            # print(node)
            for i in n['deviceInterfaces']['nodes']:
                # ignore host interfaces
                if i['type'] == 'host':
                    continue
                    # ignore blacklisted interfaces
                interface = i['name']
                # print(interface)
                if interface in blacklisted_interfaces:
                    continue
                if interface not in interfaces:
                    interfaces.append(interface)

                # get stats and update buckets/data usage
                current_stats = api.get_interface_usage(router, node, interface)
                if not current_stats:
                    # no data could be retrieved
                    continue

                # prepare new bucket
                ts, received, sent = current_stats
                this_bucket = [current_stats, current_stats]

                last_bucket = []
                try:
                    if buckets[router][node][interface]:
                        # get first bucket's ts for this interface
                        ts = buckets[router][node][interface][0][0][0]
                        last_bucket = buckets[router][node][interface].pop()
                        if ts < first_ts:
                            first_ts = ts
                except (KeyError, IndexError):
                    pass

                # keep the first and last bucket on integer overflow (128T restart)
                if last_bucket:
                    if received < last_bucket[1][1] or sent < last_bucket[1][2]:
                        buckets[router][node][interface].append(last_bucket)
                    else:
                        this_bucket[0] = last_bucket[0]

                # init
                if router not in buckets:
                        buckets[router] = {}
                if node not in buckets[router]:
                        buckets[router][node] = {}
                if interface not in buckets[router][node]:
                        buckets[router][node][interface] = []
                buckets[router][node][interface].append(this_bucket)

                # calculate data usage
                sum_received = 0
                sum_sent = 0
                # sum all buckets
                for bucket in buckets[router][node][interface]:
                    sum_received = bucket[1][1] - bucket[0][1]
                    sum_sent = bucket[1][2] - bucket[0][2]

                node_usage[interface] = sum_received + sum_sent
            usages.append((router, node, node_usage))

    write_buckets(args.buckets_file, buckets)
    write_usages(args.usages_file, first_ts, interfaces, usages)


if __name__ == '__main__':
    main()
