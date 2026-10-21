# Island Rush computer players: simple rules of thumb (the simulator's stand-ins, tools/sim_rush.py).
#   beginner  spends every light every turn: clears toward the truck at 5 green or better, otherwise builds up beside
#             the spot it wants. The board's computer players play this way (it does as well as anything simple).
#   careful   the same at 6 green or better; when it can't build up any more, it widens its way first (clears a spot
#             beside the one it wants, at 6 green or better) rather than go at worse odds.
# It only clears spots that bring it a step nearer the truck, going round other players' spots; only when they cut off
# every way to the truck does it roll them off a spot in the way, as it would clear jungle. A tiger standing on the
# way: it goes round on another way just as short if there is one, otherwise fights the tiger off the same way. On
# the truck, both fill it up first, then top up their spots beside it.

import random
from . import engine as E

STYLES = {"beginner": (5, False), "careful": (6, True)}   # (go at, widen)
FAR = 99


def ways(st, p, walls=True):
    """Steps from each spot to the truck for p, through anything but other players' spots (with walls; FAR: no way)."""
    far = [FAR] * E.N
    far[E.CENTER] = 0
    queue = [E.CENTER]
    k = 0
    while k < len(queue):
        t = queue[k]
        k += 1
        for n in E.NB[t]:
            if far[n] == FAR and (not walls or st.owner[n] in (-1, p)):
                far[n] = far[t] + 1
                queue.append(n)
    return far


def choose(st, style="beginner", rng=random):
    """(verb, spot) for the player whose turn it is. rng: anything with random() (tests pass a seeded one)."""
    go, widen = STYLES[style]
    p = st.cur
    acts = E.legal_actions(st)
    clears = set(t for v, t in acts if v == E.V_CLEAR)
    adds = set(t for v, t in acts if v == E.V_ADD)
    if E.CENTER in adds:                                 # on the truck: fill it up first
        return E.V_ADD, E.CENTER
    if st.truck[p] > 0:                                 # on the truck and full: top up its spots beside the truck
        beside = [n for n in E.NB[E.CENTER] if n in adds]
        if beside:
            return E.V_ADD, min(beside, key=lambda n: (E.lights(st, p, n), rng.random()))
        return E.V_END, -1
    mine = E.spots_of(st, p)
    if not mine:                                         # wiped out with its corner taken: wait for a free spot
        return E.V_END, -1
    far = ways(st, p)
    best = min(far[t] for t in mine)
    if best == FAR:                                      # walled in by other players: through them
        far = ways(st, p, False)
        best = min(far[t] for t in mine)
    wants = []
    for t in range(E.N):
        if far[t] >= best or E.lights(st, p, t) > 0:
            continue
        if any(E.lights(st, p, n) > 0 for n in E.NB[t]):
            wants.append(t)
    wants.sort(key=lambda t: (E.tiger_at(st, t), -E.chance(st, p, t), rng.random()))
    for t in wants:
        if t in clears and E.chance(st, p, t) >= go:  # (walking onto empty ground is 10 green)
            return E.V_CLEAR, t
        beside = [n for n in E.NB[t] if n in adds]
        if beside:
            return E.V_ADD, min(beside, key=lambda n: (E.lights(st, p, n), rng.random()))
        if t in clears:
            wide = []
            if widen:
                wide = [n for n in E.NB[t] if n in clears and st.owner[n] == -1 and not E.tiger_at(st, n) and
                        E.chance(st, p, n) >= go]
            if wide:
                return E.V_CLEAR, max(wide, key=lambda n: (E.chance(st, p, n), rng.random()))
            return E.V_CLEAR, t
    return E.V_END, -1                                   # nothing to do toward the truck: keep the lights
