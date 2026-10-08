# MewTree — a proper family tree for Mewgenics

*[Русская версия ниже](#mewtree--нормальное-семейное-древо-для-mewgenics)*

MewTree reads your Mewgenics save and builds one web page with the whole colony: every cat
that ever passed through the house (alive, dead or given away), who descends from whom,
inbreeding, stats, abilities, mutations and a pile of silly statistics.

It is **not a game mod**: nothing is injected and no game file is changed. It is a small
program next to the game that only *reads a copy* of the save.

## What you get

- **The whole tree.** Lines of the cats at home, all families, or every cat. Click a cat to
  light up its ancestors and descendants.
- **Cats that look like your cats.** Faces and whole bodies are put together from the game's
  own parts, palette and pose, the same way the game does it, inside the game's family tree
  frame.
- **Everything about a cat.** Base stats and bonuses, abilities, passives, disorders,
  mutations and equipment with the game's icons and descriptions; sex and orientation; where
  it lives or how it ended.
- **Breeding help.** Born-with-7 stats are highlighted in gold. "Compare a pair" shows the
  common ancestors, the kitten's inbreeding (Wright's coefficient, as the game counts it), the
  range of base stats and whether the two would look at each other at all.
- **Fun stats.** Death rate, the deadliest class, how many cats died virgins, who loves whom,
  where everyone went, and a "wall of fame and shame" with 30 awards.
- **Favourites and a pet cat.** Star the cats you care about; pick one pet cat that greets
  you with a random in-game line on every refresh.
- **Game look.** The game's wallpaper, font, stat, class and ability icons.
- **English and Russian**, switchable on the page. Game texts follow the same switch.
- **Live.** Leave it running: the page is rebuilt after every save, just refresh the tab.

## Requirements

- Windows 10/11 (the `.exe`). Linux / Steam Deck / macOS: run from source with Python 3.10+
  (the save and game lookup is written for them, but only Windows has been tested).
- Mewgenics installed through Steam. Tested on game version **1.1**.
  Without the game the page still works, but with plain icons and internal names.
- A web browser.

## Install and use

1. Download `MewTree-x.y.z.zip` from the releases and unpack it anywhere (not into the game
   folder, there is no need).
2. Run `MewTree.exe`. It finds Steam, the game and your saves, writes `mewtree.html` next to
   itself and opens it.
3. Keep the window open while you play. After the game saves, press F5 in the browser.

Several saves or Steam accounts: pick one from the list under the page title.
You can also drop any `.sav` file onto `MewTree.exe`.

Windows may warn about an unknown publisher: the exe is not signed. Build it yourself from
the source if you prefer (below).

### Command line

```
MewTree.exe --list        where it looked and what it found
MewTree.exe --pick        choose the save in the console
MewTree.exe --save PATH   open this save
MewTree.exe --gpak PATH   path to resources.gpak
```

Environment variables: `STEAM_DIR`, `MEWGENICS_SAVES` (the folder that holds
`<SteamID>\saves`), `MEWGENICS_GPAK`, `MEWTREE_LANG` (`ru` / `en`, console language).

### From source (Windows, Linux, Steam Deck, macOS)

The repository holds the sources in `src/` and the launch scripts next to them:

```
run.bat          Windows: build the page and watch the saves
./run.sh         Linux / Steam Deck / macOS: the same
build_exe.bat    Windows: make MewTree.exe with PyInstaller
```

Only Python 3.10+ is needed, no third-party packages. On Linux the saves are looked up in the
Proton prefixes of every Steam library (`steamapps/compatdata/*/pfx/...`). The scripts take
the same options as the exe, e.g. `./run.sh --list`. The page lands next to the scripts.

## Uninstall

Delete the folder. MewTree writes only `mewtree.html` and `mewtree.json` next to itself.
Favourites, the pet cat and settings live in your browser's storage for that page.

## Troubleshooting

- **"No save found"**: run `MewTree.exe --list` to see where it looked, or drop the `.sav`
  onto the exe. Saves are in `%APPDATA%\Glaiel Games\Mewgenics\<SteamID>\saves`.
- **Plain icons and odd names**: the game was not found. Pass `--gpak` with the path to
  `resources.gpak`.
- **The page is slow**: Settings → turn off "Faces from the game".
- **A game update broke it**: the save format or the game files changed. Please open an
  issue with the game version.

## Good to know

- Your save is never written to; MewTree works on a temporary copy.
- No game files are included here. All art, fonts and texts are read from *your* installed
  copy when the page is built. Because of that the generated `mewtree.html` contains game
  art: keep it for yourself and friends, do not re-host it.
- Orientation labels use the game's own thresholds. "Would they pair up" in the pair view is
  a simple rule (straight: the other sex, gay: the same sex, bi: anyone), not the game's code.
- "Died a virgin" means no kittens and no lover recorded in the save.

## Credits

