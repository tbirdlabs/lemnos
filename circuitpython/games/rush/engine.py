# Island Rush: up to 6 players race through the jungle to the taco truck in the middle of the island
# (docs/rules/island-rush-rules-v0.2.md). Nobody attacks anybody: everyone clears jungle; a tiger chases the leader.
# The truck is shared ground: anyone who reaches it can get on; at the end of every round the tiger attacks everyone
# on it, and the last one left there wins. Pure logic, no hardware: the board's game and the simulator
# (tools/sim_rush.py) both run this.
#
#   st = new_game(seats=(1, 4), seed=7)          # players in turn order, by seat
#   while not st.over:
#       verb, t = some_player(st)                # from legal_actions(st)
#       apply(st, verb, t)                       # END ends the turn (and the round, and the tiger moves)
#
# A spot is jungle (owner -1, units = its jungle lights), empty (owner -1, units 0) or a player's (owner p, units =
# p's lights). The truck (CENTER) is the exception: owner stays -1, units is its jungle, and truck[p] is each
# player's lights on it once the jungle is cleared. lights(st, p, t) reads either.

from gamehost import geometry as G

N = G.SPOTS
CENTER = G.CENTER
NB = G.NEIGHBORS
BAR = 10
V_END = 0
V_ADD = 1
V_CLEAR = 2

DEFAULTS = {
    "start": 3,           # lights on your corner at the start, and when you start over
    "income": 3,          # new lights a turn
    "cap": 3,             # lights a spot can hold (each player's, on the truck)
    "jungle": (0, 3, 2, 1),   # jungle lights by distance from the center: the truck (none: the tiger guards it),
                              # inner ring, middle, outer
    "tigers": 1,          # how many (each chases a different leader: the nearest to the truck, the next...)
    "tigersPer": 3,       # if more than 0: one tiger for every this many players (at least `tigers`): 2 with 4-6
    "pounce": 1,          # 1: a tiger jumps straight to a free spot beside its target instead of walking
    "tigerA": 2,          # a tiger's strength (its A) when it attacks a spot
    "tigerHoldA": 2,      # ... when it attacks a player on the truck
    "tigerUntilMiss": 1,  # on the truck it keeps attacking each player until it misses (0: one roll each)
    "truckRegrow": 1,     # jungle lights on the truck after the tiger clears everyone off
    "regrow": 1,          # jungle lights on a spot of yours the tiger empties
    "maxRounds": 60,      # a draw after this many rounds
    "chaseTie": 1,        # leaders tied for nearest: 0 the one who got there first, 1 the one with the most lights
    "rotate": 1,          # 1: who starts the round moves round by round (seat 1, then 2, ...): no one is always last
    "crowd": 2,           # 2+ left on the truck after the tiger: 0 play on, 1 the most lights there wins (a tie plays
                          # on), 2 play on with the tiger 1 stronger at the truck for every round it found a crowd
}


def dist(t):
    q = G.Q[t]
    r = G.R[t]
    return max(abs(q), abs(r), abs(q + r))


DIST = tuple(dist(t) for t in range(N))


def corner_of(seat):
    """The corner a seat starts from: the left end of its side, as its player faces the board."""
    return G.SIDES[seat][0]


def chance_of(a, d):
    """Green out of 10: 10 x A / (A + D), rounded half up, kept between 1 and 9; 10 against nothing."""
    if d <= 0:
        return 10
    c = (20 * a + (a + d)) // (2 * (a + d))
    return max(1, min(9, c))


class Player:
    def __init__(self, seat):
        self.seat = seat
        self.corner = corner_of(seat)
        self.bar = 0
        self.best = 9             # the nearest it has been to the truck (distance)
        self.best_at = 0          # the move count when it got there (ties for the tiger's chase go to the earlier)


