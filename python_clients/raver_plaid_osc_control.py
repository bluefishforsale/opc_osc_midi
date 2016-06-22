#!/usr/bin/env python

"""A demo client for Open Pixel Control
http://github.com/zestyping/openpixelcontrol

Creates a shifting rainbow plaid pattern by overlaying different sine waves
in the red, green, and blue channels.

To run:
First start the gl simulator using the included "wall" layout

    make
    bin/gl_server layouts/wall.json

Then run this script in another shell to send colors to the simulator

    python_clients/raver_plaid.py

"""

from __future__ import division
import time
import math
import sys
import threading

from queue import Queue

import opc
import color_utils

from pythonosc import dispatcher
from pythonosc import osc_server

#-------------------------------------------------------------------------------
# handle command line

if len(sys.argv) == 1:
    IP_PORT = '127.0.0.1:7890'
elif len(sys.argv) == 2 and ':' in sys.argv[1] and not sys.argv[1].startswith('-'):
    IP_PORT = sys.argv[1]
else:
    print("""
    Usage: raver_plaid.py [ip:port]
    If not set, ip:port defauls to 127.0.0.1:7890
    """)
    sys.exit(0)


#-------------------------------------------------------------------------------
# connect to server

client = opc.Client(IP_PORT)
if client.can_connect():
    print('connected to %s' % IP_PORT)
else:
    # can't connect, but keep running in case the server appears later
    print('WARNING: could not connect to %s' % IP_PORT)


#-------------------------------------------------------------------------------
# send pixels

print('sending pixels forever (control-c to exit)...')

n_pixels = 512   # number of pixels in the included "wall" layout
fps = 24         # frames per second


#------------------------------------------------------------------------------
# initialize the values
freq_r = -1.7
freq_g =  2.3
freq_b = -1.9
speed_r = -0.7
speed_g =  2.3
speed_b = -0.9

#------------------------------------------------------------------------------
# initialize the queues
queue_r = Queue()
queue_g = Queue()
queue_b = Queue()

queue_r.put(("/1/red", speed_r, freq_r))
queue_g.put(("/1/green", speed_g, freq_g))
queue_b.put(("/1/blue", speed_b, freq_b))

#------------------------------------------------------------------------------
# The TouchOSC server
dispatcher = dispatcher.Dispatcher()
dispatcher.map("/1/red",   queue_r.put)
dispatcher.map("/1/green", queue_g.put)
dispatcher.map("/1/blue",  queue_b.put)
#dispatcher.map("/1/black1", print)
#dispatcher.map("/1/black2", print)

ip = '172.16.12.168'
port = 5006
server = osc_server.ForkingOSCUDPServer((ip, port), dispatcher)
server_thread = threading.Thread(target=server.serve_forever)

def render_pixels(queue_r, queue_g, queue_b):
    start_time = time.time()
    while True:
        t = time.time() - start_time

        pixels = []
        for ii in range(n_pixels):
            pct = ii / n_pixels
            # diagonal black stripes
            pct_jittered = (pct * 77 ) % 77
            blackstripes = color_utils.cos(
                    pct_jittered,
                    offset=t*0.05,
                    period=20,
                    minn=-1.0,
                    maxx=2.5)
            blackstripes_offset = color_utils.cos(
                    t,
                    offset=-0.9,
                    period=60,
                    minn=-1.5,
                    maxx=3)
            blackstripes = color_utils.clamp(
                    blackstripes + blackstripes_offset, 0, 1)
            # 3 sine waves for r, g, b which are out of sync with each other
            r_name, speed_r, freq_r = queue_r.get()
            g_name, speed_g, freq_g = queue_g.get()
            b_name, speed_b, freq_b = queue_b.get()

            print(("%.2f" %t, speed_r, freq_r))
            print(("%.2f" %t, speed_g, freq_g))
            print(("%.2f" %t, speed_b, freq_b))

            r = blackstripes * color_utils.remap(
                    math.cos((
                        t/speed_r + pct*freq_r)*math.pi*2),
                    -1, 1, 0, 256)
            g = blackstripes * color_utils.remap(
                    math.cos((
                        t/speed_g + pct*freq_g)*math.pi*2),
                    -1, 1, 0, 256)
            b = blackstripes * color_utils.remap(
                    math.cos((t/speed_b + pct*freq_b)*math.pi*2),
                    -1, 1, 0, 256)
            pixels.append((r, g, b))
        client.put_pixels(pixels, channel=0)
        time.sleep(1 / fps)


print("Serving on {}".format(server.server_address))
server_thread.start()
render_thread = threading.Thread(target=render_pixels, args=(queue_r, queue_g, queue_b))
render_thread.start()

server_thread.join()
render_thread.join()

server.shutdown()
