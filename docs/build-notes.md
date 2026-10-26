# Build notes: chasing bugs on the board

Notes for the Thunderbird Labs build page: the bugs, dead ends and surprises from building the board and its games,
and how each one was run down. Most of the work happened in sessions with Claude Code, with the board plugged into
the PC so code could be tried on the real hardware over its USB console. The numbers come from those sessions.

The hardware, for context: a Feather RP2040 SCORPIO running CircuitPython drives a hex island of 37 hexes (111
LEDs, or 155 on the small board with 144/m strip) and six 10-light bars, one per seat. Each bar is built into a
controller. Games are plug-ins on the board's drive, and the board itself handles the game picker, setup, menus and
controllers.

---

## 1. The aurora that was too slow for the board

**Symptom.** Aurora is a wall-decoration mode: curtains of northern lights that build, peak and fade, drawn from
each LED's real position on the board. It looked right in desktop renders, but the RP2040 couldn't keep up with it.

**First step: measure on the real hardware, not the desktop.** The desktop is about a hundred times faster than the
RP2040, so desktop timing says nothing. A small timing script was pasted into the board's REPL over USB, which
showed the moving parts of the sky took under 1 ms. Working out the colors of 155 LEDs took **60 ms**, and that
turned out later to be the *quiet* sky, with one curtain of three (see the measurement mistake below). At the planned
25 updates a second, that's half again more time than there is.

**Second step: a baseline.** Before optimizing, every attract mode got the same full-frame timing on the board:

| Mode | Average frame | Frames a second |
| --- | --- | --- |
| Clock | 46 ms | about 21 |
| Forest Fire | 45 ms | about 21 |
| Fireflies | 26 ms | about 39 |

So the board's real ceiling is about 20 frames a second, not the 40 in the config. Drawing 155 LEDs through the
host and sending them out already takes much of a frame. That set the target: get Aurora close to 20.

**What didn't work, in order:**

1. *Leaner Python.* A color lookup table, flat lists, local variables, fewer lookups per LED: 60 ms down to about
   41 ms. Still far too slow.
2. *ulab, CircuitPython's built-in numpy.* Doing the math on whole arrays in compiled code sounded like the answer.
   It was slower (71 ms, and 53 ms even after trimming), and timing single operations on the board showed why. On a
   155-element array, an add or multiply costs about 0.4 ms, a sine about 1 ms, and a curtain needed around 45 of
   them. The RP2040 (a Cortex-M0+) has no floating-point hardware, so every float operation runs in software, array
   or not. Worse, every array operation made a new array. In real time even the quiet sky ran at about 7 frames a
   second, with the memory clean-ups stalling the board for up to 420 ms.

**What worked: whole numbers and tables.** On this chip integer math is cheap, and small integers cost no memory.
The sky was rewritten so that, per LED, it's one subtraction, a range check, three table lookups and three
additions:

- Positions in 64ths of a hex width.
- A 1,024-step sine table, looked up once per *column* of LEDs (29 columns) instead of per LED.
- Each curtain's fade, already colored green to teal to violet, precomputed as a table by distance from its edge.
  The pink "surge" fringe gets its own small table, rebuilt only while a surge is changing.
- Working lists created once and reused, so a sky update leaves little to clean up.

Result, measured in the running game: about 37 ms a sky update on a quiet sky and 59 ms at a full display. In real
time that's about 16 and 13 frames a second (the quiet sky ran at 7 with ulab), with the sky itself updating 7 to 10
times a second, which is plenty for something that moves this slowly. It's still slower than the other modes, and
what's left is mostly the cost of doing anything 155 times in Python on an M0+.

**A measurement mistake worth admitting.** The integer version first timed at 23 ms and 22 frames a second, which
looked like victory. But the timing scripts set the sky to full activity and then ran the game's update, which reset
it to a quiet sky. Every step-by-step figure above (60, 41, 71, 53 and 23 ms) was a quiet sky. The comparisons
between versions still hold, since they were all measured the same way, but none of them showed a full display.
Only the final runs, holding the sky at its peak, did. Lesson: check that the thing you're timing is the thing you
think you're timing.

**Smoothness check.** Aurora must never flash. A desktop test runs whole displays and records the biggest change any
LED makes between updates, as a rate: no LED may swing from dark to full in under about 0.2 s, slower than the
board's 3-flashes-a-second limit. That test caught two real jumps: a new display swapping out a curtain that was
still visible, and a surge switching on instantly. It caught a third later, after a rewrite: at the height of a
surge, an LED crossing a curtain's edge jumped straight from green to pink, because a short blend had been dropped.

**Lessons:** measure on the target hardware; know whether your chip has an FPU; time the pieces before rewriting
them; on a microcontroller, memory churn is a performance problem.

---

## 2. Game picker previews that showed a blinking dot

**Symptom.** In the game picker, each game shows a preview "card" on the island. Aurora's and the clock's showed
only a blinking white center hex: the picker's fallback when a card fails.

**Ruling things out.** Every card drew fine on the desktop, so the cards weren't broken. The picker caught the error
and hid it, so the next step was to load each card on the board itself, with a big game running, and print the real
error:

