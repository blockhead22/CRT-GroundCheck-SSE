# D: Project Shelf Cleanup - 2026-07-19

## Scope

This pass covers project-like roots on `D:\` outside the live `AI_round2`
working tree. It is intentionally conservative: rebuildable dependency and
build output can be removed, while dirty repositories and unique source or
design assets stay available until they have a verified recovery path.

## Completed Cleanup

Thirty-seven explicit generated directories were moved out of project trees to:

```text
D:\_pending_delete_generated_2026-07-19\
```

The staged payload measures:

```text
7,555,819,979 bytes (about 7.04 GiB)
502,435 files
66,580 directories
```

The moved directories were limited to paths named:

```text
node_modules
.cache
dist
build
```

Every moved path passed an explicit `D:\` root check and had a nearby package
lock, package manifest, Gradle build file, or settings file. No source root,
Git metadata, database, upload folder, or creative asset directory was included
in this generated-output batch.

Ten stale April/May Aether smoke artifacts were moved from `D:\tmp` into the
same deletion root. `D:\tmp\check_matters.py`, modified 2026-07-08, was kept.

The following empty roots were also staged:

```text
D:\fipnode
D:\fip-node
D:\flightsim
```

`D:\aiproject` was staged after verification showed that it contained only an
unborn `.git` directory, zero tracked files, and no working files. The empty
`D:\AI_round2\_external_cleanup_quarantine` placeholder was staged as well.

## Physical Reorganization

Nineteen historical roots were moved intact to:

```text
D:\Project Archive\2026-07-19\
```

The clean historical `D:\crt-core` checkout was then moved there as a twentieth
root. Active Aether, Aeteros Filesystem, Project Board, Server3, and current
NickBlock.dev paths stayed at their original locations.

The archived Git recovery inventory is tracked in:

```text
D:\AI_round2\docs\plans\D_PROJECT_ARCHIVE_RECOVERY_MANIFEST_2026-07-19.md
```

The archive itself contains `D:\Project Archive\README.md` pointing back to
these tracked records.

## Active Or Current

Keep these paths in place:

| Path | Evidence |
| --- | --- |
| `D:\AI_round2` | Current Aether/CRT workspace; clean cleanup branch at audit time. |
| `D:\aeteros-filesystem` | Current filesystem project; clean tracked checkout. |
| `D:\projectboard` | Recent project board; local `board.db` change and untracked `.claude` state make it active/local. |
| `D:\NickBlock.dev\new_repo\CRT` | Current clean checkout of the CRT repository. |
| `D:\NickBlock.dev\new_repo\nickblock.dev` | Current portfolio checkout; only untracked `.claude` state at audit time. |
| `D:\NickBlock.dev\new_repo\printing-lair` | Current clean Printing Lair checkout. |
| `D:\NickBlock.dev\nickblock.dev` | Recent non-Git source/media mirror; preserve until compared with the active portfolio checkout. |
| `D:\Server3` | Recently modified operational/server tree; no deletion decision without a service audit. |

## Legacy But Preserve

These are not current shelf entry points, but they contain dirty state, unique
source, historical value, or creative assets. They were moved intact under
`D:\Project Archive\2026-07-19` so the active shelf is legible without losing
local-only work.

| Path or family | Why it is preserved |
| --- | --- |
| `crt-core` | Clean historical Aether Core checkout, preserved for lineage and comparison. |
| `537 Repos` | Historical Team 537 repositories; one checkout has local IDE changes. |
| `NickBlock.dev-legacy\nickblock.dev-gatsby` | Old portfolio clone with extensive uncommitted changes. |
| `NickBlock.dev-legacy\nickblock.devold` | Old portfolio clone with uncommitted and untracked files. |
| `nickblock.dev-new` | Old site checkout with a large tracked tree and dirty generated/output state. |
| `nickblock-dev` | Small local-only Gatsby repository with package changes. |
| `nickblockdevbackup` | Non-Git source backup; generated cache/output removed, source retained. |
| `nickblockdesigns` | Local-only design-site source with uncommitted changes. |
| `RBL` | Multiple historical repositories; frontend and backend worktrees contain local changes. |
| `ShelterSnap` | Multiple app generations plus original Illustrator/icon assets. |
| `journal` | Git checkout with local source and asset changes. |
| `fip` and `FIPproject` | Local experiments with untracked C++, Python, Node, and DirectOutput files. |
| `lairworker` | Local contour-cut worker source with no recoverable commit history. |
| `ROCmetals` and `RocMetalworks` | Original Illustrator files and rendered design options. |
| `atc`, `Discord`, `testing`, `theprintinglair` | Small historical prototypes/configuration preserved together. |

## Git Safety Findings

The audit found no basis for deleting old repositories as duplicates yet:

- several old NickBlock.dev clones have substantial uncommitted state;
- `D:\journal\journal` has a modified app file and untracked content;
- RBL checkouts contain deleted, modified, or untracked files;
- `D:\fip` has no tracked files even though it contains source and binaries;
- local-only repositories without remotes cannot be recovered by cloning.

Remote presence or an old date therefore does not qualify a source tree for
deletion. A future archive pass should snapshot local diffs/untracked manifests
before moving those roots.

## Pending Destructive Step

`D:\_pending_delete_generated_2026-07-19` is a deletion staging root, not an
archive. Its contents are either rebuildable generated output, stale smoke
artifacts, empty directories, or the zero-file `aiproject` Git placeholder.

Before permanent deletion, verify:

```text
all original generated paths remain absent
the staging root resolves exactly to D:\_pending_delete_generated_2026-07-19
no source or creative assets have entered the staging root
```

Once deleted, dependencies and build output must be regenerated from their
nearby manifests. Source repositories and dirty worktrees remain where they
were.

The verified native PowerShell deletion command was rejected by the local
command policy on 2026-07-19. No alternate-shell or UI bypass was attempted.
The payload therefore remains consolidated for one explicit manual deletion.

## Next Archive Pass

1. Capture concise dirty-state manifests for each archived legacy family.
2. Compare the archived NickBlock.dev clones and the recent non-Git mirror
   against the current portfolio checkout.
3. Decide whether the archived source trees also need compressed cold backups.
4. Keep Aether product roadmap priorities unchanged; this is repository hygiene,
   not a new feature lane.
