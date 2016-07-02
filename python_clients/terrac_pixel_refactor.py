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
from functools import partial
from collections import namedtuple
import argparse
import time
import math
import OSC
import sys
from Queue import Empty
from multiprocessing import Queue, Process
from pprint import pprint

import opc
import color_utils

ColorParams = namedtuple('ColorParams', ('speed', 'freq'))

def main():
    # Process command line args

    parser = argparse.ArgumentParser(description='An OSC server which sends RGB values to an OPC server')
    parser.add_argument('--listen_ip', default='0.0.0.0', help='')
    parser.add_argument('--listen_port', default=5006, help='')
    parser.add_argument('--send_ip', default='0.0.0.0', help='')
    parser.add_argument('--send_port', default='7890', help='')
    parser.add_argument('--pixel_count', default=512, help='')
    parser.add_argument('--fps', default=24, help='')
    args = parser.parse_args()

    # OPC server setup
    opc_addr = "%s:%s" % (args.send_ip, args.send_port)

    # Number of Pixels, and Frame rate
    n_pixels = args.pixel_count   # number of pixels in the included "wall" layout
    fps = args.fps         # frames per second

    # render thread command and response
    cmd_queue, resp_queue = Queue(), Queue()

    # start the pixel server
    pixel_client = Process(
        target=render_client,
        args=(opc_addr, cmd_queue, resp_queue, n_pixels, fps))
    pixel_client.start()
    resp = resp_queue.get()
    if resp == SERVER_CONNECTION_FAIL:
        raise Exception("Render server could not connect to OPC server.")
    elif resp == PIXEL_SERVER_RUNNING:
        print("Pixel server started successfully.")
    else:
        raise Exception("Unexpected response from pixel server: {}"
            .format(resp))


    # using custom partial function, see comments below
    osc_handler = mypartial(osc_color_handler, cmd_queue=cmd_queue)

    # OSC server Setup
    # pyOSC module implementation
    osc_server = OSC.OSCServer((args.listen_ip, args.listen_port))
    osc_server.addDefaultHandlers()
    osc_server.addMsgHandler("/red",   osc_handler)
    osc_server.addMsgHandler("/green", osc_handler)
    osc_server.addMsgHandler("/blue",  osc_handler)
# need to enrich pixel server's color control model to handle these
#    osc_server.addMsgHandler( "/black",  osc_handler)
#    osc_server.addMsgHandler( "/black_offset",  osc_handler)
    osc_server.timeout = 0.001

    print("Listening for OSC on {}".format("%s:%d" % osc_server.server_address))
    print('control-c to exit...')

    server_job = Process(target=osc_server.serve_forever)
    server_job.start()

    # since the osc server is also running in a different process, this thread
    # can just sit here and idle, which is fine.  A more complete architecture
    # would route the OSC commands to this thread, which would aggregate and
    # normalize commands, and then pass them on to the render server.  That
    # enables this thread to act as a single-point dispatcher for all
    # commands, regardless of where they came from, simplifying the data flow
    # model.  That would look like adding another message queue from the OSC
    # server to here.
    # We should also really monitor the pixel client's response queue for errors,
    # and tie in some command to quit the application which will gracefully tear
    # down the other processes.  For the render server, that implies sending it
    # a QUIT command.
    while True:
        time.sleep(1.0)

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
    # path is the OSC handle '/foobar' for the control
    # tags will always contain 'fff'
    # args is a OSCMessage with data
    # source is where the message came from (in case you need to reply)
    #print(path, tags, data, source)
    cmd_queue.put( (COLOR_COMMAND, (path, data[0] - 0.5, data[1] - 0.5)) )

def raver_plaid(n_pixels, params, frame_time):
    print(params)
    red_params, green_params, blue_params = params
    pixels = []
    for i in range(n_pixels):
        pct = i / n_pixels
        # diagonal black stripes
        pct_jittered = (pct * 77 ) % 77
        blackstripes = color_utils.cos(
                pct_jittered,
                offset=frame_time*0.05,
                period=20,
                minn=-1.0,
                maxx=2.5)
        blackstripes_offset = color_utils.cos(
                frame_time,
                offset=-0.9,
                period=60,
                minn=-1.5,
                maxx=3)
        blackstripes = color_utils.clamp(
                blackstripes + blackstripes_offset, 0, 1)

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

SERVER_CONNECTION_FAIL = 'server connection fail'
PIXEL_SERVER_RUNNING = 'pixel server running'
PIXEL_SERVER_QUITTING = 'pixel server quitting'

COLOR_COMMAND = 'color command'
QUIT_COMMAND = 'quit command'

DEFAULT_COLOR_PARAM = ColorParams(0.01, 0.01)
DEFAULT_COLOR_PARAMS = {
    "red": DEFAULT_COLOR_PARAM,
    "blue": DEFAULT_COLOR_PARAM,
    "green": DEFAULT_COLOR_PARAM}

def render_client(addr, cmd_queue, resp_queue, n_pixels, fps):
    """Client process to receive commands and draw pixel frames."""
    # Connect to OPC server
    print("Connecting to OPC at {}".format(addr))
    client = opc.Client(addr)
    if not client.can_connect():
        # can't connect, but keep running in case the server appears later
        print('WARNING: could not connect to %s' % addr)
        resp_queue.put(SERVER_CONNECTION_FAIL)
        return
    else:
        resp_queue.put(PIXEL_SERVER_RUNNING)

    dt = 1.0 / fps

    # could also initialize this in control thread and put it on command queue,
    # though that would leave control_params possibly uninitialized.
    control_params = dict(DEFAULT_COLOR_PARAMS)
    last_render = time.time()

    while True:
        # this is not very sophisticated, see those pages I sent you for better
        # and more stable frame timing.  Frame clock stability is important for
        # smooth visual appeal.
        time_left = last_render + dt - time.time()
        while time_left > 0:
            # block until we run out of time or receive a command
            # this can be made more snappy by reducing time_left so we go through
            # at least a couple of loops.
            try:
                command, payload = cmd_queue.get(timeout=time_left)
                if command == COLOR_COMMAND:
                    name, speed, freq = payload
                    control_params[name] = payload
                elif command == QUIT_COMMAND:
                    resp_queue.put(PIXEL_SERVER_QUITTING)
                    return
                else:
                    # either blow up, log the unknown command, or something else.
                    # fill it in yourself
                    pass
            except Empty:
                pass

        # ready to render
        render_time = last_render = time.time()
        pixels = raver_plaid(n_pixels, control_params, render_time)
        client.put_pixels(pixels, channel=0)


if __name__ == '__main__':
    main()