```
CARDS free with rush loaded: 36608
CARDS aurora FAILED: MemoryError('memory allocation failed, allocating 416 bytes')
CARDS clock ok
CARDS fire FAILED: MemoryError()
CARDS fireflies FAILED: MemoryError('memory allocation failed, allocating 376 bytes')
```

**Cause.** The picker loads a card while the current game is still in memory (you can go back to it). Games that
live in a folder were already precompiled to `.mpy`. Single-file games were copied to the drive as `.py` source, so
people could edit them without a toolchain. Loading a card from a `.py` game means compiling the whole game on the
board, and compiling takes far more memory than running compiled code. With Island Rush loaded (about 36 KB free),
the biggest single-file games couldn't be compiled. It depended on how much memory happened to be free, so which
cards failed varied from run to run.

There was history here. Earlier, when switching games first ran out of memory, the decision was to compile the big
games and keep the small ones as editable source. As the attract modes grew, "small" stopped being true.

**Fix.** The deploy script now compiles every game to `.mpy`, and puts the editable sources in `games/src/` on the
drive, where the board doesn't load them. To change a game on the drive, edit its source there and copy it into
`games/`; a `.py` is loaded before an `.mpy`. With Island Rush loaded and only 24 KB free, all eight cards now load.
The picker also prints the reason when a card fails, so the next one won't be a mystery.

**Found along the way.** Fireflies kept, for every one of the 155 LEDs, a list of the LEDs near it: about 28 KB on a
board with about 70 KB free, all for three "answers" per evening. It now works that out only when needed.

**Lessons:** a fallback that hides errors also hides the cause, so log it; memory on a microcontroller depends on
what's already loaded, so test with the worst case loaded.

**It came back.** With Aurora or Rain running, every card in the picker fell back to the blinking hex again, the
clock's too. This time the picker's log said why at once:

```
game picker: rain's card didn't load (MemoryError('memory allocation failed, allocating 418 bytes',))
game picker: clock's card didn't load (MemoryError('memory allocation failed, allocating 256 bytes',))
game picker: aurora's card didn't load (MemoryError('memory allocation failed, allocating 1024 bytes',))
```

The worst case hadn't been the worst case: the fix above was checked with Island Rush running, not with the two
hungriest attract screens (25 KB free with Aurora running). Measuring on the board what loading each game keeps
showed the real problem. A one-file game has no card of its own, so the picker loads the whole game to draw its
picture: 5.6 KB for Fire, 8 KB for Rain, 11 KB for Aurora, 13 KB for the clock, plus more while it loads. Island
Rush's card, in its own `card.py`, costs 1 KB.

**Fix.** The attract screens are folders now, like Island Rush: `games/aurora/game.py` and a small `card.py` that
draws the picture without loading the game. Their sources still go to `games/src/` on the drive.

---

## 3. The controller that did nothing

**Symptom.** The wired controller (rotary encoder plus two buttons) did nothing in any game.

**Test in layers.** A stand-alone test sketch read the controller's pins directly, bypassing the game host, the
lobby and every controller hub, and drove each controller's bar from them: the encoder adds and removes lights, and
the buttons step the color. It also printed every pin change, every raw encoder count, and each switch's level at
startup. All pins opened fine, and nothing ever changed.

Next a raw scan watched all 30 of the board's pins at once, with pull-ups on, while the button was pressed. Nothing
changed. Then a jumper wire from D9 straight to GND: still nothing. That was a strong hint the code was fine. To be
sure, the scan was checked against a switch known to work, the SCORPIO's own BOOT button, and it registered every
press. So the code was fine and D9 wasn't reaching the chip, even with a jumper on the header pin.

**Cause.** When the headers went on, only the pins in use at the time were soldered, to make the header easy to swap
if the design changed. The controller's pins weren't among them. Centered perfectly in their holes, they touched
nothing, and a meter on the header pin said everything was fine. Once soldered, every pin worked. The encoder and
buttons turned out to be wired backwards too, which was quick to fix with the test sketch running.

**Lessons:** test from the hardware up; check your test against something known to work before trusting a
"nothing happened"; solder every pin you'll wire to.

---

## 4. Shorter stories from earlier sessions

