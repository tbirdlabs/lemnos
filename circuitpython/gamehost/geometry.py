# The board's shape, for any game: the island's 37 hexes ("spots"), the lines between them, the 6 seats around it,
# and how each seat sees it. Pure data and math, no hardware. A game uses this to find spots, neighbors and sides;
# lights.py uses the same names to find the LEDs, wherever the strip actually runs.
#
# Names, all as seen from seat 1 (Player One, the bottom):
#   Rows      A to G, from the farthest from seat 1 (A) to the nearest (G). Rows have 4, 5, 6, 7, 6, 5, 4 hexes.
#   Hexes     the row and 1 to n, left to right: A1-A4, B1-B5, C1-C6, D1-D7 (D4 is the center), E1-E6, F1-F5, G1-G4.
#   Lines     the vertical edges in a row, under which the small board has an LED. A row has one more line than
#             hexes, also counted left to right from 1: line B1 is row B's left end, line Bk is just left of hex Bk,
#             and line B6 is the right end. So hex Bk sits between lines Bk and Bk+1. (The slanted edges between
#             rows have no LEDs.)
#   spot("B3"), line("B3"), between("B3", "B4"), name(t), line_name(k) convert between names and numbers.
#
# Inside, spots and lines are also numbered, in reading order (row A first, each row left to right): spots 0-36,
# lines 0-43. The numbers are for arrays and loops; they have nothing to do with the order of the LED strip. Every
# function here that takes a spot takes either its name or its number, except View's cursor methods.
# Each spot also has axial hex coordinates (Q[t], R[t]), with the center (D4) at (0, 0), R running from -3 (row A)
# to 3 (row G) and Q along the rows. DIRECTIONS steps to the 6 neighbors.
#
# Seats are numbered 1-6 clockwise from the bottom (seat 1, where row G is); see docs/wiring.md.
#   SIDES[seat]        the 4 coast spots facing that seat, left to right as that player sees them
#   VIEWS[seat]        that seat's view of the island (a View): its rows far to near, left to right, and arrow keys
#
#   from gamehost import geometry as G
#   G.neighbors("D4")              # the 6 spots around the middle (as numbers; G.name(t) for their names)
#   G.VIEWS[3].rows[6]             # the row nearest seat 3, left to right as they see it
#   G.VIEWS[3].arrow(t, "up")      # where "up" takes a cursor on spot t for the player at seat 3

RADIUS = 3                               # spots from the center to an edge
ROW_LENGTHS = (4, 5, 6, 7, 6, 5, 4)
SPOTS = 37
SEATS = 6
LEDS_PER_SPOT = 3                        # light 0 = the left one as seen from seat 1
BAR_LEDS = 10                            # each seat's bar; light 0 = LED 1, at that player's left
ON_BAR = SPOTS                           # View.arrow / View.path: the cursor is on the player's bar
DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))

Q = []
R = []
ROW = []                                 # 0 = row A ... 6 = row G
COL = []                                 # place in the row, 0 = the left end as seen from seat 1
ROWS = []                                # the spots of each row, left to right as seen from seat 1
ROW_NAMES = "ABCDEFG"
_at = {}
for _r in range(-RADIUS, RADIUS + 1):
    _row = []
    for _q in range(max(-RADIUS, -RADIUS - _r), min(RADIUS, RADIUS - _r) + 1):
        _at[(_q, _r)] = len(Q)
        _row.append(len(Q))
        Q.append(_q)
        R.append(_r)
        ROW.append(_r + RADIUS)
        COL.append(len(_row) - 1)
    ROWS.append(_row)


def spot_at(q, r):
    """The spot at axial (q, r), or -1 off the island."""
    return _at.get((q, r), -1)


def name(t):
    """A spot's name, like "D4"."""
    return ROW_NAMES[ROW[t]] + str(COL[t] + 1)


_SPOT_NAMED = {name(t): t for t in range(SPOTS)}


def spot(x):
    """A spot's number from its name ("B3", or "b3"); a number is returned as it is."""
    if isinstance(x, int):
        return x
    t = _SPOT_NAMED.get(x.upper(), -1)
    if t < 0:
        raise ValueError("no hex named %r (rows A-G, hexes from 1)" % (x,))
    return t


NEIGHBORS = tuple(tuple(n for n in (spot_at(Q[t] + dq, R[t] + dr) for dq, dr in DIRECTIONS) if n >= 0)
                  for t in range(SPOTS))
CENTER = spot_at(0, 0)


def neighbors(t):
    """The spots touching spot t (3 to 6 of them), as numbers."""
    return NEIGHBORS[spot(t)]


def adjacent(a, b):
    return spot(b) in NEIGHBORS[spot(a)]


# ---- Lines: the vertical edges in each row (an LED under each on the small board) ----
LINES = sum(n + 1 for n in ROW_LENGTHS)  # 44
LINE_ROW = []                            # line k's row, 0 = A
LINE_COL = []                            # line k's place in its row, 0 = the left end (its name is LINE_COL + 1)
LINE_START = []                          # the first line of each row
for _r, _n in enumerate(ROW_LENGTHS):
    LINE_START.append(len(LINE_ROW))
    for _c in range(_n + 1):
        LINE_ROW.append(_r)
        LINE_COL.append(_c)


def line_name(k):
    """A line's name, like "B6" (row B's right end)."""
    return ROW_NAMES[LINE_ROW[k]] + str(LINE_COL[k] + 1)


_LINE_NAMED = {line_name(k): k for k in range(LINES)}