- Save layout: [p0lymeric/mewgenics_analysis](https://github.com/p0lymeric/mewgenics_analysis)
  (MIT) for the cat record fields; the rest was worked out for this tool.
- Cat composition and the Flash (SWF) reader come from my
  [Combat Roster Panel](https://github.com/TotSamiyMorzh/mewgenics-combat-roster) mod.
- Mewgenics is by Edmund McMillen and Tyler Glaiel. This is an unofficial fan tool.
- **AI disclosure:** MewTree was built by Claude Code (Claude Opus 5.5) with the
  [universal-modder](https://github.com/rehan-remade/universal-modder) skills and tested by a
  human on a real 140-day save. No AI-generated art: every picture is the game's own,
  rendered at build time.

## License

MIT for the code, see [LICENSE](LICENSE). Game assets belong to their owners and are not
part of this repository.

---

# MewTree — нормальное семейное древо для Mewgenics

MewTree читает сейв Mewgenics и собирает одну веб-страницу со всей колонией: все коты,
которые прошли через дом (живые, погибшие, отданные), кто от кого, инбридинг, статы,
способности, мутации и куча дурацкой статистики.

Это **не мод**: в игру ничего не внедряется и файлы игры не меняются. Это программка рядом
с игрой, которая только *читает копию* сейва.

## Что умеет

- **Всё древо.** Линии котов в доме, все семьи или вообще все коты. Клик по коту подсвечивает
  его предков и потомков.
- **Коты как в игре.** Морда и тело собираются из тех же частей, палитры и позы, что и в игре,
  в рамке с игрового экрана родословной.
- **Всё про кота.** Базовые статы и прибавки, способности, пассивки, расстройства, мутации и
  снаряжение с игровыми иконками и описаниями; пол и ориентация; где живёт или чем кончил.
- **Помощь в разведении.** Врождённые семёрки подсвечены золотом. «Сравнить пару» показывает
  общих предков, инбридинг котёнка (по Райту, как считает игра), разброс базовых статов и
  подойдут ли коты друг другу по ориентации.
- **Приколы.** Смертность, самый смертельный класс, сколько котов умерло девственниками, кто
  в кого влюблён, куда все делись и «доска почёта и позора» на 30 номинаций.
- **Избранные и любимчик.** Звёздочки для важных котов и один любимчик, который при каждом
  обновлении страницы говорит случайную фразу из игры.
- **Вид как в игре.** Обои, шрифт, значки статов, классов и способностей из игры.
- **Русский и английский**, переключаются на странице вместе с текстами игры.
- **Вживую.** Не закрывай окно: после каждого сохранения страница пересобирается, остаётся
  обновить вкладку.

## Что нужно

- Windows 10/11 (для `.exe`). Linux / Steam Deck / macOS: запуск из исходников, Python 3.10+
  (поиск сейвов и игры для них написан, но проверялась только Windows).
- Mewgenics, установленная через Steam. Проверено на версии **1.1**.
  Без игры страница соберётся, но с простыми иконками и внутренними названиями.
- Браузер.

## Установка и запуск

1. Скачай `MewTree-x.y.z.zip` из релизов и распакуй куда угодно (в папку игры не нужно).
2. Запусти `MewTree.exe`. Он найдёт Steam, игру и сейвы, положит рядом `mewtree.html` и
   откроет его.
3. Не закрывай окно, пока играешь. После сохранения в игре нажми F5 в браузере.

Несколько сейвов или аккаунтов Steam: выбери нужный в списке под заголовком страницы.
Можно просто перетащить любой `.sav` на `MewTree.exe`.

Windows может ругнуться на неизвестного издателя: exe не подписан. Если не доверяешь,
собери его сам из исходников (`build_exe.bat`).

**Linux / Steam Deck / macOS и запуск из исходников.** В репозитории исходники лежат в `src/`,
рядом скрипты: `run.bat` (Windows), `./run.sh` (Linux / Steam Deck / macOS) и `build_exe.bat`
(собрать `MewTree.exe`). Нужен только Python 3.10+, сторонних пакетов нет.

Команды: `--list` (где искал и что нашёл), `--pick` (выбрать сейв в консоли),
`--save ПУТЬ`, `--gpak ПУТЬ`. Переменные окружения: `STEAM_DIR`, `MEWGENICS_SAVES`,
`MEWGENICS_GPAK`, `MEWTREE_LANG` (`ru` / `en`).

## Удаление

Удали папку. MewTree пишет только `mewtree.html` и `mewtree.json` рядом с собой.
Избранные, любимчик и настройки лежат в хранилище браузера для этой страницы.

## Если что-то не так

- **«Сейв не найден»**: `MewTree.exe --list` покажет, где он искал; или перетащи `.sav` на exe.
  Сейвы лежат в `%APPDATA%\Glaiel Games\Mewgenics\<SteamID>\saves`.
- **Простые иконки и странные названия**: игра не найдена, укажи `--gpak` с путём к
  `resources.gpak`.
- **Страница тормозит**: Настройки → выключи «Морды из игры».
- **Сломалось после обновления игры**: поменялся формат сейва или файлы игры. Напиши issue
  с версией игры.

## Стоит знать

- Сейв никогда не изменяется: MewTree работает с временной копией.
- Файлов игры здесь нет. Картинки, шрифт и тексты берутся из *твоей* установленной игры в
  момент сборки страницы. Поэтому готовый `mewtree.html` содержит графику игры: показывай
  друзьям, но не выкладывай в открытый доступ.
- Ориентация определяется по порогам самой игры. «Подойдут ли друг другу» в сравнении пары
  считается по простому правилу (натурал: другой пол, гей: свой, би: любой), а не по коду игры.
- «Умер девственником» значит: нет котят и нет записанного в сейве возлюбленного.

MewTree сделан Claude Code (Claude Opus 5.5) с помощью universal-modder и проверен человеком
на настоящем сейве. Графика не сгенерирована ИИ: всё нарисовано игрой.
