# gamehost: the board's side of every game. It knows the hardware (lights, controllers, wiring) and nothing about
# any game; games (in games/) know the rules and nothing about pins. See docs/making-games.md.
#
#   game.py       the Game base class: the whole interface between the board and a game
#   host.py       runs a game: polls the controllers, calls the game, shows the frame
#   geometry.py   the board's shape: hex and line names, neighbors, seats, each seat's view, arrow-key moves
#   lights.py     drawing by hex, line and bar; the LED map of both boards; the power cap
#   drivers.py    LED drivers (NeoPXL8, one NeoPixel strand, none)
#   fx.py         light effects (blink, breathe, flash, chase), on one clock, with the flash-rate limit
#   dice.py       a die roll shown on a seat's bar
#   actions.py    the action names controllers send
#   controls.py   controllers: the inputs and hubs below, turned into (controller, action)
#   inputs.py     wired inputs: button, encoder, one-switch scan, resistor ladder
#   hubs.py       I2C controller boards, the serial console
#   plugins.py    how config.py names your own drivers, inputs, hubs and games
