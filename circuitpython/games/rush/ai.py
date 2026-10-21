# Island Rush computer players: simple rules of thumb (the simulator's stand-ins, tools/sim_rush.py).
#   beginner  spends every light every turn: clears toward the truck at 5 green or better, otherwise builds up beside
#             the spot it wants. The board's computer players play this way (it does as well as anything simple).
#   careful   the same at 6 green or better, and keeps its lights for next turn rather than throw them at bad odds.
# On the truck, both fill it up first.

import random
from . import engine as E

STYLES = {"beginner": (5, False), "careful": (6, True)}


def choose(st, style="beginner", rng=random):
    """(verb, spot) for the player whose turn it is. rng: anything with random() (tests pass a seeded one)."""
    go, save = STYLES[style]
    p = st.cur
    acts = E.legal_actions(st)
    clears = [t for v, t in acts if v == E.V_CLEAR]
    adds = [t for v, t in acts if v == E.V_ADD]
    if E.CENTER in adds:                                 # on the truck: fill it up first
        return E.V_ADD, E.CENTER
    if not clears:
        if adds and not save:
            return E.V_ADD, min(adds, key=lambda t: (E.DIST[t], rng.random()))
        return E.V_END, -1
    # the target: nearest the truck, then the best odds
    target = min(clears, key=lambda t: (E.DIST[t], -E.chance(st, p, t), rng.random()))
    if E.chance(st, p, target) >= go:
        return E.V_CLEAR, target
    beside = [n for n in E.NB[target] if n in adds]
    if beside:
        return E.V_ADD, min(beside, key=lambda t: (st.units[t], rng.random()))
    others = [t for t in clears if E.chance(st, p, t) >= go]
    if others:
        return E.V_CLEAR, min(others, key=lambda t: (E.DIST[t], rng.random()))
    if save:
        return E.V_END, -1
    return E.V_CLEAR, target
