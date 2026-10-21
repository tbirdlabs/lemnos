# Island Rush Rules v0.6

Oct 21, 2026 · Jim O'Neill

Split off from Salient: Island Rush is now its own game, built from scratch with its own simple rules. It keeps the board's way of showing things (your bar, green out of 10) and nothing else from Salient's rules: no ships, supply lines, cut-off spots, dug in, naval support, overrun, pushes or volcano.

The names (the board's, and the games') are still being decided.

## The game

Up to 6 players race through the jungle to the taco truck in the middle of the island. Mostly everyone fights the jungle, but anyone in your way can be rolled off their spot. Only one can hold the truck, so there it's king of the hill. Nobody is knocked out; everyone plays to the end.

## How to play

1. **You start in a corner** of the island with 3 lights. Your straight way to the truck is 3 spots long.
2. **Each turn your bar fills with new lights.** Each move uses one.
3. **Pick your own spot to add a light** (up to 3 a spot).
4. **Pick a jungle spot next to yours to clear it.** Your bar shows your chance: green out of 10. Win and the jungle loses a light; clear its last one and you move in. Lose and you lose a light. Another player's spot next to yours works the same way, against their lights there: win and you roll them off it in one go (their lights go back to their spots beside it) and move in.
5. **The tigers prowl the jungle and go for whoever is closest to the truck,** biting the spot of theirs nearest the truck. One tiger with 2 or 3 players, two with 4 to 6. A tiger in your way? Pick it to fight it: win and it runs off until the end of the round.
6. **Hold the truck and survive the tiger to win.** One player holds the truck at a time. Get there when someone's on it and you roll them off it: win, and their lights go back to their spot beside the truck and you move in; lose, and you lose a light. At the end of every round the tiger attacks whoever holds the truck. If they're still on it, they win.

## What the lights mean

| You see | It means |
| --- | --- |
| Green | Jungle: 1 to 3 lights, like a player's |
| Dark | Cleared ground: anyone next to it can walk in |
| Your color | Your spots and lights |
| White, glowing slowly | The taco truck (the center spot), empty |
| The truck in a player's color | Who holds the truck, and how many lights they have there |
| Orange lights running round a spot | The tiger (at the end of a round you see it walk through the jungle; it can stand on the truck when no one holds it) |
| Your bar, lit | Lights you can use |
| Your bar, green and red | Your chance to clear this spot |
| Orange and your color on your bar, a white light running | The tiger attacking you: orange is its chance |

Players' colors: red, blue, yellow, purple, cyan and pink (not green, orange or white: the jungle, the tiger and the truck).

## Under the hood