class State:
    def __init__(self, rules, seats, seed):
        self.s = dict(DEFAULTS)
        self.s.update(rules or {})
        self.rng = (seed or 1) & 0xFFFFFFFF
        self.owner = [-1] * N
        self.units = [0] * N
        jungle = self.s["jungle"]
        for t in range(N):
            self.units[t] = jungle[DIST[t]]
        self.players = [Player(x) for x in seats]
        self.truck = [0] * len(self.players)
        for p, pl in enumerate(self.players):
            self.owner[pl.corner] = p
            self.units[pl.corner] = self.s["start"]
            pl.best = DIST[pl.corner]
        k = self.s["tigers"]
        if self.s["tigersPer"] > 0:
            k = max(k, (len(seats) + self.s["tigersPer"] - 1) // self.s["tigersPer"])
        self.tigers = [-1] * k                    # off the island until the end of the first round
        self.cur = 0
        self.first = 0                # who started this round
        self.round = 1
        self.moves = 0
        self.over = False
        self.winner = -1
        self.crowds = 0               # rounds the tiger has found 2 or more on the truck
        self.log = None               # a list to record [player, verb, spot, roll] in, if wanted
        self.tiger_log = None         # a list to record the tiger's attacks in, if wanted: [spot, player, [(roll,
                                      # chance), ...]] (the board shows them; tools/sim_rush.py counts them)
        if self.players:              # (no players: just the jungle, for the setup screen)
            start_turn(self)


def new_game(seats=(1, 4), seed=1, rules=None):
    return State(rules, seats, seed)


def d10(st):
    """1-10 from the game's own mulberry32 stream (replays come out the same everywhere)."""
    st.rng = (st.rng + 0x6D2B79F5) & 0xFFFFFFFF
    z = st.rng
    z = ((z ^ (z >> 15)) * (z | 1)) & 0xFFFFFFFF
    z ^= (z + (((z ^ (z >> 7)) * (z | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
    z = (z ^ (z >> 14)) & 0xFFFFFFFF
    return z % 10 + 1


def tiger_at(st, t):
    return t >= 0 and t in st.tigers


def lights(st, p, t):
    """p's lights on spot t."""
    if t == CENTER:
        return st.truck[p]
    return st.units[t] if st.owner[t] == p else 0


def on_truck(st):
    return [p for p in range(len(st.players)) if st.truck[p] > 0]


def jungle(st, t):
    """Jungle lights on t (0: cleared, or a player's)."""
    return st.units[t] if st.owner[t] == -1 else 0


def _take(st, p, t, n):
    """p loses n lights from t; an emptied spot of p's is empty ground."""
    if t == CENTER:
        st.truck[p] -= n
        return
    st.units[t] -= n
    if st.units[t] == 0:
        st.owner[t] = -1


def _put(st, p, t, n):
    if t == CENTER:
        st.truck[p] += n
    else:
        st.owner[t] = p
        st.units[t] += n
    pl = st.players[p]
    if DIST[t] < pl.best:
        pl.best = DIST[t]
        pl.best_at = st.moves


def strength(st, p, t):
    """All p's lights on spots touching t."""
    a = 0
    for n in NB[t]:
        a += lights(st, p, n)
    return a


def strongest(st, p, t):
    """p's spot touching t with the most lights (ties: nearest the truck, then lowest number), or -1."""
    best = -1
    bl = 0
    for n in NB[t]:
        k = lights(st, p, n)
        if k > 0 and (best < 0 or k > bl or (k == bl and DIST[n] < DIST[best])):
            best = n
            bl = k
    return best


def chance(st, p, t):
    return chance_of(strength(st, p, t), jungle(st, t))


def can_clear(st, p, t):
    """Clear jungle on t, or walk onto empty ground (or the cleared truck) next to p's spots."""
    if st.players[p].bar < 1 or tiger_at(st, t) or lights(st, p, t) > 0:
        return False
    if t != CENTER and st.owner[t] != -1:
        return False                                  # another player's spot: a wall
    src = strongest(st, p, t)
    if src < 0:
        return False
    return jungle(st, t) > 0 or lights(st, p, src) >= 2     # walking in leaves a light behind


def can_add(st, p, t):
    k = lights(st, p, t)
    return 0 < k < st.s["cap"] and st.players[p].bar >= 1


def legal_actions(st):
    out = [(V_END, -1)]
    if st.over:
        return out
    p = st.cur
    for t in range(N):
        if can_add(st, p, t):
            out.append((V_ADD, t))
        elif can_clear(st, p, t):
            out.append((V_CLEAR, t))
    return out


def spots_of(st, p):
    return [t for t in range(N) if lights(st, p, t) > 0]


def apply(st, verb, t):
    """One move by the player whose turn it is. Returns the d10 roll (0 if none)."""
    if st.over:
        raise ValueError("the game is over")
    p = st.cur
    pl = st.players[p]
    roll = 0
    st.moves += 1
    if verb == V_END:
        if st.log is not None:
            st.log.append([p, verb, t, 0])
        end_turn(st)
        return 0
    if verb == V_ADD:
        if not can_add(st, p, t):
            raise ValueError("can't add at %d" % t)
        pl.bar -= 1
        _put(st, p, t, 1)
    elif verb == V_CLEAR:
        if not can_clear(st, p, t):
            raise ValueError("can't clear %d" % t)
        pl.bar -= 1
        src = strongest(st, p, t)
        if jungle(st, t) == 0:                        # empty ground: walk in
            _take(st, p, src, 1)
            _put(st, p, t, 1)
        else:
            roll = d10(st)
            if roll <= chance(st, p, t):
                st.units[t] -= 1
                if st.units[t] == 0 and lights(st, p, src) >= 2:
                    _take(st, p, src, 1)
                    _put(st, p, t, 1)
            else:
                _take(st, p, src, 1)
    else:
        raise ValueError("no such move %d" % verb)
    if st.log is not None:
        st.log.append([p, verb, t, roll])
    if pl.bar <= 0:
        end_turn(st)
    return roll


def end_turn(st):
    st.cur = (st.cur + 1) % len(st.players)
    if st.cur == st.first:
        tiger_phase(st)
        if st.over:
            return
        st.round += 1
        if st.round > st.s["maxRounds"]:
            st.over = True
            return
        if st.s["rotate"]:
            st.first = (st.first + 1) % len(st.players)
            st.cur = st.first
    start_turn(st)


def start_turn(st):
    p = st.cur
    pl = st.players[p]
    if not spots_of(st, p):                           # wiped out: start again in your corner
        spot = pl.corner
        if st.owner[spot] != -1 or tiger_at(st, spot):
            free = [t for t in G.SIDES[pl.seat] if st.owner[t] == -1 and not tiger_at(st, t)]
            spot = free[0] if free else -1
        if spot >= 0:
            st.owner[spot] = p
            st.units[spot] = st.s["start"]
    pl.bar = min(BAR, pl.bar + st.s["income"])


def leaders(st):
    """The players with spots, nearest the truck first (ties: the one with more lights, or with chaseTie 0 whoever
    got that near first)."""
    out = []
    for p, pl in enumerate(st.players):
        mine = spots_of(st, p)
        if not mine:
            continue
        d = min(DIST[t] for t in mine)
        tie = -sum(lights(st, p, t) for t in mine) if st.s["chaseTie"] == 1 else pl.best_at
        out.append((d, tie, p))
    out.sort()
    return [p for d, tie, p in out]


def leader(st):
    """The player nearest the truck, or -1 if nobody has a spot."""
    ls = leaders(st)
    return ls[0] if ls else -1


def _step_toward(st, i, goal):
    """Move tiger i one spot along the shortest way, through spots no player holds (never the truck), to a spot
    touching goal. A tiger off the island comes out of the jungle on a free spot touching goal, the one farthest from
    the truck (beside or behind the leader rather than in its way)."""
    start = st.tigers[i]
    if start < 0 or (st.s["pounce"] and start not in NB[goal]):
        free = [n for n in NB[goal] if st.owner[n] == -1 and n != CENTER and not tiger_at(st, n)]
        if free:
            st.tigers[i] = max(free, key=lambda n: (DIST[n], -n))
        return
    if start in NB[goal]:
        return
    prev = {start: -1}
    queue = [start]
    found = -1
    k = 0
    while k < len(queue):
        t = queue[k]
        k += 1
        if t in NB[goal]:
            found = t
            break
        for n in NB[t]:
            if n not in prev and st.owner[n] == -1 and n != CENTER and not tiger_at(st, n):
                prev[n] = t
                queue.append(n)
    if found < 0:
        return
    while prev[found] != start:
        found = prev[found]
    st.tigers[i] = found


def tiger_attack(st, p, t, a, until_miss):
    """The tiger attacks p's lights on t with strength a. Returns [(roll, chance), ...]."""
    rolls = []
    while lights(st, p, t) > 0:
        roll = d10(st)
        c = chance_of(a, lights(st, p, t))
        rolls.append((roll, c))
        if roll > c:
            break
        _take(st, p, t, 1)
        if t != CENTER and st.owner[t] == -1:
            st.units[t] = st.s["regrow"]              # the jungle takes it back
            break
        if not until_miss:
            break
    return rolls


def tiger_phase(st):
    s = st.s
    on = on_truck(st)
    if on:                                            # the tiger goes for everyone on the truck
        a = s["tigerHoldA"] + (st.crowds if s["crowd"] == 2 else 0)
        for p in on:
            rolls = tiger_attack(st, p, CENTER, a, s["tigerUntilMiss"])
            if st.tiger_log is not None:
                st.tiger_log.append([CENTER, p, rolls])
        left = on_truck(st)
        if len(left) > 1 and s["crowd"] == 1:
            most = max(st.truck[p] for p in left)
            top = [p for p in left if st.truck[p] == most]
            if len(top) == 1:
                left = top
        if len(left) > 1:
            st.crowds += 1
        if len(left) == 1:
            st.over = True
            st.winner = left[0]
        elif not left:
            st.units[CENTER] = s["truckRegrow"]      # cleared off: jungle again
        return
    ls = leaders(st)
    for i in range(len(st.tigers)):
        ls = [p for p in ls if spots_of(st, p)]     # (an earlier tiger may have taken someone's last spot)
        if not ls:
            return
        p = ls[i % len(ls)]
        goal = min(spots_of(st, p), key=lambda t: (DIST[t], t))
        _step_toward(st, i, goal)
        if st.tigers[i] < 0:
            continue
        near = [t for t in NB[st.tigers[i]] if t != CENTER and st.owner[t] == p]
        if near:
            t = min(near, key=lambda x: (DIST[x], x))
            rolls = tiger_attack(st, p, t, s["tigerA"], False)
            if st.tiger_log is not None:
                st.tiger_log.append([t, p, rolls])
