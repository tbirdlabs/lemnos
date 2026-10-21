# Island Rush simulator (games/rush/engine.py): stand-in players race to the truck, many games on every core.
#
#   py -3 tools/sim_rush.py --games 400 --players 2,3,4,6 --who careful,beginner
#   py -3 tools/sim_rush.py --games 400 --set tigers=2 --set tigerHoldA=3
#
# Stand-ins: careful (clears toward the truck at 6 green or better, otherwise builds up beside it, or widens its way
# rather than go at worse odds), beginner (spends every light every turn, goes at 5 green or
# better, otherwise builds up), random (any legal move but ending early). --who lists one kind per seat in turn
# order (repeated to fill), so "careful,beginner" alternates them.
# Reports per player count: rounds to a win (median, 10th-90th), draws (the round cap), wins by turn order and by
# kind, how often players got onto the truck and were rolled off it by another, and how
# often the tiger attacked a spot off the truck.

import argparse
import os
import random
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from games.rush import ai as AI, engine as E   # noqa: E402

SEATS = {1: (1,), 2: (1, 4), 3: (1, 3, 5), 4: (1, 2, 4, 5), 5: (1, 2, 3, 4, 5), 6: (1, 2, 3, 4, 5, 6)}


def careful(st, rng):
    return AI.choose(st, "careful", rng)


def beginner(st, rng):
    return AI.choose(st, "beginner", rng)


def randomly(st, rng):
    acts = [a for a in E.legal_actions(st) if a[0] != E.V_END]
    return rng.choice(acts) if acts else (E.V_END, -1)


KINDS = {"careful": careful, "beginner": beginner, "random": randomly}


def one(job):
    seats, who, rules, seed = job
    rng = random.Random(seed)
    st = E.new_game(seats, seed * 7919 + 1, rules)
    st.tiger_log = []
    arrivals = 0                                     # a player getting onto the truck
    bumps = 0                                        # a holder rolled off it
    while not st.over:
        p = st.cur
        was = st.truck[p]
        held = E.holder(st)
        verb, t = KINDS[who[st.cur]](st, rng)
        E.apply(st, verb, t)
        if was == 0 and st.truck[p] > 0:
            arrivals += 1
        if held >= 0 and held != p and st.truck[held] == 0 and verb == E.V_CLEAR and t == E.CENTER:
            bumps += 1
    bites = sum(1 for e in st.tiger_log if e[0] != E.CENTER and e[2])
    return st.winner, st.round, arrivals, bites, bumps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=400)
    ap.add_argument("--players", default="2,3,4,6")
    ap.add_argument("--who", default="careful")
    ap.add_argument("--set", action="append", default=[], help="a rule, e.g. tigers=2")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    a = ap.parse_args()
    rules = {}
    for kv in a.set:
        k, v = kv.split("=")
        rules[k] = tuple(int(x) for x in v.split("/")) if "/" in v else int(v)
    kinds = a.who.split(",")
    print("rules: %s   players: %s" % (rules or "defaults", a.who))
    with Pool(a.workers) as pool:
        for n in (int(x) for x in a.players.split(",")):
            who = [kinds[i % len(kinds)] for i in range(n)]
            res = pool.map(one, [(SEATS[n], who, rules, g + 1) for g in range(a.games)])
            rounds = sorted(r[1] for r in res if r[0] >= 0)
            draws = sum(1 for r in res if r[0] < 0)
            by_order = [sum(1 for r in res if r[0] == i) for i in range(n)]
            by_kind = {}
            for i, k in enumerate(who):
                by_kind[k] = by_kind.get(k, 0) + by_order[i]
            arrivals = sum(r[2] for r in res)
            bumps = sum(r[4] for r in res)
            q = lambda f: rounds[min(len(rounds) - 1, int(f * len(rounds)))] if rounds else 0
            print("%d players: rounds median %d (10%%-90%%: %d-%d), draws %d%%; wins by turn order %s; by kind %s; "
                  "onto the truck %.1f times a game, rolled off it %.1f; tiger bites %.1f a game"
                  % (n, q(0.5), q(0.1), q(0.9), 100 * draws // len(res),
                     "/".join("%d" % (100 * x // len(res)) for x in by_order),
                     ", ".join("%s %d%%" % (k, 100 * v // len(res)) for k, v in by_kind.items()),
                     arrivals / len(res), bumps / len(res), sum(r[3] for r in res) / len(res)),
                  flush=True)


if __name__ == "__main__":
    main()
