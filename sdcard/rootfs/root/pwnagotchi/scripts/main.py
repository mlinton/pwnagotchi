#!/usr/bin/python3
import argparse
import yaml
import time
import traceback

import core
import pwnagotchi, pwnagotchi.plugins as plugins

from pwnagotchi.log import SessionParser
from pwnagotchi.voice import Voice
from pwnagotchi.agent import Agent
from pwnagotchi.ui.display import Display

parser = argparse.ArgumentParser()

parser.add_argument('-C', '--config', action='store', dest='config', default='/root/pwnagotchi/config.yml')

parser.add_argument('--manual', dest="do_manual", action="store_true", default=False, help="Manual mode.")
parser.add_argument('--clear', dest="do_clear", action="store_true", default=False,
                    help="Clear the ePaper display and exit.")

args = parser.parse_args()

if args.do_clear:
    print("clearing the display ...")
    with open(args.config, 'rt') as fp:
        config = yaml.safe_load(fp)
        cleardisplay = config['ui']['display']['type']
        if cleardisplay in ('inkyphat', 'inky'):
            print("inky display")
            from inky import InkyPHAT

            epd = InkyPHAT(config['ui']['display']['color'])
            epd.set_border(InkyPHAT.BLACK)
            self._render_cb = self._inky_render
        elif cleardisplay in ('papirus', 'papi'):
            print("papirus display")
            from pwnagotchi.ui.papirus.epd import EPD

            os.environ['EPD_SIZE'] = '2.0'
            epd = EPD()
            epd.clear()
        elif cleardisplay in ('waveshare_1', 'ws_1', 'waveshare1', 'ws1'):
            print("waveshare v1 display")
            from pwnagotchi.ui.waveshare.v1.epd2in13 import EPD

            epd = EPD()
            epd.init(epd.lut_full_update)
            epd.Clear(0xFF)
        elif cleardisplay in ('waveshare_2', 'ws_2', 'waveshare2', 'ws2'):
            print("waveshare v2 display")
            from pwnagotchi.ui.waveshare.v2.waveshare import EPD

            epd = EPD()
            epd.init(epd.FULL_UPDATE)
            epd.Clear(0xff)
        else:
            print("unknown display type %s" % cleardisplay)
        quit()

with open(args.config, 'rt') as fp:
    config = yaml.safe_load(fp)

plugins.load_from_path(plugins.default_path)
if 'plugins' in config['main'] and config['main']['plugins'] is not None:
    plugins.load_from_path(config['main']['plugins'])

plugins.on('loaded')

display = Display(config=config, state={'name': '%s>' % pwnagotchi.name()})
agent = Agent(view=display, config=config)

core.log("%s@%s (v%s)" % (pwnagotchi.name(), agent._identity, pwnagotchi.version))
# for key, value in config['personality'].items():
#    core.log("  %s: %s" % (key, value))

for _, plugin in plugins.loaded.items():
    core.log("plugin '%s' v%s loaded from %s" % (plugin.__name__, plugin.__version__, plugin.__file__))

if args.do_manual:
    core.log("entering manual mode ...")

    log = SessionParser(config['main']['log'])

    core.log("the last session lasted %s (%d completed epochs, trained for %d), average reward:%s (min:%s max:%s)" % (
        log.duration_human,
        log.epochs,
        log.train_epochs,
        log.avg_reward,
        log.min_reward,
        log.max_reward))

    while True:
        display.on_manual_mode(log)
        time.sleep(1)
        if config['twitter']['enabled'] and log.is_new() and Agent.is_connected() and log.handshakes > 0:
            import tweepy

            core.log("detected a new session and internet connectivity!")

            picture = '/dev/shm/pwnagotchi.png'

            display.update()
            display.image().save(picture, 'png')
            display.set('status', 'Tweeting...')
            display.update()

            try:
                auth = tweepy.OAuthHandler(config['twitter']['consumer_key'], config['twitter']['consumer_secret'])
                auth.set_access_token(config['twitter']['access_token_key'], config['twitter']['access_token_secret'])
                api = tweepy.API(auth)

                tweet = Voice(lang=config['main']['lang']).on_log_tweet(log)
                api.update_with_media(filename=picture, status=tweet)
                log.save_session_id()

                core.log("tweeted: %s" % tweet)
            except Exception as e:
                core.log("error: %s" % e)

    quit()

core.logfile = config['main']['log']

agent.start_ai()
agent.setup_events()
agent.set_starting()
agent.start_monitor_mode()
agent.start_event_polling()

# print initial stats
agent.next_epoch()

agent.set_ready()

while True:
    try:
        # recon on all channels
        agent.recon()
        # get nearby access points grouped by channel
        channels = agent.get_access_points_by_channel()
        # check for free channels to use
        agent.check_channels(channels)
        # for each channel
        for ch, aps in channels:
            agent.set_channel(ch)

            if not agent.is_stale() and agent.any_activity():
                core.log("%d access points on channel %d" % (len(aps), ch))

            # for each ap on this channel
            for ap in aps:
                # send an association frame in order to get for a PMKID
                agent.associate(ap)
                # deauth all client stations in order to get a full handshake
                for sta in ap['clients']:
                    agent.deauth(ap, sta)

        # An interesting effect of this:
        #
        # From Pwnagotchi's perspective, the more new access points
        # and / or client stations nearby, the longer one epoch of
        # its relative time will take ... basically, in Pwnagotchi's universe,
        # WiFi electromagnetic fields affect time like gravitational fields
        # affect ours ... neat ^_^
        agent.next_epoch()
    except Exception as e:
        core.log("main loop exception: %s" % e)
        core.log("%s" % traceback.format_exc())
