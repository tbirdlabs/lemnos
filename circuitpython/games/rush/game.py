# Island Rush on the board (docs/rules/island-rush-rules-v0.2.md): up to 6 players race through the jungle from
# the island's corners to the taco truck in the middle; a tiger chases the leader and guards the truck; the last one
# left on the truck after the tiger wins. The rules are engine.py, the computer players ai.py; this file is the
# board's side: setup, the play UI and drawing.
#
# Setup: any controller presses pick to join. Move picks a corner (each seat's is the left end of its side, as its
# player faces the board), pick takes it; move picks a color, pick takes it. The first to join then sets how many play
# in all, 2 to 6, on their bar (the computer plays the rest); pick starts once everyone has a color. Back undoes a
# step. The USB page can set it all up instead (options, setup).
#
# Playing, as in Salient: each player reads the island from their own side. Move steps through the rows that hold
# something you can pick, then your bar; pick opens a row, move steps through its spots, pick picks; back returns to
# the rows. Arrows move the cursor directly. A controller without back gets a way-out stop at the end of each row.
# Pick your own spot to add a light; pick jungle (or empty ground, or the truck) next to yours to see your chance on
# your bar, and pick again to go. Pick your bar to end your turn; it also ends when your bar is empty.
#
# The lights: jungle is green (1-3 lights, as players' lights), empty ground dark, the tiger orange lights running
# round its spot, the truck a slow white glow, or each player on it in turn, a second each. At the end of a round the
# tiger's rolls run along the bar of the player it attacks, over its chance in orange.

from gamehost import dice, fx, geometry
from gamehost.game import Game as BaseGame
from . import ai as AI
from . import engine as E

OFF = (0, 0, 0)
WHITE = (255, 255, 255)
DIM = (36, 36, 36)                       # the cursor glow on an unlit light
GREEN = (0, 255, 40)
RED = (255, 0, 0)
JUNGLE = (0, 70, 8)
TIGER = (255, 90, 0)
TRUCK = (200, 200, 200)
# Players' colors: none green (the jungle), orange (the tiger) or white (the truck and the cursor)
PALETTE = ((255, 20, 20), (30, 70, 255), (255, 220, 0), (150, 30, 255), (0, 200, 255), (255, 50, 160))
NAMES = ("red", "blue", "yellow", "purple", "cyan", "pink")
LIT = ((False, False, False), (False, True, False), (True, False, True), (True, True, True))   # 0-3 lights

BARPOS = geometry.ON_BAR
BARROW = 7
OUT = -2
FRAMES = geometry.VIEWS

CURSOR = fx.flash(0.5, WHITE, duty=0.4)
WINNER = fx.breathe(1.6, low=0.5)
CHOOSING = fx.blink(0.6, duty=0.6)
TRUCK_GLOW = fx.breathe(2.5, low=0.25)
PROWL = fx.chase(1.2, tail=1)
TIGER_MARK = fx.blink(0.5, duty=0.5)     # the spot the tiger is attacking
TRUCK_TURN = 1.0                         # seconds each player on the truck is shown

AI_PAUSE = 1.0
AI_HOP = 0.16
AI_AIM = 1.0
AI_ADD = 0.45
TIGER_PAUSE = 0.6


def draw_spot(lights, t, u, color, glow=False, effect=None):
    """u lights in color (1 = the middle LED, 2 = the outer two, 3 = all). Under the cursor (glow) the lit lights
    flash white and the empty ones glow dim white."""
    lit = LIT[min(3, u)]
    colors = []
    effects = []
    for i in range(3):
        if lit[i]:
            colors.append(color)
            effects.append(CURSOR if glow else effect)
        else:
            colors.append(DIM if glow else OFF)
            effects.append(None)
    lights.spot(t, colors, effects)


def cycle(lst, cur, d):
    if cur in lst:
        return lst[(lst.index(cur) + d) % len(lst)]
    return lst[0]


def _gaps(seats):
    s = sorted(seats)
    return [(s[(i + 1) % len(s)] - s[i]) % 6 or 6 for i in range(len(s))]


