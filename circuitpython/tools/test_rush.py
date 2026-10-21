# Desktop test of Island Rush (games/rush): the engine's rules, and the board's game through the host's interfaces
# with a fake clock. Human players are driven only by controller actions (three buttons with row-then-spot
# scanning, one switch with way-out stops, or a D-pad), each wanting the move the computer player would choose;
# every move must land as picked, and games must end with a winner. Also setup on the board and from the USB page.
#   py -3 tools/test_rush.py

import os
import random
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from gamehost import geometry, host
from gamehost.controls import Controls
from gamehost.lights import OFF, Lights
from games.rush import ai as AI
from games.rush import engine as E
from games.rush import game as G

DT = 0.025
FAILS = []
CAN = {"scan": ("move", "move_back", "pick", "back"), "switch": ("move", "pick"),
       "arrows": ("up", "down", "left", "right", "pick", "back")}


def check(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print("FAIL", name, detail)


class Clock:
    def __init__(self, game, lights):
        self.t = 100.0
        self.game = game
        self.lights = lights
        self.n = 0

    def tick(self, k=1):
        for _ in range(k):
            self.t += DT
            self.game.update(self.t)
            self.n += 1
            if self.n % 3 == 0:
                self.lights.fill(OFF)
                self.game.draw(self.lights, self.t)
                self.lights.show()


def send(g, clk, c, a):
    g.event(c, a, clk.t)
    clk.tick()


def drive_scan(g, clk, c, verb, tile):
    st = g.st
    has_back = "back" in c.can
    fr = g.cur().frame
    n0 = len(st.log)
    for _ in range(400):
        if len(st.log) > n0:
            return
        want_row = G.BARROW if verb == E.V_END else fr.row[tile]
        if g.mode_ui == "aim":
            send(g, clk, c, "pick" if g.aim == tile else ("back" if has_back else "move"))
        elif g.level_ui == "spot":
            in_row = g.cursor not in (G.BARPOS, G.OUT) and fr.row[g.cursor] == want_row
            if in_row and g.cursor == tile:
                send(g, clk, c, "pick")
            elif in_row:
                send(g, clk, c, "move")
            elif g.cursor == G.OUT:
                send(g, clk, c, "pick")
            elif has_back:
                send(g, clk, c, "back")
            else:
                send(g, clk, c, "move")
        else:
            send(g, clk, c, "pick" if g.row == want_row else "move")
    raise RuntimeError("scan driver stuck: %d %d" % (verb, tile))


def drive_arrows(g, clk, c, verb, tile):
    st = g.st
    fr = g.cur().frame
    n0 = len(st.log)
    for _ in range(400):
        if len(st.log) > n0:
            return
        target = G.BARPOS if verb == E.V_END else tile
        if g.mode_ui == "aim" and g.aim != tile:
            send(g, clk, c, "back")
        elif g.level_ui == "spot" and g.cursor == target:
            send(g, clk, c, "pick")
        else:
            if g.level_ui != "spot" or g.cursor < 0:
                send(g, clk, c, "up")            # leave the row level onto a spot
                continue
            nxt = fr.path(g.cursor, target)[0]
            for key in ("left", "right", "up", "down"):
                if fr.arrow(g.cursor, key) == nxt:
                    send(g, clk, c, key)
                    break
    raise RuntimeError("arrow driver stuck")


DRIVERS = {"scan": drive_scan, "switch": drive_scan, "arrows": drive_arrows}


def new_ui():
    b = host.Board(Lights(), Controls(hardware=False))
    g = G.Game(b)
    return b, g, Clock(g, b.lights)


def play_through(name, g, clk, drivers, seed):
    st = g.st
    st.log = []
    rng = random.Random(seed)
    end = clk.t + 60000
    while not st.over and clk.t < end:
        c = g.seats[st.cur].ctrl
        if c is None or g.busy:
            clk.tick()
            continue
        verb, tile = AI.choose(st, "beginner", rng)
        n = len(st.log)
        drivers[c.id](g, clk, c, verb, tile)
        ok = len(st.log) == n + 1 and st.log[n][1] == verb and st.log[n][2] == tile
        check(name + ": move applied", ok, (st.log[n:], verb, tile))
        if not ok:
            break
    for _ in range(4000):                            # the last rolls and the tiger
        if not g.busy:
            break
        clk.tick()
    check(name + ": game over with a winner", st.over and st.winner >= 0 and not g.busy, (st.round, st.winner, g.busy))


def engine_rules():
    corners = [E.corner_of(s) for s in range(1, 7)]
    check("six different corners", len(set(corners)) == 6 and all(E.DIST[t] == 3 for t in corners), corners)
    for t in corners:
        q, r = geometry.Q[t], geometry.R[t]
        line = [geometry.spot_at(q * k // 3, r * k // 3) for k in (2, 1)] if hasattr(geometry, "spot_at") else []
        check("straight way in from %d" % t, all(x is not None for x in line), line)
    st = E.new_game((1, 4), 5)
    check("jungle by ring", [st.units[t] for t in (E.CENTER,)] == [0] and
          all(st.units[t] == E.DEFAULTS["jungle"][E.DIST[t]] for t in range(E.N) if st.owner[t] < 0), st.units)
    check("start: 3 lights in each corner, 3 on the bar", st.units[E.corner_of(1)] == 3 and st.players[0].bar == 3)
    check("chance: 3 against 1 jungle", E.chance(st, 0, E.NB[E.corner_of(1)][0]) in (7, 8), E.chance(st, 0, 1))

    def game(seed, seats=(1, 3, 5)):
        g = E.new_game(seats, seed)
        g.log = []
        rng = random.Random(seed)
        while not g.over:
            v, t = AI.choose(g, "beginner", rng)
            E.apply(g, v, t)
        return g
    a = game(11)
    b = game(11)
    check("the same seed plays the same game", a.log == b.log and a.winner == b.winner)
    wins = [0] * 3
    for s in range(60):
        g = game(s)
        check("a winner every game", g.winner >= 0, (s, g.round))
        wins[g.winner] += 1
    check("every seat wins sometimes", min(wins) > 5, wins)

    # computer players only clear toward the truck; tigers walk a spot at a time through spots no player holds, beside
    # their leader's lead spot, and don't sit still when there's another spot beside it
    away = walks = leaps = still = moved = heads = bites = 0
    for seats in ((1, 4), (1, 2, 3, 4, 5, 6)):
        for seed in range(40):
            g = E.new_game(seats, seed)
            g.tiger_log = []
            rng = random.Random(seed)
            while not g.over:
                p = g.cur
                mine = E.spots_of(g, p)
                v, t = AI.choose(g, "beginner", rng)
                if v == E.V_CLEAR and mine:
                    far = AI.ways(g, p)
                    if min(far[x] for x in mine) == AI.FAR:
                        far = AI.ways(g, p, False)
                    away += far[t] >= min(far[x] for x in mine)
                n = len(g.tiger_log)
                was = list(g.tigers)
                E.apply(g, v, t)
                if len(g.tiger_log) == n or g.tiger_log[n][0] == E.CENTER:
                    continue
                board = g.tiger_board
                bitten = set()                       # (an earlier tiger's bite may give a spot back to the jungle)
                for spot, who, rolls, i, path in g.tiger_log[n:]:
                    at = was[i]
                    for x in path:
                        if (board[0][x] != -1 and x not in bitten) or (x == E.CENTER and any(board[2])):
                            walks += 1
                        if at >= 0 and x not in E.NB[at]:
                            leaps += 1
                        at = x
                    if was[i] >= 0:
                        moved += 1 if path else 0
                        still += 0 if path else 1
                    if spot >= 0:
                        bitten.add(spot)
                        lead = min((x for x in range(E.N) if board[0][x] == who), key=lambda x: (E.DIST[x], x))
                        heads += spot == lead
                        bites += 1
    check("computer players never clear away from the truck", away == 0, away)
    check("tigers walk only through spots no player holds (the truck only when no one does)", walks == 0, walks)
    check("tigers walk a spot at a time (leaping only when boxed in)", leaps * 10 < moved, (leaps, moved))
    check("tigers move most rounds", still * 3 < moved, (still, moved))
    check("tigers bite their leader's lead spot", heads * 10 > bites * 9, (heads, bites))

    # one player holds the truck: another rolls them off it (their lights go back beside the truck, the rest are
    # lost) or loses a light; the tiger attacks the holder at the end of the round, and a holder left there wins
    def truck_game():
        st = E.new_game((1, 4), 3)
        nb0, nb1 = E.NB[E.CENTER][0], E.NB[E.CENTER][3]
        st.truck[0] = 3
        st.owner[nb0], st.units[nb0] = 0, 2
        st.owner[nb1], st.units[nb1] = 1, 3
        st.cur = st.first = 1
        st.players[1].bar = 3
        return st, nb0, nb1

    def rng_for(st, win):                            # a dice stream whose next roll wins (or loses) at this chance
        c = E.chance(st, st.cur, E.CENTER)
        for r in range(1000):
            st.rng = r
            if (E.d10(st) <= c) == win:
                st.rng = r
                return
    st, nb0, nb1 = truck_game()
    check("only the holder can add to the truck", E.can_add(st, 0, E.CENTER) is False and st.truck[1] == 0)
    check("challenge: the holder's lights against yours", E.against(st, 1, E.CENTER) == 3 and
          E.chance(st, 1, E.CENTER) == 5, E.chance(st, 1, E.CENTER))
    rng_for(st, True)
    E.apply(st, E.V_CLEAR, E.CENTER)
    check("a won challenge rolls the holder off", E.holder(st) == 1 and st.truck == [0, 1] and st.units[nb1] == 2,
          (st.truck, st.units[nb1]))
    check("... its lights back beside the truck, up to 3", st.units[nb0] == 3 and st.owner[nb0] == 0, st.units[nb0])
    st, nb0, nb1 = truck_game()
    rng_for(st, False)
    E.apply(st, E.V_CLEAR, E.CENTER)
    check("a lost challenge costs a light", st.truck == [3, 0] and st.units[nb1] == 2, (st.truck, st.units[nb1]))
    st, nb0, nb1 = truck_game()
    st.tiger_log = []
    E.tiger_phase(st)
    hit = [e[1] for e in st.tiger_log if e[0] == E.CENTER]
    check("the tiger attacks the holder", hit == [0], st.tiger_log)
    check("a holder left on the truck wins; cleared off, it's jungle again",
          (st.over and st.winner == 0) if st.truck[0] else (not st.over and st.units[E.CENTER] == 1),
          (st.truck, st.over, st.units[E.CENTER]))
    # a tiger in your way can be fought: your lights touching it against its strength; a win drives it off the island
    # till the round's end (what's under it stays), a loss costs a light. It can stand on the truck when it's open.
    st, nb0, nb1 = truck_game()
    st.truck[0] = 0
    st.tigers[0] = E.CENTER
    check("a tiger can be fought", E.can_clear(st, 1, E.CENTER) and E.against(st, 1, E.CENTER) == 2 and
          E.chance(st, 1, E.CENTER) == 6, E.chance(st, 1, E.CENTER))
    rng_for(st, True)
    E.apply(st, E.V_CLEAR, E.CENTER)
    check("a won fight drives the tiger off, nobody moves in", st.tigers[0] == -1 and st.truck[1] == 0 and
          st.units[nb1] == 3, (st.tigers, st.truck, st.units[nb1]))
    st, nb0, nb1 = truck_game()
    st.truck[0] = 0
    st.tigers[0] = E.CENTER
    rng_for(st, False)
    E.apply(st, E.V_CLEAR, E.CENTER)
    check("a lost fight costs a light", st.tigers[0] == E.CENTER and st.units[nb1] == 2, (st.tigers, st.units[nb1]))
    st, nb0, nb1 = truck_game()
    check("no tiger on a held truck", not E._free(st, E.CENTER, 0))
    st.truck[0] = 0
    check("a tiger can stand on the open truck", E._free(st, E.CENTER, 0))

    st = E.new_game((1, 4), 3)
    st.players[1].bar = 3
    nb = [n for n in E.NB[E.CENTER]][0]
    st.owner[nb] = 1
    st.units[nb] = 2
    st.cur = 1
    check("walk onto the open truck", E.can_clear(st, 1, E.CENTER) and E.jungle(st, E.CENTER) == 0)
    E.apply(st, E.V_CLEAR, E.CENTER)
    check("... with 1 light, leaving 1", st.truck[1] == 1 and st.units[nb] == 1)

    # another player's spot next to yours can be rolled off: your lights touching it against theirs on it; a win sends
    # their lights back to their other spots touching it (up to 3, the rest lost) and you move in, a loss costs a light
    def spot_game():
        st = E.new_game((1, 4), 3)
        a, b, c = 0, 1, 2                            # A1, A2, A3 in a row: player 0 on A1, player 1 on A2 (3) and B2
        st.owner[a], st.units[a] = 0, 3
        st.owner[b], st.units[b] = 1, 3
        b2 = [x for x in E.NB[b] if x in E.NB[a]][0]
        st.owner[b2], st.units[b2] = 1, 2
        st.cur = st.first = 0
        st.players[0].bar = 3
        return st, a, b, b2

    def rng_at(st, t, win):
        c = E.chance(st, st.cur, t)
        for r in range(1000):
            st.rng = r
            if (E.d10(st) <= c) == win:
                st.rng = r
                return
    st, a, b, b2 = spot_game()
    check("another player's spot can be attacked", E.can_clear(st, 0, b) and E.against(st, 0, b) == 3 and
          E.chance(st, 0, b) == 5, E.chance(st, 0, b))
    rng_at(st, b, True)
    E.apply(st, E.V_CLEAR, b)
    check("a won attack rolls them off and you move in", st.owner[b] == 0 and st.units[b] == 1 and st.units[a] == 2,
          (st.owner[b], st.units[b], st.units[a]))
    check("... their lights back to their spot beside it, up to 3", st.owner[b2] == 1 and st.units[b2] == 3,
          st.units[b2])
    st, a, b, b2 = spot_game()
    rng_at(st, b, False)
    E.apply(st, E.V_CLEAR, b)
    check("a lost attack costs a light", st.owner[b] == 1 and st.units[b] == 3 and st.units[a] == 2,
          (st.units[b], st.units[a]))


def board_setup(name, humans, total, seed):
    """humans: [(controller seat, corner seat to take, driver kind)]; the first to join sets the total."""
    b, g, clk = new_ui()
    ctls = []
    drivers = {}
    for k, (cseat, side, kind) in enumerate(humans):
        c = b.controls.get("h%d" % k, "player %d" % (k + 1), cseat, CAN[kind])
        ctls.append(c)
        drivers[c.id] = DRIVERS[kind]
    clk.tick(5)
    for k, c in enumerate(ctls):
        send(g, clk, c, "pick")                      # join
        j = g.joiner(c)
        for _ in range(8):
            if j.seat == humans[k][1]:
                break
            send(g, clk, c, "move")
        check(name + ": corner of seat %d" % humans[k][1], j.seat == humans[k][1], j.seat)
        send(g, clk, c, "pick")
        send(g, clk, c, "move")                      # a different color
        send(g, clk, c, "pick")
    lj = g.joiner(ctls[0])
    check(name + ": the first player sets the total", lj.stage == "total", lj.stage)
    for _ in range(8):
        if g.total == total:
            break
        send(g, clk, ctls[0], "move")
    check(name + ": total %d" % total, g.total == total, g.total)
    send(g, clk, ctls[0], "pick")
    check(name + ": started", g.phase == "play", g.phase)
    seats = [x.seat for x in g.seats]
    check(name + ": everyone at their corner", all(h[1] in seats for h in humans) and len(seats) == total, seats)
    check(name + ": colors differ", len(set(x.color for x in g.seats)) == total)
    play_through(name, g, clk, drivers, seed)
    st = g.st
    send(g, clk, ctls[0], "pick")
    check(name + ": back to setup", g.phase == "join")
    print("%-34s seats %s, winner seat %s, round %d, %d moves" % (name, seats, g.seats[st.winner].seat,
                                                                  st.round, len(st.log)))


def usb_page():
    b, g, clk = new_ui()
    c1 = b.controls.get("a", "player 1 (USB)", 1, CAN["arrows"])
    c2 = b.controls.get("b", "player 2 (Wiimote)", None, CAN["arrows"])
    clk.tick(2)
    keys = [f["key"] for f in g.options()]
    check("page: the form", keys == ["players", "seat:a", "seat:b"], keys)
    msg = g.setup({"players": "3", "seat:a": "2", "seat:b": "2"}, clk.t)
    check("page: two at one seat is refused", msg and "both at seat 2" in msg and g.phase == "join", msg)
    msg = g.setup({"players": "4", "seat:a": "1", "seat:b": "4"}, clk.t)
    check("page: started", msg is None and g.phase == "play", msg)
    seats = [(x.seat, x.ctrl.id if x.ctrl else None) for x in g.seats]
    check("page: humans where asked, computers spread", len(seats) == 4 and (1, "a") in seats and (4, "b") in seats,
          seats)
    play_through("page game", g, clk, {"a": drive_arrows, "b": drive_arrows}, 3)


def computers_only():
    b, g, clk = new_ui()
    g.start(clk.t, seed=9, lineup=[(x, G.PALETTE[k], None) for k, x in enumerate((1, 2, 3, 4, 5, 6))])
    shown = []
    done = g.tiger_done

    def tiger_done(now):                             # the board the tigers played forward ends as the real one
        if not g.tiger_queue:
            real = E.board(g.st)
            shown.append(g.disp[4] == real[4] and g.disp[0] == real[0] and
                         all(g.disp[1][t] == real[1][t] for t in range(E.N) if t != E.CENTER))
        done(now)
    g.tiger_done = tiger_done
    for _ in range(200000):
        if g.st.over and not g.busy:
            break
        clk.tick()
    check("six computers finish a game", g.st.over and g.st.winner >= 0, (g.st.round, g.busy))
    check("the tigers' walks and bites shown match the board after", shown and all(shown), shown)


def hosted():
    names = host.game_names()
    check("Island Rush is a game on the board", "rush" in names, names)
    h = host.Host(name="rush", board=host.Board(Lights(), Controls(hardware=False)))
    h.frame(0.0)
    check("it runs under the host", h.name == "rush" and isinstance(h.game, G.Game))


if __name__ == "__main__":
    engine_rules()
    board_setup("2 players, scan and arrows", [(1, 1, "scan"), (4, 4, "arrows")], 2, 1)
    board_setup("1 switch vs 3 computers", [(2, 2, "switch")], 4, 2)
    board_setup("3 humans + 3 computers", [(1, 1, "arrows"), (3, 3, "scan"), (5, 5, "switch")], 6, 3)
    usb_page()
    computers_only()
    hosted()
    print("%d failed" % len(FAILS) if FAILS else "all passed")
    sys.exit(1 if FAILS else 0)
