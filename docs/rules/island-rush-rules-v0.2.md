# Island Rush Rules v0.2

Oct 21, 2026 · Jim O'Neill

Split off from Salient: Island Rush is now its own game, built from scratch with its own simple rules. It keeps the board's way of showing things (your bar, green out of 10) and nothing else from Salient's rules: no ships, supply lines, cut-off spots, dug in, naval support, overrun, pushes or volcano.

The names (the board's, and the games') are still being decided.

## The game

Up to 6 players race through the jungle to the taco truck in the middle of the island. Nobody fights anybody: everyone fights the jungle. Nobody is knocked out; everyone plays to the end.

## How to play

1. **You start in a corner** of the island with 3 lights. Your straight way to the truck is 3 spots long.
2. **Each turn your bar fills with new lights.** Each move uses one.
3. **Pick your own spot to add a light** (up to 3 a spot).
4. **Pick a jungle spot next to yours to clear it.** Your bar shows your chance: green out of 10. Win and the jungle loses a light; clear its last one and you move in. Lose and you lose a light.
5. **The tigers go after whoever is closest to the truck.** One tiger with 2 or 3 players, two with 4 to 6.
6. **Get to the truck and survive the tiger to win.** Anyone can get on the truck, even when others are there. At the end of every round the tiger attacks everyone on it, and gets angrier each time it finds more than one. The last one left on the truck wins.

## What the lights mean

| You see | It means |
| --- | --- |
| Green | Jungle: 1 to 3 lights, like a player's |
| Dark | Cleared ground: anyone next to it can walk in |
| Your color | Your spots and lights |
| White, glowing slowly | The taco truck (the center spot), empty |
| The truck in players' colors, a second each | Who's on the truck, and how many lights each has there |
| Orange lights running round a spot | The tiger |
| Your bar, lit | Lights you can use |
| Your bar, green and red | Your chance to clear this spot |
| Orange and your color on your bar, a white light running | The tiger attacking you: orange is its chance |

Players' colors: red, blue, yellow, purple, cyan and pink (not green, orange or white: the jungle, the tiger and the truck).

## Under the hood

- **Jungle:** thicker toward the middle: 1 light on the outer ring, 2 on the middle ring, 3 on the inner ring. The truck has none: the tiger is its guard.
- **New lights:** 3 a turn, the same for everyone (holding more spots gives nothing: it's a race). The bar holds 10; unused lights carry over.
- **Clearing:** chance = 10 × A / (A + D), rounded, kept between 1 and 9. A = all your lights on spots touching it; D = its jungle lights. A win takes one jungle light. When the last one goes, 1 light moves in from your strongest spot touching it, if that spot has 2 or more; otherwise the spot stays empty, and anyone touching it can walk in for one light, no roll. A loss takes a light from your strongest spot touching it.
- **Other players:** their spots are walls to you. You can't attack them or walk through them.
- **The tigers:** one for every 3 players (one with 2 or 3, two with 4 to 6). At the end of every round each one pounces: it jumps to a free spot (jungle or cleared ground, never the truck or a player's spot) next to its player's spot nearest the truck, the one of those farthest from the truck, then attacks that spot: chance as above with the tiger's strength as A (2) against that spot's lights. A win takes one light; the spot is the jungle's again if it empties. The first tiger goes after the player closest to the truck, the second after the next closest. Ties for closest go to the one with more lights on the island. A tiger already next to its player stays put.
- **The truck is shared:** once its jungle is cleared, any player touching it can move in (1 light, leaving 1 behind, no roll), and each player on it keeps their own lights there (up to 3). Nobody can attack anybody there either.
- **Winning:** while anyone is on the truck, the tiger skips its move and attacks each of them at the end of the round, one after another, each attack going on until it misses (strength 2). Then, if exactly one player is left on the truck, they win. If more than one is left, play goes on: others can still arrive, and the tiger comes again next round. If the tiger clears everyone off, the truck is jungle again (1 light). Whoever gets there, in whatever seat, faces the same tiger.
- **An angrier tiger:** every round the tiger finds more than one player on the truck, its strength there goes up by 1 for the rest of the game, so a crowd can't sit there forever.
- **On the lights:** with several players on the truck, its LEDs take turns showing each player's color and lights, about a second each.
- **Starting over:** a player left with no spots starts again in their corner with 3 lights at their next turn (if the corner is free; otherwise the nearest free spot on their side).
- **Turn order:** clockwise from the lowest seat. Who starts moves on each round (the lowest seat starts round 1, the next round 2, and so on), so nobody is always the last before the tiger.
- **Computer players:** fill seats no one takes. They play by rules of thumb: clear toward the truck at 5 green or better, otherwise build up beside the spot they want, spend every light. No difficulty levels yet.
- **Setup on the board:** press pick to join. Move picks a corner, pick takes it; move picks a color, pick takes it. The first to join then sets how many play in all (2 to 6, lit on their bar); the computer plays the rest, spread round the board. Pick starts. Back undoes a step. The USB page can set it up instead (the number of players, and each controller's seat).

## Open questions

- [ ] Skill: charging beats being careful about 2 to 1, so the game's only real choice is how hard to push. Fine for a mixed table; little for an adult to master.
- [ ] Difficulty for the computer players.
- [ ] Jungle growing back on empty spots no one holds.
- [ ] Game length: about 3-4 minutes with 2 players, 8 with 6 (at about 15 s a turn). Thicker jungle makes it longer.
- [ ] Which corner each seat gets (each corner sits between two seats): the left end of your side, as you face the board.

## What the simulator showed

`tools/sim_rush.py` (Python, every core). 2000 games each; wins by turn order (%):

| Players | Careful players | Beginners | Typical rounds |
| --- | --- | --- | --- |
| 2 | 45 / 54 | 44 / 55 | 6-7 |
| 3 | 30 / 29 / 39 | 31 / 32 / 35 | 5-7 |
| 4 | 23 / 19 / 24 / 32 | 23 / 19 / 28 / 29 | 5-6 |
| 6 | 14 / 14 / 14 / 16 / 19 / 17 | 14 / 16 / 16 / 16 / 16 / 19 | 5-6 |

Draws (60 rounds) 0-2%. Two or more on the truck at once in 54-69% of games.

How v0.1 got there: one player holding the truck made moving first worth a lot (65/35 between careful players). A shared truck with jungle on it flipped that (later seats finished the jungle earlier seats had cut down: 32/67). No jungle on the truck: 44/55. Crowds that never left the truck made 20% of 6-player games draws: an angrier tiger (or most lights wins) ended them. Rotating who starts each round evened 3 to 6 players. Charging (beginners) beats careful play about 2 to 1 head to head.

## Changes

| Version | Change |
| --- | --- |
| v0.2 | The tigers pounce (jump next to their player) instead of walking one spot a round, and there's one for every 3 players. A walking tiger got boxed in by players' spots: with 6 players it attacked nobody in 19% of rounds, stood still in 35%, and bit the same player twice running 39% of the time. Now it attacks every round, the same player twice running 7%; 6 beginners win by seat 16/16/17/16/15/18%, game length unchanged. |
| v0.1 | First version, split off from Salient (Oct 21, 2026). |
