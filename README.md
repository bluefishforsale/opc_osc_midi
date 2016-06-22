OPC_OSC_MIDI
================


Quick start:
----------

OS X:

* Install HomeBrew
  * /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"

* Install Python3
  * pip install python3

* Install python-osc
  * pip3 install python-osc

* Start the openGL server
  * bin/gl_server -l layouts/512_pts.json 1234

* Run the pixel generator
  * python3 ./python_clients/raver_plaid_osc_control.py

Overview:
----------
OpenPixelControl is a simple stream protocol for controlling RGB lighting, particularly RGB LEDs.
See http://openpixelcontrol.org/ for a spec.

OpenSoundControl is a protocol for networking sound synthesizers, computers, and other multimedia devices for purposes such as musical performance or show control.

MIDI is not yet implemented, but will be in the future.

DMX is not yet implemented, but will be in the future.

