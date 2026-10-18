# CircuitPython entry point (runs at power-up): the game host with the game named in config.py.
# For the Salient bring-up benchmark instead, replace this with:  from games.salient import bench; bench.main()
from gamehost import host

host.run()
