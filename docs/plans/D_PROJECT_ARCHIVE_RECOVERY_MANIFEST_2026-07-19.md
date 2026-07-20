# D: Project Archive Recovery Manifest - 2026-07-19

Archive root:

```text
D:\Project Archive\2026-07-19\
```

This manifest proves that the Git repositories moved during the shelf cleanup
still open at their archived locations. Dirty counts are snapshots, not quality
scores, and must not be cleaned with reset/checkout commands.

## Git Repositories

| Archived path | Branch | Last local commit | Dirty rows | Recovery source |
| --- | --- | --- | ---: | --- |
| `537 Repos\Scouting2016` | `master` | `407dd66` (2017-02-15) | 0 | origin configured |
| `537 Repos\ScoutingCordova` | `master` | `5855054` (2017-03-16) | 3 | origin configured; local IDE state |
| `537 Repos\student-tracker` | `master` | `cdae89c` (2019-11-17) | 0 | origin configured |
| `crt-core` | `master` | `49e37ab` (2026-05-07) | 0 | origin configured |
| `fip` | `main` | unborn | 15 | archive is authoritative; no remote or commits |
| `journal\journal` | `main` | `764c473` (2025-01-05) | 3 | origin plus local source/assets |
| `lairworker\contour-cut-worker` | unborn | unborn | 0 tracked | archive is authoritative; source is untracked |
| `NickBlock.dev-legacy\nickblock.dev-gatsby` | `main` | `ac6bb62` (2025-02-11) | 214 | origin plus extensive local changes |
| `NickBlock.dev-legacy\nickblock.devold` | `main` | `0dbe60d` (2025-02-14) | 32 | origin plus local/untracked files |
| `nickblock.dev-new` | `main` | `b0ad8c3` (2025-02-08) | 10,180 | origin; tracked generated files were staged for deletion |
| `nickblockdesigns\react\nickblockdesigns` | `master` | `3b65ebc` (2023-01-22) | 13 | local Git history; no origin |
| `nickblock-dev` | `master` | `86e15af` (2025-02-11) | 2 | local Git history; no origin |
| `RBL\RBL-frontend` | `main` | `6b9f936` (2024-05-09) | 154 | origin plus local/deleted files |
| `RBL\SAVE\backend\rbl_api` | `master` | `c59e778` (2024-01-06) | 0 | origin configured |
| `RBL\SAVE\backend\rbl_login` | `master` | `babfc89` (2024-01-10) | 1 | origin plus local modification |
| `RBL\SAVE\roastbattleleague` | `master` | `42ad57a` (2024-01-08) | 2 | local Git history; no origin |
| `RBL\SAVE\RoastBattleLeague.com` | `main` | `1836bd8` (2024-01-12) | 0 | origin configured |

## Cleanup-Induced Dirty Rows

Before generated folders were staged, these repositories already had dirty
rows:

```text
nickblock.dev-gatsby: 213
nickblock.devold: 30
nickblock.dev-new: 23
```

After staging rebuildable `node_modules`, `.cache`, `dist`, or `build` folders,
their counts became 214, 32, and 10,180 respectively. The large third count is
because the historical repository tracked dependency/build files. Those files
remain recoverable from Git history even after the deletion staging root is
removed. Do not confuse these cleanup-induced tracked deletions with previously
uncommitted source work.

## Non-Git Assets And Source

The dated archive also contains non-Git project roots that remain authoritative
for their local content:

```text
atc
Discord
FIPproject
nickblockdevbackup
ROCmetals
RocMetalworks
ShelterSnap
testing
theprintinglair
```

These include Illustrator originals, rendered design options, app generations,
small prototypes, and source backups. Their age is not evidence that they are
duplicates.

## Recovery Rules

- Do not run `git reset --hard`, `git clean`, or checkout-based cleanup here.
- For repositories with no remote or unborn history, the archive is the only
  known recovery source.
- Restore a moved project by moving its complete archive directory back to its
  recorded original path in `D_PROJECT_SHELF_CLEANUP_2026-07-19.md`.
- Reinstall dependencies only after choosing to reactivate a project.
- The generated-output deletion staging root is not a backup.
