#!/usr/bin/env python

"""Open Pixel Control read and display Image via PIL
http://github.com/zestyping/openpixelcontrol

To run:
First start the gl simulator using, for example, the included "wall" layout

    make
    bin/gl_server layouts/wall.json

Then run this script in another shell to send colors to the simulator

    python_clients/pil_load.py --layout layouts/wall.json

"""

from __future__ import division
import time
import sys
import optparse
import random
try:
    import json
except ImportError:
    import simplejson as json

from PIL import Image
from colorutils import Color


import opc
import color_utils


#-------------------------------------------------------------------------------
# command line

parser = optparse.OptionParser()
parser.add_option('-i', '--image', dest='image',
                    action='store', type='string')
parser.add_option('-l', '--layout', dest='layout',
                    action='store', type='string',
                    help='layout file')
parser.add_option('-s', '--server', dest='server', default='127.0.0.1:7890',
                    action='store', type='string',
                    help='ip and port of server')
parser.add_option('-f', '--fps', dest='fps', default=20,
                    action='store', type='int',
                    help='frames per second')

options, args = parser.parse_args()

if not options.layout:
    parser.print_help()
    print 'ERROR: you must specify a layout file using --layout'
    sys.exit(1)


#-------------------------------------------------------------------------------
# parse layout file
print '    parsing layout file'

coordinates = []
for item in json.load(open(options.layout)):
    if 'point' in item:
        coordinates.append(tuple(item['point']))


#-------------------------------------------------------------------------------
# connect to server

client = opc.Client(options.server)
if client.can_connect():
    print '    connected to %s' % options.server
else:
    # can't connect, but keep running in case the server appears later
    print '    WARNING: could not connect to %s' % options.server
print '    sending pixels forever (control-c to exit)...'

n_pixels = len(coordinates)
random_values = [random.random() for ii in range(n_pixels)]
start_time = time.time()


#-------------------------------------------------------------------------------
# connect to server
def ByteToHex( byteStr ):
    return ''.join( [ "%02X " % ord( x ) for x in byteStr ] ).strip()


def toaster_frame(img):
    pixels = []
    for w in range(0, img.width):
        for h in range(0, img.height):
            (r, g, b) = img.getpixel((w,h))
            #print(r, g, b)
            pixels.append(Color(rgb=(r, g, b)).rgb)
            #pixels.append((128, 255, 128))   # lime green
    return pixels

img = Image.open(options.image)
img.thumbnail((64, 64), Image.ANTIALIAS)
img_frames = img.n_frames

while True:
    t = time.time() - start_time
    #print((t * 10) % 24)
    #pixels = [pixel_color(t*0.6, coord, ii, n_pixels, random_values) for ii, coord in enumerate(coordinates)]

    img.seek(int(t * 10) % 24)
    print(img.tell())
    img_rgb = img.convert('RGB')
    pixels = toaster_frame(img_rgb)
    #img.seek(img.tell()+1)

    client.put_pixels(pixels, channel=0)
    time.sleep(1 / options.fps)
