OPC_OSC_MIDI
================


Quick start:
----------

OS X:

* Install HomeBrew
  * /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

* Install the extra python modules via pip
  * pip3 install python-osc
  * pip3 install colorutils

* Start the openGL server
  * ./bin/gl_server -l layouts/512_pts.json 1234

* Run the pixel generator
  * ./python_clients/spiral_dj_control.py --listen_ip <your ip>

* Use the TouchOSC client to load the layout
  * DJ Spiral Control.touchosc


What each part does:
----------
OpenPixelControl is a simple stream protocol for controlling RGB lighting, particularly RGB LEDs.
See http://openpixelcontrol.org/ for a spec.

OpenSoundControl is a protocol for networking sound synthesizers, computers, and other multimedia devices for purposes such as musical performance or show control.

TouchOSC is used on android or IOS devices to

MIDI is not yet implemented, but will be in the future.

DMX is not yet implemented, but will be in the future.

