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
import argparse
import time
import math
import OSC
import sys
import multiprocessing

from multiprocessing import Queue
from pprint import pprint

import opc
import color_utils

#from pythonosc import dispatcher
#from pythonosc import osc_server

#-------------------------------------------------------------------------------
# Process command line args

parser = argparse.ArgumentParser(description='An OSC server which sends RGB values to an OPC server')
parser.add_argument('--listen_ip', default='0.0.0.0', help='')
parser.add_argument('--listen_port', default=5006, help='')
parser.add_argument('--send_ip', default='0.0.0.0', help='')
parser.add_argument('--send_port', default='7890', help='')
parser.add_argument('--pixel_count', default=512, help='')
parser.add_argument('--fps', default=24, help='')
args = parser.parse_args()

#------------------------------------------------------------------------------
# initialize the queue
command_queue = Queue()

#-------------------------------------------------------------------------------
# Connect to OPC server
OPC_IP_PORT = "%s:%s" % (args.send_ip, args.send_port)
client = opc.Client(OPC_IP_PORT)
if not client.can_connect():
    # can't connect, but keep running in case the server appears later
    print('WARNING: could not connect to %s' % IP_PORT)
    sys.exit(1)

#-------------------------------------------------------------------------------
# Number of Pixels, and Frame rate
n_pixels = args.pixel_count   # number of pixels in the included "wall" layout
fps = args.fps         # frames per second


def osc_color_handler(*args):
    queue = command_queue.__weakref__()
    # path, tags, args, source
    #print(args)
    path = args[0]
    data = args[2]
    # tags will contain 'fff'
    # args is a OSCMessage with data
    # source is where the message came from (in case you need to reply)
    #queue.put((path, args[0], args[1]))
    #queue.put_nowait((path, data[0] - 0.5 * 1.5, data[1] - 0.5 * 1.5))
    queue.put((path, data[0] - 0.5 * 1.5, data[1] - 0.5 * 1.5))
    return

def render_pixels(n_pixels, client, start_time):
    queue = command_queue.__weakref__()
    #------------------------------------------------------------------------------
    # initialize the values
    freq_r = 0.01
    freq_g = 0.01
    freq_b = 0.01
    speed_r = 0.01
    speed_g = 0.01
    speed_b = 0.01

    t = time.time() - start_time

    #name, speed, freq = queue.get_nowait()
    name, speed, freq = queue.get()
    pprint(name, speed, freq)
    if name is not None:
        if name == '/red':
            speed_r, freq_r = speed, freq
        if name == '/green':
            speed_g, freq_g = speed, freq
        if name == '/blue':
            speed_b, freq_b = speed, freq
        else:
            speed_r = speed_r
            freq_r = freq_r
            speed_g = speed_g
            freq_g = freq_g
            speed_b = speed_b
            freq_b = freq_b

    print(("%.2f" % t, speed_r, freq_r))
    print(("%.2f" % t, speed_g, freq_g))
    print(("%.2f" % t, speed_b, freq_b))

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
    time.sleep( 1/fps )


if __name__ == '__main__':
    #------------------------------------------------------------------------------
    # OSC server Setup
    # pyOSC module implementation
    osc_server = OSC.OSCServer((args.listen_ip, args.listen_port))
    osc_server.addDefaultHandlers()
    osc_server.addMsgHandler( "/red",   osc_color_handler)
    osc_server.addMsgHandler( "/green", osc_color_handler)
    osc_server.addMsgHandler( "/blue",  osc_color_handler)
    osc_server.addMsgHandler( "/black",  osc_color_handler)
    osc_server.addMsgHandler( "/black_offset",  osc_color_handler)
    osc_server.timeout=0

    print("Listening for OSC on {}".format("%s:%d" % osc_server.server_address))
    print("Connecting to OPC on {}".format(OPC_IP_PORT))
    print('control-c to exit...')

    server_job = multiprocessing.Process(target=osc_server.serve_forever)
    server_job.start()

    start_time = time.time()
    while 1:
        #osc_server.handle_request()
        render_pixels(args.pixel_count, client, start_time)
