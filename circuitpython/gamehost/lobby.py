# The lobby: everything on the board between games, the same for every game. Choosing the game, joining, the game's
# setup, and what happens when a game ends. The host runs it; a game only describes its setup (options(): the same
# form the USB page shows), starts a game from it (setup()), may draw what the choices will look like (preview()),
# and says when it's over (finished()). See game.py and docs/making-games.md.
#
# On the board, with move / pick / back (move back and the arrows step too):
#   Setup     Press pick to join. Each player then sets their own fields (a seat, a color, a side...) on their own
#             bar: move steps through the choices, pick takes one, back goes back a field; back on the first one
#             leaves. The first to join leads: after their own fields they set the game's other fields (how many
#             play, the difficulty...), and last their bar breathes green: pick starts the game. Back there goes
#             back through the fields. With nobody joined, back opens the game picker.
#   Games     The island shows a game's card, the chooser's bar which game it is (a light each). Move steps, pick
#             plays that game (its setup; the same game, mid-game: its setup again), back returns to where it was.
#   Menu      From any game, at any time: menu (a wired button held MENU_HOLD_S, the console's q, the USB page's Menu)
#             pauses the game and asks first, so it never happens by accident: the asker's bar goes green with one
#             red light somewhere along it. Move the white light to the red one and pick: the game picker. Pick
#             anywhere green, back, or wait CONFIRM_S: back to the game as it was. In the setup, menu opens the
#             picker at once.
#   Playing   The game has the controllers until it says it's over (finished()).
#   End       The game's last picture stays. Pick plays again with the same setup; back returns to the setup with
#             everyone still in it, the leader on the start, so anyone can change their fields.
# A controller without back (one switch) gets a way-back stop after the last choice of every list: its bar dim red.
# At the end of a game, its move goes to that stop and back (a scanning switch steps by itself, so it never leaves
# the game's picture on its own).
# A game with no setup form (paint, the clock) just runs: only menu leaves it.
#
# The bars: a list of choices shows a light per choice (in the choice's color, if it has one), the one chosen
# flashing; a "fill" field (how many, a level) lights as many as its value. A joined player who's done waits with a
# dim bar (the game's preview may draw over it). Before anyone joins, connected controllers' bars breathe: pick to
# join. A setup the game turns down blinks the leader's bar red (the reason goes to the console).

import sys
from . import fx

OFF = (0, 0, 0)
WHITE = (255, 255, 255)
DIM = (24, 24, 24)
GREEN = (0, 255, 40)
RED = (255, 0, 0)
BAR = 10
START = "start"                          # the leader's last step
DONE = None                              # a player whose fields are all set
BACKSTOP = "back"                        # the way-back stop of a controller without back

FLASH = fx.flash(0.6, WHITE)
BREATHE = fx.breathe(2.0, low=0.2)
GO = fx.breathe(1.2, low=0.3)
ERROR = fx.blink(0.6)
ERROR_S = 2.0
CONFIRM_S = 30.0                         # the menu's question goes away by itself after this
STEP = {"move": 1, "right": 1, "up": 1, "move_back": -1, "left": -1, "down": -1}


