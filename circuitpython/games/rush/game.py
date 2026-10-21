# Island Rush on the board (docs/rules/island-rush-rules-v0.8.md): up to 6 players race through the jungle from the
# island's corners to the taco truck in the middle; tigers chase the leaders, and one guards the truck. One player holds
# the truck at a time (another rolls them off it); whoever holds it after the tiger at the end of a round wins. A tiger
# in your way can be fought off, and another player rolled off a spot. The rules are engine.py, the computer players
# ai.py; this file is the board's side: the setup's fields, the play UI and drawing.
#
# Setup (the board's lobby, gamehost/lobby.py, or the USB page): each player who joins picks a corner (each seat's is
# the left end of its side, as its player faces the board; the island shows it, white blinking) and then a color;
# the first to join then sets how many play in all, 2 to 6 (the computer plays the rest, spread round the board).
#
# Playing, as in Salient: each player reads the island from their own side. Move steps through the rows that hold
# something you can pick, then your bar; pick opens a row, move steps through its spots, pick picks; back returns to
# the rows. Arrows move the cursor directly. A controller without back gets a way-out stop at the end of each row.
# Pick your own spot to add a light; pick jungle (or empty ground, the truck, a tiger or another player's spot) next
# to yours to see your chance on your bar, and pick again to go. Pick your bar to end your turn; it also ends when your
# bar is empty.
#
# The lights: jungle is green (1-3 lights, as players' lights), empty ground dark, the tiger orange lights running
# round its spot, the truck a slow white glow, or its holder's lights. At the end of a round each
# tiger walks through the jungle a spot at a time to its leader's lead spot, then its rolls run along the bar of the
# player it attacks, over its chance in orange.

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
TIGER_STEP = 0.35                        # seconds a walking tiger takes a spot


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
        self.st = None                   # no game until setup()
        self.busy = False
        self.jungle = None               # the jungle alone, for the setup's preview

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
    # Setup (the lobby walks people through options(); see gamehost/game.py)
    # =========================================================================
    def options(self, choices=None):
        ctrls = self.board.controllers
        seats = [(str(x), "Seat %d" % x) for x in range(1, 7)]
        colors = [(str(k), NAMES[k], PALETTE[k]) for k in range(len(PALETTE))]
        if choices is None:              # the page: everyone playing to begin with
            least = 2
            n = max(2, min(6, len(ctrls)))
        else:
            humans = self.humans(choices)
            least = max(2, len(humans) if not isinstance(humans, str) else 0)
            p = choices.get("players", "")
            n = max(least, int(p)) if p.isdigit() else least
        out = [{"key": "players", "label": "Players", "value": str(n), "bar": "fill",
                "choices": [(str(k), "%d players" % k) for k in range(least, 7)],
                "note": "The computer plays any seat no one takes."}]
        taken = []
        for k, c in enumerate(ctrls):    # each controller at its own seat, or the next free one
            free = [x for x in range(1, 7) if x not in taken]
            seat = c.seat if c.seat in free else (free[0] if free else 0)
            if seat:
                taken.append(seat)
            out.append({"key": "seat:" + c.id, "label": c.name, "value": str(seat) if seat else "out",
                        "choices": [("out", "Sits out")] + seats, "player": c.id, "out": "out", "unique": "seat",
                        "seat": True})
            out.append({"key": "color:" + c.id, "label": c.name + ": color", "value": str(k % len(PALETTE)),
                        "choices": colors, "player": c.id, "unique": "color",
                        "show": {"seat:" + c.id: [str(x) for x in range(1, 7)]}})
        return out

    def humans(self, choices):
        """{seat: (controller, color index or -1)} for the controllers playing, or a message if the choices don't
        work."""
        out = {}
        used = []
        for c in self.board.controllers:
            s = choices.get("seat:" + c.id, "out")
            if s == "out":
                continue
            if not s.isdigit() or not 1 <= int(s) <= 6:
                return "Pick a seat from 1 to 6 for %s." % c.name
            if int(s) in out:
                return "%s and %s are both at seat %s." % (out[int(s)][0].name, c.name, s)
            k = choices.get("color:" + c.id, "")
            k = int(k) if k.isdigit() and int(k) < len(PALETTE) and int(k) not in used else -1
            used.append(k)
            out[int(s)] = (c, k)
        return out

    def lineup(self, choices):
        """(seat, color, controller or None) for every player, seat order (turn order starts at the lowest seat),
        or a message if the choices don't work."""
        humans = self.humans(choices)
        if isinstance(humans, str):
            return humans
        p = choices.get("players", "2")
        total = int(p) if p.isdigit() else 2
        if not 2 <= total <= 6:
            return "Island Rush is for 2 to 6 players."
        if total < len(humans):
            return "%d controllers are playing, more than %d players." % (len(humans), total)
        seats = spread_seats(sorted(humans), total)
        spare = [k for k in range(len(PALETTE)) if k not in [h[1] for h in humans.values()]]
        out = []
        for x in seats:
            c, k = humans.get(x, (None, -1))
            if k < 0:
                k = spare.pop(0)
            out.append((x, PALETTE[k], c))
        return out

    def setup(self, choices, now):
        lineup = self.lineup(choices)
        if isinstance(lineup, str):
            return lineup
        self.start(now, lineup=lineup)
        return None

    def preview(self, lights, now, lobby):
        """The jungle and the truck; each player's corner, white blinking while they choose it, then in their color
        (blinking while they choose that); once the leader sets how many play, the computers' corners too."""
        if self.jungle is None:
            self.jungle = E.new_game((), 1)
        pv = self.jungle
        self.draw_jungle(lights, pv.units, pv.owner, (), [E.corner_of(x) for x in range(1, 7)])
        lights.spot(E.CENTER, [TRUCK] * 3, TRUCK_GLOW)
        ch = lobby.choices
        lead = lobby.joined[0] if lobby.joined else None
        if lead is not None and lobby.editing(lead) in ("players", "start"):
            lineup = self.lineup(ch)
            if not isinstance(lineup, str):
                for x, color, c in lineup:
                    if c is None:
                        draw_spot(lights, E.corner_of(x), 1, color)
        for c in lobby.joined:
            s = ch.get("seat:" + c.id, "")
            if not s.isdigit():
                continue
            k = ch.get("color:" + c.id, "")
            color = PALETTE[int(k)] if k.isdigit() and int(k) < len(PALETTE) else WHITE
            doing = lobby.editing(c)
            if doing == "seat:" + c.id:
                lights.spot(E.corner_of(int(s)), [WHITE] * 3, CHOOSING)
            else:
                lights.spot(E.corner_of(int(s)), [color] * 3, CHOOSING if doing == "color:" + c.id else None)
                if doing is None:
                    lights.bar(int(s), [color] * E.BAR)

    def finished(self):
        return self.st is not None and self.st.over and not self.busy

    def start(self, now, seed=None, lineup=None):
        """A new game: lineup is (seat, color, controller or None) for each player, seat order."""
        self.st = E.new_game(tuple(x[0] for x in lineup), dice.seed() if seed is None else seed)
        self.st.tiger_log = []
        self.seats = [Seat(x[0], x[1], x[2]) for x in lineup]
        self.timer_at = None
        self.mode_ui = "board"           # board | aim
        self.aim = -1
        self.roll = None                 # (player, chance, dice.Roll, background colors) while a roll runs
        self.disp = None                 # the board as it was, shown while a roll runs
        self.tiger_queue = []            # the tigers' turns still to show: ("step", tiger, spot) and
                                         # ("bite", spot, player, roll, chance)
        self.tiger_mark = -1
        self.tiger_from = None           # the board as the last round ended (the tigers play forward from it)
        self.logged = 0
        self.busy = False
        self.changed()
        self.cursor = self.cur().pos
        self.start_scan()
        self.schedule_ai(now)

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
        rolled = verb == E.V_CLEAR and E.against(st, p, t) > 0
        before = self.make_view()
        c = E.chance(st, p, t) if rolled else 0
        roll = E.apply(st, verb, t)
        self.changed()
        new = st.tiger_log[self.logged:]
        self.logged = len(st.tiger_log)
        for spot, who, rolls, i, path in new:
            for x in path:
                self.tiger_queue.append(("step", i, x))
            for r, ch in rolls:
                self.tiger_queue.append(("bite", spot, who, r, ch))
        if new:
            self.tiger_from = st.tiger_board
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
        if self.tiger_queue:                                 # the round ended: the tigers first
            self.busy = True
            self.disp = tuple(list(x) for x in self.tiger_from)   # the board as the round ended, played forward
            self.after(now, TIGER_PAUSE, self.tiger_next)
            return
        self.disp = None
        if not self.st.over and self.st.cur != p:
            self.cursor = self.cur().pos
            self.start_scan()
        elif not self.st.over and self.human():
            if self.cursor not in self.items() and self.cursor not in (OUT,):
                self.start_scan()
        self.schedule_ai(now)

    def tiger_next(self, now):
        ev = self.tiger_queue.pop(0)
        if ev[0] == "step":
            self.tiger_mark = -1
            self.disp[4][ev[1]] = ev[2]
            self.after(now, TIGER_STEP, self.tiger_done)
            return
        spot, who, r, ch = ev[1:]
        self.tiger_mark = spot
        bg = [TIGER if i < ch else self.seats[who].color for i in range(E.BAR)]
        self.roll = (who, ch, dice.Roll(now, r, E.BAR, laps=0), bg)     # quicker than a player's: there can be many
        self.after(now, self.roll[2].duration + 0.3, lambda n: self.tiger_bit(spot, who, r <= ch, n))

    def tiger_bit(self, spot, who, hit, now):
        self.roll = None
        if hit:                                              # show the light it took
            owner, units, truck = self.disp[0], self.disp[1], self.disp[2]
            if spot == E.CENTER:
                truck[who] -= 1
            else:
                units[spot] -= 1
                if units[spot] == 0:
                    owner[spot] = -1
                    units[spot] = self.st.s["regrow"]
        self.tiger_done(now)

    def tiger_done(self, now):
        if self.tiger_queue:
            self.after(now, 0.3 if self.tiger_queue[0][0] == "bite" else 0, self.tiger_next)
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
        if self.st is not None and not self.st.over:
            self.play_event(c, a, now)

    def make_view(self):
        return E.board(self.st)

    def draw(self, lights, now):
        if self.st is not None:
            self.draw_play(lights, now)

    def draw_jungle(self, lights, units, owner, tigers, skip=(), glow=()):
        for t in range(E.N):
            if t in skip or t == E.CENTER or owner[t] >= 0:
                continue
            if t in tigers:
                lights.spot(t, [TIGER] * 3, CURSOR if t in glow else PROWL)
            elif units[t] > 0:
                draw_spot(lights, t, units[t], JUNGLE)

    def draw_play(self, lights, now):
        st = self.st
        if self.view is None:
            self.view = self.make_view()
        owner, units, truck, bars, tigers = self.disp or self.view
        glow = self.glow_set()
        self.draw_jungle(lights, units, owner, tigers, glow=glow)
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
        self.draw_truck(lights, now, truck, units[E.CENTER], E.CENTER in glow, E.CENTER in tigers)
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

    def draw_truck(self, lights, now, truck, jungle, glow, tiger=False):
        st = self.st
        on = [p for p in range(len(truck)) if truck[p] > 0]
        mark = TIGER_MARK if self.tiger_mark == E.CENTER else None
        if st.over and st.winner >= 0 and truck[st.winner] > 0:
            draw_spot(lights, E.CENTER, truck[st.winner], self.seats[st.winner].color, False, WINNER)
        elif tiger:
            lights.spot(E.CENTER, [TIGER] * 3, CURSOR if glow else PROWL)
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
        if st.over or self.roll is not None or self.tiger_mark != -1 or self.tiger_queue or self.disp is not None:
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
