# Changelog

## Unreleased

- **Suggested pairs.** A new "Подобрать пары / Suggest pairs" button ranks the pairings the game
  would accept, using the game's own breeding numbers: compatibility (the initiator's total
  charisma × the partner's libido × lover affinity × sexuality, anything under 5% turned down),
  stat inheritance biased towards the better parent by the room's Stimulation, active and passive
  ability odds with their guaranteed thresholds, Skill Share+, inbreeding, birth defects and
  disorders.
- **Room recommendation.** Cats can be moved between rooms, so every pair is also given the room
  that suits it best: the highest Stimulation whose Comfort stays workable once the pair moves in
  (Comfort at −10 or less fails the rolls outright, and rooms holding BreedSuppression furniture
  — the Idol of Chastity — never breed at all). Each room's Stimulation and Comfort are summed
  from the furniture standing in it in the save.
- Gear and mutation stat modifiers are now exported, so compatibility uses the cat's total
  charisma rather than its base value.

## 1.0.0 — 2026-10-08

First public release. Tested on Mewgenics 1.1.

- Family tree of the whole colony from the save file: house lines, all families, all cats,
  favourites; ancestors and descendants highlighted on click.
- Cats drawn from the game's own parts: faces on the tree, whole cats in the game's family
  tree frame in the side panel, with a big view on click.
- Cat panel: stats with the born-with-7 highlight, abilities, passives, disorders, mutations
  and equipment with game icons and descriptions, sex, orientation, room or fate.
- Pair comparison: common ancestors, kitten inbreeding, base stat range, orientation check.
- Fun stats: the colony in numbers, love life, where everyone went, 30 awards.
- Favourites and a pet cat with in-game quotes.
- Game wallpaper, font and icons; settings to turn the heavy parts off.
- All saves and Steam accounts on one page with a switcher.
- English and Russian.
- Windows exe, plus run.bat / run.sh to run from source on Windows, Linux, Steam Deck and macOS.
