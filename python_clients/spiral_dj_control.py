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

#-------------------------------------------------------------------------------
# Connect to OPC server
OPC_IP_PORT = "%s:%s" % (args.send_ip, args.send_port)
client = opc.Client(OPC_IP_PORT)
if not client.can_connect():
    # can't connect, but keep running in case the server appears later
    print('WARNING: could not connect to %s' % IP_PORT)
    sys.exit(1)


# function which emulates the functionality of partial, but does not use the
# module. This was added because OSC was raising the error
# OSC.OSCServerError: Message callback '<functools.partial object at 0x102633578>' is not callable
# when using functools.partial
def mypartial(f,*bind_a,**bind_kw):
    def wrapped(*a,**kw):
        all_kw = bind_kw.copy()
        all_kw.update(kw)
        return f(*(bind_a+a),**all_kw)
    return wrapped

def osc_color_handler(path, tags, data, source, cmd_queue):
    # args ==  path, [tags], args, source
    # tags will contain 'fff'
    # args is a OSCMessage with data
    # source is where the message came from (in case you need to reply)
    print(path, data)
    cmd_queue.put(path, data)

def queue_to_dict(cmd_queue, cmd_dict, osc_inputs):
    for name, value in cmd_queue.get():
        #print(name, value)
        if name in osc_inputs:
            cmd_dict[name] = value[0]
    return cmd_dict

def render_pixels(n_pixels, start_time, osc_inputs, control_dict):
    t = time.time() - start_time

    black_params = control_dict["/LeftBlack/1"], control_dict["/LeftBlack/2"], control_dict["/LeftBlack/3"], control_dict["/LeftBlack/4"]
    red_params   = control_dict["/LeftRed/1"], control_dict["/LeftRed/2"]
    green_params = control_dict["/LeftGreen/1"], control_dict["/LeftGreen/2"]
    blue_params  = control_dict["/LeftBlue/1"], control_dict["/LeftBlue/2"]

    print(black_params)

    pixels = []
    for ii in range(n_pixels):
        pct = ii / n_pixels
        # diagonal black stripes
        pct_jittered = (pct * 77 ) % 77
        blackstripes = color_utils.cos(
                pct_jittered,
                offset = t*black_params[0],
                period = black_params[1],
                minn = -1.0,
                maxx = 2.5)
        blackstripes_offset = color_utils.cos(
                t,
                offset = black_params[2],
                period = black_params[3],
                minn = -1.5,
                maxx = 3)
        blackstripes = color_utils.clamp(
                blackstripes + blackstripes_offset, 0, 1)

        # sinewave function for colors
        def color_stripe(params):
            return blackstripes * color_utils.remap(
                math.cos((
                    frame_time/params.speed + pct*params.freq)*math.pi*2),
                -1, 1, 0, 256)

        # 3 sine waves for r, g, b which are out of sync with each other
        r = color_stripe(red_params)
        g = color_stripe(green_params)
        b = color_stripe(blue_params)
        pixels.append((r, g, b))

    return pixels



def main():
    #-------------------------------------------------------------------------------
    # Number of Pixels, and Frame rate
    n_pixels = args.pixel_count   # number of pixels in the layout
    fps = args.fps                # frames per second

    #------------------------------------------------------------------------------
    # initialize the queue
    command_queue = Queue()
    # initialize the command dictionary
    command_dict = {}

    #------------------------------------------------------------------------------
    # OSC server Setup
    # pyOSC module implementation
    osc_server = OSC.OSCServer((args.listen_ip, args.listen_port))
    osc_server.addDefaultHandlers()
    osc_server.timeout=0
    print("Listening for OSC on {}".format("%s:%d" % osc_server.server_address))
    print("Connecting to OPC on {}".format(OPC_IP_PORT))
    print('control-c to exit...')

    osc_inputs = [
                  "/LeftChooser/1/1", "/LeftChooser/1/2", "/LeftChooser/1/3", "/LeftChooser/1/4", "/LeftChooser/1/5",
                  "/RightChooser/1/1", "/RightChooser/1/2", "/RightChooser/1/3", "/RightChooser/1/4", "/RightChooser/1/5",
                  "/LeftBlack/1", "/LeftBlack/2", "/LeftBlack/3", "/LeftBlack/4",
                  "/RightBlack/1", "/RightBlack/2", "/RightBlack/3", "/RightBlack/4",
                  "/LeftRed/1", "/LeftRed/2", "/RightRed/1", "/RightRed/2",
                  "/LeftGreen/1", "/LeftGreen/2", "/RightGreen/1", "/RightGreen/2",
                  "/LeftBlue/1", "/LeftBlue/2", "/RightBlue/1", "/RightBlue/2",
                  "/LeftLevel", "/RightLevel" "/XFader",
                  "/HSB/1", "/HSB/2", "/HSB/3",
                  "/Strobe", "/StrobeRate/1/1", "/StrobeRate/1/2", "/StrobeRate/1/3", "/StrobeRate/1/4",
                  "/RedLevel", "/GreenLevel", "/BlueLevel",
                  ]

    DEFAULT_COLOR_PARAM = 0.01
    osc_handler = mypartial(osc_color_handler, cmd_queue=command_queue)
    for osc_input in osc_inputs:
        # register the handler with the command queue callback
        osc_server.addMsgHandler(osc_input, osc_handler)
        # add in an initial value to all controls
        command_dict[osc_input] = DEFAULT_COLOR_PARAM

    server_job = multiprocessing.Process(target=osc_server.serve_forever)
    server_job.start()

    start_time = time.time()
    while True:
        #osc_server.handle_request()
        command_dict = queue_to_dict(command_queue, command_dict, osc_inputs)
        pixels = render_pixels(args.pixel_count, start_time, osc_inputs, command_dict)
        client.put_pixels(pixels, channel=0)
        time.sleep( 1/fps )


if name == '__main__':
    main()
