# ChatGPT Export Data

This folder contains the full ChatGPT conversation export (~7.2GB).
It is **not tracked in git** due to size — shared via Google Drive.

## Contents (when populated)

- `conversations-000.json` through `conversations-012.json` — raw conversation data (~650MB)
- `chat.html` — rendered conversation view (~599MB)
- `user-*/` — uploaded files/images (~347MB)
- `<conversation-id>/` folders — per-conversation media
- `export_manifest.json` — export metadata

## To restore on a new machine

1. Download from Google Drive (shared folder)
2. Extract into `data/chatgpt_export/`
3. This README should be the only file tracked in git