- **Jungle:** thicker toward the middle: 1 light on the outer ring, 2 on the middle ring, 3 on the inner ring. The truck has none: the tiger is its guard.
- **New lights:** 3 a turn, the same for everyone (holding more spots gives nothing: it's a race). The bar holds 10; unused lights carry over.
- **Clearing:** chance = 10 × A / (A + D), rounded, kept between 1 and 9. A = all your lights on spots touching it; D = its jungle lights. A win takes one jungle light. When the last one goes, 1 light moves in from your strongest spot touching it, if that spot has 2 or more; otherwise the spot stays empty, and anyone touching it can walk in for one light, no roll. A loss takes a light from your strongest spot touching it.
- **Rolling someone off a spot:** a player touching another player's spot can pick it to roll them off. Chance as for clearing, with A = all the attacker's lights touching it and D = the other player's lights on it. One roll. A win rolls them off: their lights there go back to their other spots touching it (never the truck), the emptiest first, up to 3 a spot, and the rest are lost; then 1 light moves in from the attacker's strongest spot touching it, if that has 2 or more (otherwise the spot is left empty). A loss takes a light from the attacker's strongest spot touching it. Tigers still can't walk through players' spots.
- **The tigers:** one for every 3 players (one with 2 or 3, two with 4 to 6). The first goes after the player closest to the truck, the second after the next closest; ties for closest go to the one with more lights on the island. At the end of every round each tiger walks through the jungle and cleared ground (never a player's spot, the other tiger's spot, or the truck while someone holds it) to a spot beside its player's lead spot (their spot nearest the truck): the one nearest the truck that isn't in the player's way, jungle before cleared ground, by the shortest walk. A tiger already beside its player moves round to another spot beside it, if there is one. Then it attacks the lead spot: chance as above with the tiger's strength as A (2) against that spot's lights. A win takes one light; the spot is the jungle's again if it empties. A tiger boxed in by players' spots, with no way through, leaps there instead (about 1 tiger turn in 20 with 6 players, never with 2).
- **Fighting a tiger:** a tiger's spot is closed until it moves, but a player touching it can pick it to fight it. Chance as for clearing, with A = all the player's lights touching it and D = the tiger's strength (2). One roll. A win drives the tiger off the island; whatever is under it (jungle or cleared ground) stays, and it comes back at the end of the round the way it first shows up, leaping next to its player. A loss takes a light from the player's strongest spot touching it. A tiger standing on the open truck is fought the same way, and nobody can get on the truck until it's gone.
- **Holding the truck:** with no one on it, a player touching it moves in (1 light, leaving 1 behind, no roll) and can add lights there (up to 3). Only one player holds it at a time.
- **Rolling someone off the truck:** the same as off a spot, against the holder's lights on the truck. The holder's lights go back to their spots beside the truck; if the challenger can't move in, the truck is left open.
- **Winning:** while someone holds the truck, the tigers skip their moves and the tiger attacks the holder at the end of the round, going on until it misses (strength 2). If the holder is still on the truck, they win. If it clears them off, the truck is jungle again (1 light) and play goes on. Whoever gets there, in whatever seat, faces the same tiger; the players after them in the round get one turn each to roll them off first.
- **Starting over:** a player left with no spots starts again in their corner with 3 lights at their next turn (if the corner is free; otherwise the nearest free spot on their side).
- **Turn order:** clockwise from the lowest seat. Who starts moves on each round (the lowest seat starts round 1, the next round 2, and so on), so nobody is always the last before the tiger.
- **Computer players:** fill seats no one takes. They play by rules of thumb: only clear spots that bring them a step nearer the truck, going round other players' spots (they roll another player off a spot only when others' spots cut off every way to the truck); clear at 5 green or better, otherwise build up beside the spot they want; with a tiger on the way they go round on another way just as short if there is one, otherwise fight it at 5 green or better (or build up beside it first). They challenge the truck's holder at 5 green or better, otherwise build up beside it. On the truck they fill it up, then top up their spots beside it. No difficulty levels yet.
- **Setup on the board:** press pick to join. Move picks a corner, pick takes it; move picks a color, pick takes it. The first to join then sets how many play in all (2 to 6, lit on their bar); the computer plays the rest, spread round the board. Pick starts. Back undoes a step. The USB page can set it up instead (the number of players, and each controller's seat).

## Open questions

- [ ] Skill: charging beats being careful about 1.6 to 1, so the game's only real choice is how hard to push. Fine for a mixed table; little for an adult to master.
- [ ] Difficulty for the computer players.
- [ ] Jungle growing back on empty spots no one holds.
- [ ] Game length: about 3-4 minutes with 2 players, 8 with 6 (at about 15 s a turn). Thicker jungle makes it longer.
- [ ] Which corner each seat gets (each corner sits between two seats): the left end of your side, as you face the board.

## What the simulator showed

`tools/sim_rush.py` (Python, every core). 2000 games each (v0.6); wins by turn order (%):

| Players | Careful players | Beginners | Median rounds (careful / beginners) |
| --- | --- | --- | --- |
| 2 | 44 / 55 | 45 / 54 | 7 / 6 |
| 3 | 27 / 35 / 37 | 30 / 32 / 36 | 6 / 5 |
| 4 | 18 / 29 / 27 / 24 | 21 / 24 / 23 / 30 | 6 / 5 |
| 6 | 15 / 18 / 14 / 15 / 17 / 18 | 12 / 13 / 18 / 21 / 18 / 15 | 5 / 5 |

No draws (60 rounds). 9 games in 10 end by round 7-11. Holders rolled off the truck by another player 0.3-1.8 times a game (more with more players). Careful against beginners, 2 players: 39 / 61. Tiger fights (beginners): none with 2 players (the one tiger stands beside its leader, never in anyone's way), 0.7 a game with 4 (won 59%), 1.9 with 6 (won 51%). A tiger stands on the truck in about 1 round in 100 with 6 players. The computer players never rolled each other off a spot (1200 games): none of them was ever cut off from the truck, so the results are v0.5's. One walled out by a ring round the truck attacks the ring.

How v0.1 got there: one player holding the truck made moving first worth a lot (65/35 between careful players). A shared truck with jungle on it flipped that (later seats finished the jungle earlier seats had cut down: 32/67). No jungle on the truck: 44/55. Crowds that never left the truck made 20% of 6-player games draws: an angrier tiger (or most lights wins) ended them. Rotating who starts each round evened 3 to 6 players. Charging (beginners) beats careful play about 2 to 1 head to head.

## Changes

| Version | Change |
| --- | --- |
| v0.6 | Players' spots are no longer walls: a player can roll another off a spot next to theirs, like the truck (one roll, their lights against yours touching it; a win sends their lights back to their spots beside it and you move in, a loss costs a light). Stops a player ringing the truck with their spots to lock everyone else out and retry the truck as often as the tiger clears them off it. |
| v0.5 | A tiger in your way can be fought (your lights touching it against its 2): a win drives it off the island until the end of the round. Tigers can walk across and stand on the truck when no one holds it. With 4-6 players the second tiger, standing beside its player on the ring round the truck, blocked others' only way in on 3-5% of turns, and it couldn't move while someone held the truck. |
| v0.4 | One player holds the truck at a time. Another who gets there rolls them off it once (their lights against the challenger's lights touching the truck): a win sends the holder's lights back to their spot beside the truck (the rest are lost) and the challenger moves in; a loss costs the challenger a light. The tiger attacks the holder at the end of the round; a holder left on it wins. Replaces the shared truck and the angrier tiger: players on the truck had nothing to do, and a crowd there was settled by the tiger's dice alone. |
| v0.3 | The tigers walk through the jungle to their leader's lead spot (one step at a time on the board) and bite it, standing beside it rather than behind it, and move round it each round instead of sitting still. A tiger right in the leader's way was tried and dropped: on the straight way in from a corner each spot has only one spot nearer the truck, so the tiger walled the leader in and the leader went sideways round it. Tigers now stand still in about 1 round in 5 (only when there's no other spot beside their leader), down from 1 in 2. Computer players only clear spots that bring them nearer the truck: before, 7-21% of their clears went sideways or back (mostly players already on the truck spending leftover lights on jungle, or going round a tiger that moves on anyway); now none. |
| v0.2 | The tigers pounce (jump next to their player) instead of walking one spot a round, and there's one for every 3 players. A walking tiger got boxed in by players' spots: with 6 players it attacked nobody in 19% of rounds, stood still in 35%, and bit the same player twice running 39% of the time. Now it attacks every round, the same player twice running 7%; 6 beginners win by seat 16/16/17/16/15/18%, game length unchanged. |
| v0.1 | First version, split off from Salient (Oct 21, 2026). |