def line(x):
    """A line's number from its name ("B1" = row B's left end); a number is returned as it is."""
    if isinstance(x, int):
        return x
    k = _LINE_NAMED.get(x.upper(), -1)
    if k < 0:
        raise ValueError("no line named %r (rows A-G, lines from 1 to one more than the row's hexes)" % (x,))
    return k


def left_line(t):
    """The line just left of spot t (as seen from seat 1): line Bk for hex Bk."""
    t = spot(t)
    return LINE_START[ROW[t]] + COL[t]


def right_line(t):
    """The line just right of spot t (as seen from seat 1): line Bk+1 for hex Bk."""
    return left_line(t) + 1


def between(a, b):
    """The line between two hexes side by side in a row, in either order: between("B3", "B4") is line B4."""
    a = spot(a)
    b = spot(b)
    if ROW[a] != ROW[b] or abs(COL[a] - COL[b]) != 1:
        raise ValueError("%s and %s aren't side by side in a row" % (name(a), name(b)))
    return right_line(a if COL[a] < COL[b] else b)


def line_spots(k):
    """The hexes on either side of line k, left one first: two, or one at a row's end."""
    k = line(k)
    row = ROWS[LINE_ROW[k]]
    c = LINE_COL[k]
    return tuple(row[i] for i in (c - 1, c) if 0 <= i < len(row))


# ---- Seats ----
# The island's corners clockwise from the top-left; seat s faces the side from corner s+2 to corner s+3 (mod 6).
_CORNERS = ((0, -3), (3, -3), (3, 0), (0, 3), (-3, 3), (-3, 0))


def _side(seat):
    a = _CORNERS[(seat + 2) % 6]
    b = _CORNERS[(seat + 3) % 6]
    dq = (b[0] - a[0]) // RADIUS
    dr = (b[1] - a[1]) // RADIUS
    return [spot_at(a[0] + k * dq, a[1] + k * dr) for k in range(RADIUS + 1)]


def _turn(q, r):
    return -r, q + r                     # one 60-degree turn


class View:
    """The island as the player at one seat sees it: their side nearest, rows running across in front of them.

    row[t]      the row spot t is in, 0 = the far row ... 6 = the nearest
    x[t]        left to right in that row (in half-spot steps, so it lines up across rows; 0 = the middle)
    rows[r]     the spots of row r, left to right
    order[t]    reading order: far row first, left to right (0..36)
    reading     the spots in reading order (reading[order[t]] == t)
    arrow(pos, key), path(frm, to): moving a cursor with arrow keys; ON_BAR is the player's bar, past the nearest row
    """

    def __init__(self, seat):
        self.seat = seat
        mid = _side(seat)[1]             # turn until this seat's side is the nearest row
        k = 0
        q, r = Q[mid], R[mid]
        while r != RADIUS:
            q, r = _turn(q, r)
            k += 1
        self.row = [0] * SPOTS
        self.x = [0] * SPOTS
        for t in range(SPOTS):
            q, r = Q[t], R[t]
            for _ in range(k):
                q, r = _turn(q, r)
            self.row[t] = r + RADIUS
            self.x[t] = 2 * q + r
        self.rows = [[] for _ in ROW_LENGTHS]
        for t in range(SPOTS):
            self.rows[self.row[t]].append(t)
        for rw in self.rows:
            rw.sort(key=lambda t: self.x[t])
        self.reading = [t for rw in self.rows for t in rw]
        self.order = [0] * SPOTS
        for k, t in enumerate(self.reading):
            self.order[t] = k

    def arrow(self, pos, key):
        """Where an arrow key ("up", "down", "left", "right") takes a cursor at pos (a spot, or ON_BAR).
        Down from the nearest row is the bar; up from the bar is the middle of the nearest row."""
        last = len(self.rows) - 1
        if pos == ON_BAR:
            if key == "up":
                rw = self.rows[last]
                return rw[(len(rw) - 1) // 2]
            return pos
        r = self.row[pos]
        rw = self.rows[r]
        c = rw.index(pos)
        if key == "left":
            return rw[c - 1] if c > 0 else pos
        if key == "right":
            return rw[c + 1] if c < len(rw) - 1 else pos
        nr = r - 1 if key == "up" else r + 1
        if nr > last:
            return ON_BAR
        if nr < 0:
            return pos
        x = self.x[pos]
        best = -1
        bd = 999
        for n in self.rows[nr]:          # nearest in the next row; a tie goes toward the middle
            d = abs(self.x[n] - x) * 4 + (0 if abs(self.x[n]) < abs(x) else 1)
            if d < bd:
                bd = d
                best = n
        return best

    def path(self, frm, to):
        """The cursor positions a player at this seat passes through with arrow keys going from frm to to (spots or
        ON_BAR), not counting frm; shortest first. A computer player can walk its cursor along it."""
        if frm == to:
            return []
        prev = {frm: None}
        q = [frm]
        h = 0
        while h < len(q):
            a = q[h]
            h += 1
            for key in ("left", "right", "up", "down"):
                n = self.arrow(a, key)
                if n in prev:
                    continue
                prev[n] = a
                q.append(n)
                if n == to:
                    out = [n]
                    x = a
                    while x != frm:
                        out.insert(0, x)
                        x = prev[x]
                    return out
        return [to]


VIEWS = (None,) + tuple(View(s) for s in range(1, SEATS + 1))       # VIEWS[seat], seats 1-6
SIDES = ((),) + tuple(tuple(sorted(_side(s), key=lambda t, v=VIEWS[s]: v.x[t])) for s in range(1, SEATS + 1))