**Red never wins.** Watching computer-vs-computer games of Salient on the board, the attacker seemed never to win.
The simulator said 49%. Both engines (the browser prototype in JavaScript and the board's CircuitPython port) replay
the same game from the same seed, so the board's games were logged with their seeds and replayed on the desktop:
every one matched move for move. Nothing was broken. But the logs showed a real pattern: about 6.5% of games ended
with the attacker wiped out by round 3, sometimes in round 1. Those games take a few minutes, while attacker wins take
20 or more, so an hour of watching could easily show several quick losses and no wins. The fix was a rule: an
attacker run off the island with ships still coming gets a free naval bombardment to land again. Quick losses
dropped from 5.6% to 0% with the overall balance almost unchanged.

**The island ran backwards, then upside down.** After wiring, the test pattern ran backwards. The first fix mirrored
left to right and left the rows upside down. The fix that worked came from asking which single wiring explains
*both* results: data entering at the bottom-right hex and running the original order exactly in reverse. The
setting now names the corner hex where the data enters, so any of the four corners works.

**LEDs jumping around mid-strip.** The test pattern skipped around on the strips. The board's config said `large`
(60/m strip) while the build used the small board (144/m, with an extra LED at each hex edge), so every address after
the first was off.

**The board that wasn't running CircuitPython.** A freshly plugged-in board showed up as COM3 with no drive and no
REPL. Its USB vendor ID was `2E8A` (Raspberry Pi), not `239A` (Adafruit CircuitPython): it was still running an old
Arduino sketch.

**Too bright to look at.** The LEDs were painful at 50% and 25%, and comfortable at 5%. But at 5% the LEDs have only
about 13 brightness steps, so dim colors (like the cursor glow on an empty light) can vanish; the glow is now doubled
at low brightness. Brightness is applied in the board's own integer math, not by the LED driver, which also saved a
second copy of every pixel in memory.

**Out of memory while the USB page watched.** The USB page (a web page on the board's own drive that talks to it
over Web Serial, with no install) shows the board's lights live. Starting a game from it ran the board out of
memory. Moving the dimming into `lights.py` and dropping the PIO assembler once the LED driver was built took free
memory during play from about 15 KB to 26 KB. (Web Serial turned out to work in Firefox as well, despite the docs.)

**The crash when switching games.** Switching from Salient to the clock crashed the board. Three things were tangled
together:

- *Memory fragmentation.* Salient fits at power-up, but after a few switches the memory is too broken up to load it
  again. The board now restarts cleanly with the new game when it doesn't fit in place.
- *A crash caused by the debugging itself.* The only radio crash caught on the console came from extra logging added
  to find the bug, which overflowed a small stack.
- *Two devices disagreeing.* After a reboot, the radio co-processor pushed its saved game ("salient") back onto the
  board, so it looked as if the switch had failed. Now the board's own settings win, and the radio follows.

**"I invented this game and can't beat level 1."** The difficulty levels had been calibrated with the computer
playing the human's side at full strength. Rerun against simulated beginners, level 1 was nearly unwinnable. The
stand-ins were still too good, though: even the "novice" saw every odds and rule perfectly, while a person is reading
lights and steering a cursor. The real finding was that players were losing to arithmetic (a ship clock, income from
connected land, decay of cut-off spots), not to bad decisions, because the board showed none of it. That led to
splitting Island Rush off as its own game: a race to the taco truck in the middle, everyone against the jungle,
nobody knocked out.

**Island Rush's misbehaving AI and tigers.**

- *Sideways clearing.* Computer players sometimes cleared jungle sideways for no reason. That was 7–21% of their
  clears, mostly players already on the truck spending leftover lights. They now only clear spots that bring them
  closer.
- *Tigers that picked on red and blue.* Tigers chased the first two seats most, because ties between equally close
  players were broken by turn order. Now ties go to whoever a tiger chased longest ago.
- *A loophole.* A player could ring the truck with their own spots and lock everyone out. Attacking other players
  closed it.
- *"Did the computer even get a turn?"* A win right after taking the truck looked as if the computer had been
  skipped. It hadn't: the first player rotates each round, so turns can fall back to back across the end of a
  round. The check did turn up a real question for later, though: in 60% of two-player games, the winner took the
  truck when nobody had a turn left to answer. The win rule is unchanged for now.

**The simulator did the heavy lifting.** Salient's rules went from v0.1 to v0.14, with thousands of
computer-vs-computer games behind each change. Spreading the simulator across all 16 CPU cores brought a 4,000-game
run down to 10–18 seconds, and even then one sweep of 24 rule combinations took half an hour (single-threaded, it
would have run all night). Some ideas that sounded right failed badly in the numbers. "Build up the beachhead first"
dropped the attacker from 21% to 3% or less, and none of nine other attacker strategies did reliably better than
plain greed. The board's CircuitPython engine replays 500 seeds identically against the browser's
JavaScript engine: 255,876 moves, the same on every one.

**Toolchain gotchas (radio firmware).** ESP-IDF's tool installer silently refuses to run under Git Bash (it detects
MSYS), so builds run from PowerShell. GCC choked on network (UNC) paths, so the build mirrors the source to a local
folder. Git wouldn't fetch a submodule onto the network share, so the dependencies live in the user folder.

---

## The toolkit that kept coming up

- **Replay by seed.** Two engines (JavaScript for the browser, CircuitPython for the board) that play identical
  games from the same seed turn "the board is acting weird" into a yes-or-no question.
- **A REPL over USB.** Paste a small script into the board's REPL to time code, scan pins or load a module with the
  real error showing. Most of these bugs were found that way.
- **Desktop renders.** Draw the board's LEDs to an image on the PC to check how a mode looks before putting it on
  the board.
- **Test in layers.** A stand-alone controller test, a raw pin scan, then a known-good switch: each one rules out a
  layer.
- **Measure, then change.** Every speed-up was decided by timing the pieces on the board, and twice the timing
  proved the obvious fix wrong.
- **Simulate before you rule.** Rule changes are tried over thousands of computer games before they reach the board.