def dim(c, k=6):
    return (c[0] // k, c[1] // k, c[2] // k)


class Lobby:
    def __init__(self, host):
        self.host = host
        self.state = "play"
        self.last = None                 # the choices the last game started with
        self.last_joined = []
        self.card = None                 # (name, draw function or None) of the card shown in the picker
        self.peeked = []                 # games whose code the picker loaded for their cards
        self.resume = "setup"            # where the picker or the menu's question goes back to
        self.asker = None                # the menu's question: who asked, the red light, the white one, until
        self.red = 0
        self.at_light = 0
        self.until = 0.0
        self.reset()

    # ---- the game running, and its form ----
    @property
    def game(self):
        return self.host.game

    @property
    def controllers(self):
        return self.host.board.controllers

    def reset(self):
        """A new game object (power-up, a switch, the USB page's New game): its setup, or straight into play if it
        has no setup form."""
        self.choices = {}
        self.joined = []
        self.at = {}                     # controller id -> the key it's setting (DONE: all set)
        self.stop = {}                   # controller id -> True while on its way-back stop
        self.error = None                # (controller, until)
        self.last = None
        self.last_joined = []
        self.fields = []
        self.refresh(fresh=True)
        self.state = "setup" if self.fields else "play"

    def form(self):
        try:
            return self.game.options(self.choices) or []
        except TypeError:                # an older game: options() without the choices
            return self.game.options() or []

    def refresh(self, fresh=False):
        """The game's form for the choices so far; values no longer allowed go back to a default."""
        self.fields = self.form()
        joined_ids = [c.id for c in self.joined]
        for f in self.fields:
            k = f["key"]
            p = f.get("player")
            if f.get("board", True) is False:
                self.choices[k] = str(f.get("value", ""))      # the game works it out from the rest
            elif p is not None and p not in joined_ids and "out" in f:
                self.choices[k] = f["out"]
            elif fresh or k not in self.choices or self.choices[k] not in self.allowed(f):
                ok = self.allowed(f)
                v = str(f.get("value", ""))
                self.choices[k] = v if v in ok else (ok[0] if ok else v)
        keys = [f["key"] for f in self.fields]
        for k in list(self.choices):
            if k not in keys:
                del self.choices[k]
        lead = self.leader()
        for c in self.joined:
            steps = self.steps(c)
            a = self.at.get(c.id, DONE)
            if a is DONE and c is lead:
                self.at[c.id] = self.first_shared()
            elif a is not DONE and a not in steps:          # a field that went (a level, once two play)
                if c is lead and a not in self.own_keys(c):
                    self.at[c.id] = self.first_shared()
                else:
                    self.at[c.id] = steps[0] if steps else DONE

    def field(self, key):
        for f in self.fields:
            if f["key"] == key:
                return f
        return None

    def allowed(self, f):
        """The values f can take now: not its sit-out value, nor one another player has in the same unique group."""
        out = f.get("out")
        vals = [str(ch[0]) for ch in f["choices"] if str(ch[0]) != out]
        group = f.get("unique")
        if group and f.get("player") is not None:
            taken = []
            for g in self.fields:
                if g.get("unique") == group and g.get("player") != f["player"]:
                    if any(c.id == g["player"] for c in self.joined):
                        taken.append(self.choices.get(g["key"]))
            vals = [v for v in vals if v not in taken]
        return vals

    def leader(self):
        return self.joined[0] if self.joined else None

    def shown(self, f):
        return f.get("board", True) is not False

    def own_keys(self, c):
        return [f["key"] for f in self.fields if f.get("player") == c.id and self.shown(f)]

    def shared_keys(self):
        return [f["key"] for f in self.fields if f.get("player") is None and self.shown(f)]

    def first_shared(self):
        s = self.shared_keys()
        return s[0] if s else START

    def steps(self, c):
        keys = self.own_keys(c)
        if c is self.leader():
            keys = keys + self.shared_keys() + [START]
        return keys

    def editing(self, c):
        """The key controller c is setting (START: about to start), or None (not joined, or done)."""
        return self.at.get(c.id, DONE) if c in self.joined else None

    @property
    def paused(self):
        """The game waits (no update) unless it's being played or showing its end: while the menu asks, in the
        picker, and in the setup (a game left mid-way doesn't carry on unseen)."""
        return self.state not in ("play", "end")

    # ---- events ----
    def event(self, c, a, now):
        if a == "menu":
            self.menu(c, now)
        elif self.state == "play":
            self.game.event(c, a, now)
        elif self.state == "confirm":
            self.confirm_event(c, a, now)
        elif self.state == "end":
            self.end_event(c, a, now)
        elif self.state == "games":
            self.games_event(c, a, now)
        else:
            self.setup_event(c, a, now)

    def update(self, now):
        if self.state == "play" and self.game.finished():
            self.state = "end"
            self.stop = {}
        elif self.state == "confirm" and now >= self.until:
            self.state = self.resume

    # ---- menu: back to the game picker from anywhere ----
    def menu(self, c, now):
        if self.state in ("games", "confirm"):
            return
        if self.state == "setup":
            self.open_games(c)
            return
        self.resume = self.state
        self.state = "confirm"
        self.asker = c
        self.at_light = 0
        self.red = 1 + int(now * 997) % (BAR - 1)            # anywhere but where the white light starts
        self.until = now + CONFIRM_S

    def confirm_event(self, c, a, now):
        if c is not self.asker:
            return
        d = STEP.get(a, 0)
        if d:
            self.at_light = (self.at_light + d) % BAR
        elif a == "pick" and self.at_light == self.red:
            self.open_games(c, self.resume)
        elif a in ("pick", "back"):
            self.state = self.resume

    def controller_added(self, c, now):
        if self.state == "setup":
            self.refresh()

    def controller_removed(self, c, now):
        if c in self.joined:
            self.leave(c)
        elif self.state == "setup":
            self.refresh()

    def join(self, c):
        self.joined.append(c)
        for f in self.fields:
            if f.get("player") == c.id and "out" in f:
                self.choices[f["key"]] = ""                   # anything but out: refresh picks a free one
        self.refresh()
        for f in self.fields:                                 # its own default where that's free
            if f.get("player") == c.id:
                v = str(f.get("value", ""))
                if v in self.allowed(f):
                    self.choices[f["key"]] = v
        steps = self.steps(c)
        self.at[c.id] = steps[0] if steps else DONE
        self.refresh()

    def leave(self, c):
        self.joined.remove(c)
        self.at.pop(c.id, None)
        self.stop.pop(c.id, None)
        self.refresh()

    def setup_event(self, c, a, now):
        if c not in self.joined:
            if a == "pick":
                self.join(c)
            elif a == "back" and not self.joined:
                self.open_games(c)
            return
        key = self.at.get(c.id, DONE)
        steps = self.steps(c)
        d = STEP.get(a, 0)
        on_stop = self.stop.get(c.id, False)
        no_back = "back" not in c.can
        if key is DONE:
            if a == "back" or (a == "pick" and no_back):
                self.go_back(c, steps, len(steps))
            return
        if d:
            if key == START:
                if no_back:
                    self.stop[c.id] = not on_stop
                return
            f = self.field(key)
            vals = self.allowed(f)
            if no_back:
                vals = vals + [BACKSTOP]
            cur = BACKSTOP if on_stop else self.choices.get(key)
            i = vals.index(cur) if cur in vals else -1
            nxt = vals[(i + d) % len(vals)] if vals else cur
            self.stop[c.id] = nxt == BACKSTOP
            if nxt != BACKSTOP:
                self.choices[key] = nxt
                self.refresh()
            return
        if a == "back" or (a == "pick" and on_stop):
            self.stop[c.id] = False
            self.go_back(c, steps, steps.index(key))
        elif a == "pick":
            if key == START:
                self.start(c, now)
                return
            i = steps.index(key)
            self.at[c.id] = steps[i + 1] if i + 1 < len(steps) else DONE
            self.refresh()

    def go_back(self, c, steps, i):
        if i <= 0:
            self.leave(c)
        else:
            self.at[c.id] = steps[i - 1]
            self.refresh()

    def start(self, c, now):
        choices = dict(self.choices)
        try:
            msg = self.game.setup(choices, now)
        except Exception as e:           # a game's bug shouldn't stop the board
            msg = "the game couldn't start (%r)" % (e,)
        if msg is not None:
            print(msg)
            self.error = (c, now + ERROR_S)
            return
        self.started(choices)

    def started(self, choices):
        """A game began with these choices (on the board, or from the USB page: then whoever has a player field that
        isn't sitting out played)."""
        self.choices = dict(choices)     # (from the page: its choices, so the seats are the ones being played)
        self.last = dict(choices)
        outs = [f for f in self.fields if f.get("player") is not None and "out" in f]
        if outs:
            played = [c for c in self.controllers
                      if any(f["player"] == c.id and choices.get(f["key"], f["out"]) != f["out"] for f in outs)]
            self.joined = [c for c in self.joined if c in played] + [c for c in played if c not in self.joined]
        self.last_joined = list(self.joined)
        self.state = "play"

    def end_event(self, c, a, now):
        if "back" not in c.can and STEP.get(a, 0):
            self.stop[c.id] = not self.stop.get(c.id, False)
            return
        if a == "pick" and self.stop.get(c.id):
            a = "back"
        if a == "pick":
            joined = self.last_joined
            msg = None
            try:
                msg = self.game.setup(dict(self.last), now) if self.last is not None else "no game to repeat"
            except Exception as e:
                msg = "the game couldn't start (%r)" % (e,)
            if msg is None:
                self.last_joined = joined
                self.state = "play"
                return
            print(msg)
            self.back_to_setup()
        elif a == "back":
            self.back_to_setup()

    def back_to_setup(self):
        """Setup again with the last game's choices and players: the leader on the start, the others done."""
        self.state = "setup"
        if self.last is not None:
            self.choices = dict(self.last)
        here = self.controllers
        self.joined = [c for c in self.last_joined if c in here]
        self.at = {}
        self.stop = {}
        self.refresh()
        lead = self.leader()
        for c in self.joined:
            self.at[c.id] = START if c is lead else DONE
        self.refresh()

    # ---- the game picker ----
    def open_games(self, c, resume="setup"):
        from . import host
        self.names = host.game_names()
        self.chooser = c
        self.resume = resume
        self.state = "games"
        self.stop = {}
        self.index = self.names.index(self.host.name) if self.host.name in self.names else 0

    def games_event(self, c, a, now):
        if c is not self.chooser:
            return
        d = STEP.get(a, 0)
        n = len(self.names)
        no_back = "back" not in c.can
        on_stop = self.stop.get(c.id, False)
        if d:
            k = (n if on_stop else self.index) + d
            k %= n + 1 if no_back else n
            self.stop[c.id] = k == n
            if k < n:
                self.index = k
        elif a == "back" or (a == "pick" and on_stop):
            self.close_games()
            self.state = self.resume
        elif a == "pick":
            name = self.names[self.index]
            self.close_games()
            if name == self.host.name:                        # this game again: its setup (a new game)
                if self.resume == "setup" or not self.fields:
                    self.state = self.resume
                else:
                    self.back_to_setup()
                return
            msg = self.host.apply("game", name, now)          # (remembered for power-up, as from the USB page)
            if msg is not None:
                print(msg)
                self.state = self.resume

    def close_games(self):
        from . import host
        self.stop = {}
        self.card = None
        for name in self.peeked:
            if name != self.host.name:
                host.unload_game(name)
        self.peeked = []
        import gc
        gc.collect()

    def card_of(self, name):
        """The draw(lights, now) of a game's card: games/NAME/card.py, or card() in games/NAME.py; None if it has
        none or there's no room to load it."""
        if self.card is not None and self.card[0] == name:
            return self.card[1]
        self.card = None
        fn = None
        path = "games." + name
        was = path in sys.modules
        try:
            try:
                mod = __import__(path + ".card", None, None, ["draw"])
                fn = getattr(mod, "draw", None)
            except ImportError:
                mod = __import__(path, None, None, ["card"])
                fn = getattr(mod, "card", None)
        except Exception as e:           # (MemoryError too: the default card)
            print("game picker: %s's card didn't load (%r)" % (name, e))
            fn = None
        if not was and name not in self.peeked:
            self.peeked.append(name)
        self.card = (name, fn)
        return fn

    # ---- drawing ----
    def draw(self, lights, now):
        self.carry_bars(lights)
        if self.state == "confirm":
            self.game.draw(lights, now)
            seat = self.seat_of(self.asker)
            lights.bar(seat, [WHITE if i == self.at_light else RED if i == self.red else GREEN for i in range(BAR)],
                       [FLASH if i == self.at_light else None for i in range(BAR)])
        elif self.state in ("play", "end"):
            self.game.draw(lights, now)
            if self.state == "end":
                for c in self.controllers:
                    if self.stop.get(c.id):
                        lights.bar(self.seat_of(c), [dim(RED, 4)] * BAR)
        elif self.state == "games":
            self.draw_games(lights, now)
        else:
            self.draw_setup(lights, now)

    def bar_seats(self):
        """Where each joined player's bar is: the seat a seat field gives it, else its controller's, else a free one."""
        out = {}
        used = []
        later = []
        for c in self.joined:
            s = None
            for f in self.fields:
                if f.get("player") == c.id and f.get("seat"):
                    v = self.choices.get(f["key"], "")
                    s = int(v) if v.isdigit() else None
            if s is None and c.seat and c.seat not in used:
                s = c.seat
            if s is None:
                later.append(c)
            else:
                out[c.id] = s
                used.append(s)
        for c in later:
            free = [x for x in (1, 4, 2, 5, 3, 6) if x not in used]
            out[c.id] = free[0] if free else 1
            used.append(out[c.id])
        return out

    def seat_of(self, c, seats=None):
        """The seat whose bar is c's player's: where it plays once joined (bar_seats), else its controller's seat."""
        if seats is None:
            seats = self.bar_seats()
        return seats.get(c.id, c.seat or 1)

    def carry_bars(self, lights):
        """A controller carrying a bar (Controller.bar) takes it to the seat it plays at, so the bar in the player's
        hands shows their own seat (lights.carry). Joined players first; a seat or bar already taken stays put."""
        seats = self.bar_seats()
        out = {}
        for c in self.joined + [c for c in self.controllers if c not in self.joined]:
            if c.bar and c.connected:
                s = self.seat_of(c, seats)
                if s not in out and c.bar not in out.values():
                    out[s] = c.bar
        lights.carry(out)

    def draw_setup(self, lights, now):
        seats = self.bar_seats()
        for c in self.joined:
            if self.at.get(c.id, DONE) is DONE:
                lights.bar(seats[c.id], [DIM] * BAR)
        self.game.preview(lights, now, self)
        if not self.joined:
            for c in self.controllers:
                lights.bar(self.seat_of(c, seats), [DIM] * BAR, BREATHE)
            return
        for c in self.joined:
            seat = seats[c.id]
            if self.error and self.error[0] is c and now < self.error[1]:
                lights.bar(seat, [RED] * BAR, ERROR)
                continue
            key = self.at.get(c.id, DONE)
            if key is DONE:
                continue
            if self.stop.get(c.id):
                lights.bar(seat, [dim(RED, 4)] * BAR)
            elif key == START:
                lights.bar(seat, [GREEN] * BAR, GO)
            else:
                self.draw_field(lights, seat, self.field(key))

    def draw_field(self, lights, seat, f):
        vals = self.allowed(f)
        cur = self.choices.get(f["key"])
        color = f.get("color") or WHITE
        if f.get("bar") == "fill":
            n = int(cur) if cur and cur.isdigit() else vals.index(cur) + 1 if cur in vals else 0
            lights.bar(seat, [color if i < n else OFF for i in range(BAR)])
            return
        colors = {}
        for ch in f["choices"]:
            if len(ch) > 2 and ch[2]:
                colors[str(ch[0])] = ch[2]
        out = [OFF] * BAR
        effects = [None] * BAR
        for i, v in enumerate(vals[:BAR]):
            c = colors.get(v, WHITE)
            out[i] = c if v == cur else dim(c)
            effects[i] = FLASH if v == cur else None
        lights.bar(seat, out, effects)

    def draw_games(self, lights, now):
        name = self.names[self.index]
        fn = self.card_of(name)
        drawn = False
        if fn is not None:
            try:
                fn(lights, now)
                drawn = True
            except Exception:
                drawn = False
        if not drawn:
            from . import geometry as G
            for t in G.neighbors(G.CENTER):
                lights.spot(t, [DIM] * 3)
            lights.spot(G.CENTER, [WHITE] * 3, BREATHE)
        seat = self.seat_of(self.chooser)
        if self.stop.get(self.chooser.id):
            lights.bar(seat, [dim(RED, 4)] * BAR)
            return
        n = min(BAR, len(self.names))
        lights.bar(seat, [WHITE if i == self.index else DIM if i < n else OFF for i in range(BAR)],
                   [FLASH if i == self.index else None for i in range(BAR)])
