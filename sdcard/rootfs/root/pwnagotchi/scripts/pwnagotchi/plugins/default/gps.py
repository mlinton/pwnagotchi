__author__ = 'evilsocket@gmail.com'
__version__ = '1.0.0'
__name__ = 'gps'
__license__ = 'GPL3'
__description__ = 'Save GPS coordinates whenever an handshake is captured.'
__enabled__ = True  # set to false if you just don't use GPS

import core
import json
import os

device = '/dev/ttyUSB0'
speed = 19200
running = False


def on_loaded():
    core.log("GPS plugin loaded for %s" % device)


def on_ready(agent):
    global running

    if os.path.exists(device):
        core.log("enabling GPS bettercap's module for %s" % device)
        try:
            agent.run('gps off')
        except:
            pass

        agent.run('set gps.device %s' % device)
        agent.run('set gps.speed %d' % speed)
        agent.run('gps on')
        running = True
    else:
        core.log("no GPS detected")


def on_handshake(agent, filename, access_point, client_station):
    if running:
        info = agent.session()
        gps = info['gps']
        gps_filename = filename.replace('.pcap', '.gps.json')

        core.log("saving GPS to %s (%s)" % (gps_filename, gps))
        with open(gps_filename, 'w+t') as fp:
            json.dump(gps, fp)
