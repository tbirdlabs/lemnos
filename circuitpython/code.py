# CircuitPython entry point (runs at power-up): the game host with the game named in config.py.
# For the wired controller test:  from gamehost import ctltest; ctltest.main()
from gamehost import host

host.run()