def _combos(items, k):
    if k == 0:
        return [[]]
    out = []
    for i in range(len(items) - k + 1):
        for rest in _combos(items[i + 1:], k - 1):
            out.append([items[i]] + rest)
    return out


def spread_seats(humans, total):
    """The seats of a game of `total` around the humans' seats, the computers spread as evenly as they can; None if
    it can't be done (more humans than total)."""
    if total < len(humans) or total < 1:
        return None
    free = [x for x in range(1, 7) if x not in humans]
    best = None
    for combo in _combos(free, total - len(humans)):
        seats = sorted(list(humans) + combo)
        g = _gaps(seats)
        key = (max(g), sum(x * x for x in g), seats)
        if best is None or key < best[0]:
            best = (key, seats)
    return best[1]


class Joiner:
    """A player during setup: choosing a corner, then a color."""

    def __init__(self, c, seat):
        self.c = c
        self.stage = "side"              # side, color, done (the first player: total)
        self.seat = seat
        self.color = 0


class Seat:
    def __init__(self, seat, color, ctrl):
        self.seat = seat
        self.color = color
        self.ctrl = ctrl
        self.frame = FRAMES[seat]
        self.pos = E.corner_of(seat)


class Game(BaseGame):
    def __init__(self, board):
        BaseGame.__init__(self, board)
        self.timer_at = None
        self.timer_fn = None
        self._items = None
        self.enter_setup()

    # ---- one pending step at a time (animations, the computer) ----
    def after(self, now, dt, fn):
        self.timer_at = now + dt
        self.timer_fn = fn

    def update(self, now):
        if self.timer_at is not None and now >= self.timer_at:
            fn = self.timer_fn
            self.timer_at = None
            self.timer_fn = None
            fn(now)

    # =========================================================================
    # Setup
    # =========================================================================
    def enter_setup(self):
        self.phase = "join"
        self.leader = None
        self.joiners = []
        self.total = 2
        self.st = None
        self.timer_at = None
        self.preview = E.new_game((), 1)            # the jungle, for the setup screen

    def joiner(self, c):
        for j in self.joiners:
            if j.c is c:
                return j
        return None

    def taken_seats(self, but=None):
        return [j.seat for j in self.joiners if j is not but and j.stage != "side"]

    def taken_colors(self, but=None):
        return [j.color for j in self.joiners if j is not but and j.stage not in ("side", "color")]

    def human_seats(self):
        return sorted(j.seat for j in self.joiners if j.stage != "side")

    def valid_totals(self):
        h = self.human_seats()
        return [t for t in range(max(2, len(h)), 7)]

    def fix_total(self):
        v = self.valid_totals()
        if v and self.total not in v:
            bigger = [t for t in v if t >= self.total]
            self.total = bigger[0] if bigger else v[-1]

    def all_ready(self):
        return bool(self.joiners) and all(j.stage in ("done", "total") for j in self.joiners)

    def join(self, c):
        free = [x for x in range(1, 7) if x not in self.taken_seats()]
        if not free:
            return
        if not self.joiners:
            self.leader = c
        self.joiners.append(Joiner(c, c.seat if c.seat in free else free[0]))
        self.fix_total()

    def setup_event(self, c, a, now):
        step = 1 if a in ("move", "right", "up") else (-1 if a in ("move_back", "left", "down") else 0)
        j = self.joiner(c)
        if j is None:
            if a == "pick":
                self.join(c)
            return
        lead = c is self.leader
        if j.stage == "side":
            free = [x for x in range(1, 7) if x not in self.taken_seats(j)]
            if step and free:
                j.seat = cycle(free, j.seat, step)
            elif a == "pick" and j.seat in free:
                j.stage = "color"
                colors = [k for k in range(len(PALETTE)) if k not in self.taken_colors(j)]
                j.color = colors[0]
            elif a == "back":
                self.joiners.remove(j)
                if lead:
                    self.leader = self.joiners[0].c if self.joiners else None
        elif j.stage == "color":
            colors = [k for k in range(len(PALETTE)) if k not in self.taken_colors(j)]
            if step:
                j.color = cycle(colors, j.color, step)
            elif a == "pick" and j.color in colors:
                j.stage = "total" if lead else "done"
            elif a == "back":
                j.stage = "side"
        elif j.stage == "done":
            if a == "back":
                j.stage = "color"
        elif j.stage == "total":
            v = self.valid_totals()
            if step and v:
                self.total = cycle(v, self.total, step)
            elif a == "pick" and self.all_ready() and self.total in v:
                self.start(now)
                return
            elif a == "back":
                j.stage = "color"
        self.fix_total()

    def lineup(self):
        """(seat, color, controller or None) for every player, seat order (turn order starts at the lowest seat)."""
        h = self.human_seats()
        seats = spread_seats(h, self.total) or h
        used = [j.color for j in self.joiners if j.stage != "side"]
        spare = [k for k in range(len(PALETTE)) if k not in used]
        out = []
        for x in seats:
            j = None
            for jj in self.joiners:
                if jj.stage != "side" and jj.seat == x:
                    j = jj
            if j:
                out.append((x, PALETTE[j.color], j.c))
            else:
                out.append((x, PALETTE[spare.pop(0)], None))
        return out

    def start(self, now, seed=None, lineup=None):
        lineup = lineup or self.lineup()
        self.st = E.new_game(tuple(x[0] for x in lineup), dice.seed() if seed is None else seed)
        self.st.tiger_log = []
        self.seats = [Seat(x[0], x[1], x[2]) for x in lineup]
        self.phase = "play"
        self.timer_at = None
        self.mode_ui = "board"           # board | aim
        self.aim = -1
        self.roll = None                 # (player, chance, dice.Roll, background colors) while a roll runs
        self.disp = None                 # the board as it was, shown while a roll runs
        self.tiger_queue = []            # the tiger's rolls still to show: (spot, player, roll, chance)
        self.tiger_mark = -1
        self.logged = 0
        self.busy = False
        self.changed()
        self.cursor = self.cur().pos
        self.start_scan()
        self.schedule_ai(now)

    # ---- the USB page ----
    def options(self):
        ctrls = self.board.controllers
        seats = [(str(x), "Seat %d" % x) for x in range(1, 7)]
        out = [{"key": "players", "label": "Players", "value": str(max(2, min(6, len(ctrls)))),
                "choices": [(str(n), "%d players" % n) for n in range(2, 7)],
                "note": "The computer plays any seat no one takes."}]
        taken = []
        for c in ctrls:                  # each controller at its own seat, or the next free one
            free = [x for x in range(1, 7) if x not in taken]
            seat = c.seat if c.seat in free else (free[0] if free else 0)
            if seat:
                taken.append(seat)
            out.append({"key": "seat:" + c.id, "label": c.name, "value": str(seat) if seat else "out",
                        "choices": [("out", "Sits out")] + seats})
        return out

    def setup(self, choices, now):
        humans = {}
        for c in self.board.controllers:
            s = choices.get("seat:" + c.id, "out")
            if s == "out":
                continue
            if not s.isdigit() or not 1 <= int(s) <= 6:
                return "Pick a seat from 1 to 6 for %s." % c.name
            if int(s) in humans:
                return "%s and %s are both at seat %s." % (humans[int(s)].name, c.name, s)
            humans[int(s)] = c
        p = choices.get("players", "2")
        total = int(p) if p.isdigit() else 2
        if not 2 <= total <= 6:
            return "Island Rush is for 2 to 6 players."
        if total < len(humans):
            return "%d controllers are playing, more than %d players." % (len(humans), total)
        seats = spread_seats(sorted(humans), total)
        self.start(now, lineup=[(x, PALETTE[k], humans.get(x)) for k, x in enumerate(seats)])
        return None

    # =========================================================================
    # Playing
    # =========================================================================
    def cur(self):
        return self.seats[self.st.cur]

    def human(self):
        return self.st is not None and not self.st.over and self.cur().ctrl is not None

    def changed(self):
        self.view = None
        self._items = None

    def start_scan(self):
        s = self.cur()
        self.level_ui = "row"
        self.row = BARROW if s.pos == BARPOS else s.frame.row[s.pos]

    def items(self):
        if self._items is None:
            st = self.st
            p = st.cur
            fr = self.cur().frame
            out = [t for t in range(E.N) if E.can_add(st, p, t) or E.can_clear(st, p, t)]
            out.sort(key=lambda t: fr.order[t])
            out.append(BARPOS)
            self._items = out
        return self._items

    def row_list(self, items):
        fr = self.cur().frame
        rows = []
        for t in items:
            if t != BARPOS and fr.row[t] not in rows:
                rows.append(fr.row[t])
        rows.append(BARROW)
        return rows

    def row_spots(self, items, r):
        fr = self.cur().frame
        return [t for t in items if t != BARPOS and fr.row[t] == r]

    def can_back(self):
        return "back" in self.cur().ctrl.can

    @staticmethod
    def step_in(lst, cur, d):
        if cur in lst:
            return lst[(lst.index(cur) + d) % len(lst)]
        return lst[0] if d > 0 else lst[-1]

    def play_event(self, c, a, now):
        st = self.st
        if st.over:
            if a == "pick" and not self.busy:
                self.enter_setup()
            return
        if self.busy or not self.human() or c is not self.cur().ctrl:
            return
        p = st.cur
        fr = self.cur().frame
        items = self.items()
        if a == "back":
            if self.mode_ui == "aim":
                self.mode_ui = "board"
                self.aim = -1
            elif self.level_ui == "spot":
                self.to_rows()
        elif a == "pick":
            if self.level_ui == "row":
                if self.row == BARROW:
                    self.act(E.V_END, -1, now)
                else:
                    rs = self.row_spots(items, self.row)
                    if rs:
                        self.level_ui = "spot"
                        self.cursor = rs[0]
                return
            t = self.cursor
            if t == OUT:
                self.level_ui = "row"
            elif self.mode_ui == "aim":
                if t == self.aim:
                    self.act(E.V_CLEAR, t, now)
            elif t == BARPOS:
                self.act(E.V_END, -1, now)
            elif E.can_add(st, p, t):
                self.act(E.V_ADD, t, now)
            elif E.can_clear(st, p, t):
                self.mode_ui = "aim"
                self.aim = t
        else:
            self.mode_ui = "board"
            self.aim = -1
            if a in ("move", "move_back"):
                d = 1 if a == "move" else -1
                spots = []
                if self.level_ui == "spot" and self.cursor not in (BARPOS, OUT):
                    self.row = fr.row[self.cursor]
                if self.level_ui == "spot" and self.cursor != BARPOS:
                    spots = self.row_spots(items, self.row)
                if spots and not self.can_back():
                    spots = spots + [OUT]
                if not spots:
                    if self.level_ui == "spot":
                        self.to_rows()
                    self.row = self.step_in(self.row_list(items), self.row, d)
                else:
                    self.cursor = self.step_in(spots, self.cursor, d)
            else:                                           # arrows
                if self.level_ui == "row" or self.cursor == OUT:
                    if self.row == BARROW:
                        self.cursor = BARPOS
                    elif self.cursor in (BARPOS, OUT) or fr.row[self.cursor] != self.row:
                        rw = fr.rows[self.row]
                        self.cursor = rw[len(rw) // 2]
                    self.level_ui = "spot"
                self.cursor = fr.arrow(self.cursor, a)

    def to_rows(self):
        fr = self.cur().frame
        self.level_ui = "row"
        if self.cursor == BARPOS:
            self.row = BARROW
        elif self.cursor != OUT:
            self.row = fr.row[self.cursor]

    # ---- doing a move: a clearing roll runs the white light along the bar over the chance ----
    def act(self, verb, t, now):
        st = self.st
        p = st.cur
        self.mode_ui = "board"
        self.aim = -1
        if t >= 0:
            self.seats[p].pos = t
        rolled = verb == E.V_CLEAR and E.jungle(st, t) > 0
        before = self.make_view()
        c = E.chance(st, p, t) if rolled else 0
        roll = E.apply(st, verb, t)
        self.changed()
        new = st.tiger_log[self.logged:]
        self.logged = len(st.tiger_log)
        for spot, who, rolls in new:
            for r, ch in rolls:
                self.tiger_queue.append((spot, who, r, ch))
        if rolled:
            self.busy = True
            self.disp = before
            bg = [GREEN if i < c else RED for i in range(E.BAR)]
            self.roll = (p, c, dice.Roll(now, roll, E.BAR), bg)
            self.after(now, self.roll[2].duration, self.roll_done)
            return
        if self.tiger_queue:
            self.disp = before
        self.after_move(p, now)

    def roll_done(self, now):
        p = self.roll[0]
        self.roll = None
        self.busy = False
        if not self.tiger_queue:
            self.disp = None
        self.after_move(p, now)

    def after_move(self, p, now):
        if self.tiger_queue:                                 # the round ended: the tiger first
            self.busy = True
            self.after(now, TIGER_PAUSE, self.tiger_roll)
            return
        self.disp = None
        if not self.st.over and self.st.cur != p:
            self.cursor = self.cur().pos
            self.start_scan()
        elif not self.st.over and self.human():
            if self.cursor not in self.items() and self.cursor not in (OUT,):
                self.start_scan()
        self.schedule_ai(now)

    def tiger_roll(self, now):
        spot, who, r, ch = self.tiger_queue.pop(0)
        self.tiger_mark = spot
        bg = [TIGER if i < ch else self.seats[who].color for i in range(E.BAR)]
        self.roll = (who, ch, dice.Roll(now, r, E.BAR, laps=0), bg)     # quicker than a player's: there can be many
        self.after(now, self.roll[2].duration + 0.3, self.tiger_done)

    def tiger_done(self, now):
        self.roll = None
        if self.tiger_queue:
            self.after(now, 0.3, self.tiger_roll)
            return
        self.tiger_mark = -1
        self.busy = False
        self.disp = None
        self.changed()
        self.cursor = self.cur().pos if not self.st.over else self.cursor
        if not self.st.over:
            self.start_scan()
        self.schedule_ai(now)

    # ---- the computer: the cursor walks to the spot, the chance shows, then it picks ----
    def schedule_ai(self, now):
        if self.st.over or self.cur().ctrl is not None or self.busy:
            return
        self.busy = True
        self.after(now, AI_PAUSE, self.ai_step)

    def ai_step(self, now):
        verb, t = AI.choose(self.st, "beginner")
        target = BARPOS if verb == E.V_END else t
        start = self.cursor if self.cursor >= 0 or self.cursor == BARPOS else self.cur().pos
        self.ai_path = self.cur().frame.path(start, target)
        self.ai_move = (verb, t, target)
        self.level_ui = "spot"
        self.ai_hop(now)

    def ai_hop(self, now):
        if self.ai_path:
            self.cursor = self.ai_path.pop(0)
            self.after(now, AI_HOP, self.ai_hop)
            return
        verb, t, target = self.ai_move
        self.cursor = target
        if verb == E.V_CLEAR:
            self.mode_ui = "aim"
            self.aim = t
        self.after(now, AI_AIM if verb == E.V_CLEAR else AI_ADD, lambda n: self.ai_act(verb, t, n))

    def ai_act(self, verb, t, now):
        self.busy = False
        self.act(verb, t, now)

    # =========================================================================
    # Input and drawing
    # =========================================================================
    def event(self, c, a, now):
        if self.phase == "play":
            self.play_event(c, a, now)
        else:
            self.setup_event(c, a, now)

    def make_view(self):
        st = self.st
        return (list(st.owner), list(st.units), list(st.truck), [pl.bar for pl in st.players], list(st.tigers))

    def draw(self, lights, now):
        if self.phase == "play":
            self.draw_play(lights, now)
        else:
            self.draw_setup(lights)

    def draw_jungle(self, lights, units, owner, tigers, skip=()):
        for t in range(E.N):
            if t in skip or t == E.CENTER or owner[t] >= 0:
                continue
            if t in tigers:
                lights.spot(t, [TIGER] * 3, PROWL)
            elif units[t] > 0:
                draw_spot(lights, t, units[t], JUNGLE)

    def draw_setup(self, lights):
        pv = self.preview
        corners = [E.corner_of(x) for x in range(1, 7)]
        self.draw_jungle(lights, pv.units, pv.owner, (), corners)
        lights.spot(E.CENTER, [TRUCK] * 3, TRUCK_GLOW)
        lead = self.joiner(self.leader) if self.leader is not None else None
        if lead is not None and lead.stage == "total":
            for x, color, c in self.lineup():
                if c is None:
                    draw_spot(lights, E.corner_of(x), 1, color)
        for j in self.joiners:
            color = WHITE if j.stage == "side" else PALETTE[j.color]
            effect = CHOOSING if j.stage in ("side", "color") else None
            lights.spot(E.corner_of(j.seat), [color] * 3, effect)
            if j.stage == "total":
                lights.bar(j.seat, [color if i < self.total else OFF for i in range(E.BAR)])
            else:
                lights.bar(j.seat, [color] * E.BAR, effect)

    def draw_play(self, lights, now):
        st = self.st
        if self.view is None:
            self.view = self.make_view()
        owner, units, truck, bars, tigers = self.disp or self.view
        glow = self.glow_set()
        self.draw_jungle(lights, units, owner, tigers)
        for t in range(E.N):
            if t == E.CENTER:
                continue
            o = owner[t]
            if o < 0:
                if t in glow and t not in tigers:
                    if units[t] > 0:
                        draw_spot(lights, t, units[t], JUNGLE, True)
                    else:
                        lights.spot(t, [DIM] * 3)
                continue
            effect = WINNER if st.over and st.winner == o else (TIGER_MARK if t == self.tiger_mark else None)
            draw_spot(lights, t, units[t], self.seats[o].color, t in glow, effect)
        self.draw_truck(lights, now, truck, units[E.CENTER], E.CENTER in glow)
        for p, s in enumerate(self.seats):
            r = self.roll
            if r is not None and r[0] == p:
                r[2].draw(lights, s.seat, r[3])
                continue
            effect = None
            if not st.over and p == st.cur and self.mode_ui == "aim" and self.aim >= 0 and self.roll is None:
                c = E.chance(st, p, self.aim)
                out = [GREEN if i < c else RED for i in range(E.BAR)]
            elif st.over and st.winner == p:
                out = [s.color] * E.BAR
                effect = WINNER
            else:
                out = [s.color if i < bars[p] else (DIM if (BARPOS in glow and p == st.cur) else OFF)
                       for i in range(E.BAR)]
            lights.bar(s.seat, out, effect)

    def draw_truck(self, lights, now, truck, jungle, glow):
        st = self.st
        on = [p for p in range(len(truck)) if truck[p] > 0]
        mark = TIGER_MARK if self.tiger_mark == E.CENTER else None
        if st.over and st.winner >= 0 and truck[st.winner] > 0:
            draw_spot(lights, E.CENTER, truck[st.winner], self.seats[st.winner].color, False, WINNER)
        elif on:
            p = on[int(now / TRUCK_TURN) % len(on)]
            draw_spot(lights, E.CENTER, truck[p], self.seats[p].color, glow, mark)
        elif jungle > 0:
            draw_spot(lights, E.CENTER, jungle, JUNGLE, glow)
        elif glow:
            lights.spot(E.CENTER, [TRUCK] * 3, CURSOR)
        else:
            lights.spot(E.CENTER, [TRUCK] * 3, TRUCK_GLOW)

    def glow_set(self):
        st = self.st
        if st.over or self.roll is not None or self.tiger_queue:
            return ()
        fr = self.cur().frame
        if self.cur().ctrl is not None and self.level_ui == "row":
            if self.row == BARROW:
                return (BARPOS,)
            rs = self.row_spots(self.items(), self.row)
            return rs if rs else fr.rows[self.row]
        if self.cursor == OUT:
            return fr.rows[self.row]
        return (self.cursor,)
