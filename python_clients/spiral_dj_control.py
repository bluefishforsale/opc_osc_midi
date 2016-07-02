#!/usr/bin/env python

"""A client for Open Pixel Control
http://github.com/zestyping/openpixelcontrol

To run:
First start the gl simulator using a layout

    make
    bin/gl_server layouts/wall.json

Then run this script in another shell to send colors to the simulator
    ./python_clients/spiral_dj_control.py --listen_ip 192.168.1.1

"""

from __future__ import division
import argparse
import colorutils
import math
import multiprocessing
import OSC
import sys
import time

import profile

from multiprocessing import Queue
from Queue import Empty
from pprint import pprint

import opc
import color_utils


def main():
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

    #------------------------------------------------------------------------------
    # OSC server Setup
    # pyOSC module implementation
    osc_server = OSC.OSCServer((args.listen_ip, args.listen_port))
    osc_server.addDefaultHandlers()
    osc_server.timeout=0.0001
    #osc_server.timeout=0
    print("Listening for OSC on {}".format("%s:%d" % osc_server.server_address))
    print("Connecting to OPC on {}".format(OPC_IP_PORT))
    print('control-c to exit...')

    #-------------------------------------------------------------------------------
    # Number of Pixels, and Frame rate
    n_pixels = args.pixel_count   # number of pixels in the layout
    fps = args.fps                # frames per second

    #------------------------------------------------------------------------------
    # initialize the queue
    command_queue = Queue()
    # initialize the command dictionary
    command_dict = {}

    color_inputs = [
                  "/LeftChooser/1/1", "/LeftChooser/1/2", "/LeftChooser/1/3", "/LeftChooser/1/4", "/LeftChooser/1/5",
                  "/RightChooser/1/1", "/RightChooser/1/2", "/RightChooser/1/3", "/RightChooser/1/4", "/RightChooser/1/5",
                  "/LeftBlack/1", "/LeftBlack/2", "/LeftBlack/3", "/LeftBlack/4",
                  "/RightBlack/1", "/RightBlack/2", "/RightBlack/3", "/RightBlack/4",
                  "/LeftRed/1", "/LeftRed/2", "/RightRed/1", "/RightRed/2",
                  "/LeftGreen/1", "/LeftGreen/2", "/RightGreen/1", "/RightGreen/2",
                  "/LeftBlue/1", "/LeftBlue/2", "/RightBlue/1", "/RightBlue/2"]
    control_inputs = [
                  "/LeftBright", "/RightBright" "/XFader",
                  "/RedLevel", "/GreenLevel", "/BlueLevel", "/Saturation",
                  "/Strobe", "/StrobeRate/1/1", "/StrobeRate/1/2", "/StrobeRate/1/3", "/StrobeRate/1/4",
                  ]

    all_inputs = color_inputs + control_inputs
    DEFAULT_COLOR_PARAM = 1.51
    DEFAULT_CONTROL_PARAM = 1.0
    osc_handler = mypartial(osc_color_handler, cmd_queue=command_queue)
    # register all osc_inputs as OSC handlers
    for color_input in color_inputs:
        # register the handler with the command queue callback
        osc_server.addMsgHandler(color_input, osc_handler)
        # add in an initial value to all controls
        command_dict[color_input] = DEFAULT_COLOR_PARAM

    for control_input in control_inputs:
        # register the handler with the command queue callback
        osc_server.addMsgHandler(control_input, osc_handler)
        # add in an initial value to all controls
        command_dict[control_input] = DEFAULT_CONTROL_PARAM

    # start the OSC serer in the background
    server_job = multiprocessing.Process(target=osc_server.serve_forever)
    server_job.start()

    dt = 1.0 / fps
    # could also initialize this in control thread and put it on command queue,
    # though that would leave control_params possibly uninitialized.
    last_render = time.time()
    while True:
    #for x in range(0, 250):
        command_dict = queue_to_dict(command_queue, command_dict, all_inputs)
        render_time = last_render = time.time()
        pixels = render_pixels(args.pixel_count, render_time, all_inputs, command_dict)
        # send the pixlels to the OPC server
        client.put_pixels(pixels, channel=0)
        time.sleep( dt )

# clamps a number between a low and high range
# useful to restrict values from being beyond value ranges
def num_clamp(num, low, high):
    return max(low, min(num, max))

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


# the callback used by OSC
def osc_color_handler(path, tags, data, source, cmd_queue):
    # args ==  path, [tags], args, source
    # tags will contain 'fff'
    # args is a OSCMessage with data
    # source is where the message came from (in case you need to reply)
    cmd_queue.put((path, data))


# convert OSC messages in the queue to values in a dictionary
def queue_to_dict(cmd_queue, cmd_dict, osc_inputs):
    try:
        name, value = cmd_queue.get(timeout=0.00001)
        if name in osc_inputs:
            cmd_dict[name] = value[0]
    except Empty:
        pass
    return cmd_dict


# render the pixels, based on raver_plaid
def render_pixels(n_pixels, frame_time, osc_inputs, control_dict):
    pixels = []
    black_params = control_dict["/LeftBlack/1"], control_dict["/LeftBlack/2"], control_dict["/LeftBlack/3"], control_dict["/LeftBlack/4"]
    red_params   = control_dict["/LeftRed/1"], control_dict["/LeftRed/2"]
    green_params = control_dict["/LeftGreen/1"], control_dict["/LeftGreen/2"]
    blue_params  = control_dict["/LeftBlue/1"], control_dict["/LeftBlue/2"]
    rgb_params   = control_dict["/RedLevel"], control_dict["/GreenLevel"], control_dict["/BlueLevel"]
    saturation   = control_dict["/Saturation"]
    brightness   = control_dict["/LeftBright"]

    for i in range(n_pixels):
        pct = i / n_pixels
        # diagonal black stripes
        pct_jittered = (pct * 33 ) % 33
        blackstripes = color_utils.cos(
                pct_jittered,
                #frame_time * pct_jittered,
                offset = frame_time * black_params[0],
                period = black_params[1],
                minn = -1.0,
                maxx = 2.5)
        blackstripes_offset = color_utils.cos(
                frame_time * 0.1,
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
                    frame_time/params[0] + pct*params[1])*math.pi*2),
                -1, 1, 0, 255)

        # 3 sine waves for r, g, b which are out of sync with each other
        r = num_clamp(color_stripe(red_params)   * control_dict["/RedLevel"]   * brightness, 0.0001, 255.0)
        g = num_clamp(color_stripe(green_params) * control_dict["/GreenLevel"] * brightness, 0.0001, 255.0)
        b = num_clamp(color_stripe(blue_params)  * control_dict["/BlueLevel"]  * brightness, 0.0001, 255.0)

        # allow for HSV modifications
        try:
            h, s, v = colorutils.rgb_to_hsv((r, g, b))
            s = num_clamp(s * saturation, 0.00001, 1.0)
            r, g, b = colorutils.hsv_to_rgb((h, s, v))
        except:
            pass
            #print((r, g, b), (h, s, v))

        pixels.append((r, g, b))
    return pixels


if __name__ == '__main__':
    #profile.run('main()')
    main()
