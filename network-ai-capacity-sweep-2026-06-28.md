# Network AI Capacity Sweep - 2026-06-28

No credentials are included in this report.

## Workstation: NickPC

- IP: `192.168.1.91`
- CPU: Intel Core i7-9700KF, 8 cores / 8 threads
- RAM: 32 GB DDR4, installed as 4 x 8 GB Corsair modules
- Board: ASUS PRIME Z390-A
- GPU: NVIDIA GeForce RTX 3060, 12 GB VRAM
- Current VRAM at sweep: 12 GB total, about 8.5 GB free
- Notable LAN services seen: SMB `445`, PostgreSQL `5432`, Ollama `11434`
- Practical daily local model tier: 7B/14B quantized
- Practical lab tier: 14B quantized, maybe larger with CPU/RAM spill but not comfortable

## Vault / thevault

- IP: `192.168.1.254`
- OS: Ubuntu 22.04.5 LTS
- CPU: Intel Core i5-4460, 4 cores / 4 threads
- RAM: 7.6 GiB
- Disk: 98 GB root, 68 GB free
- GPU: none detected
- Services active: Nginx, MariaDB, PostgreSQL, SMB, NFS
- LAN services seen: SSH `22`, HTTP `80`, SMB `445`, PostgreSQL `5432`
- Best role: storage, WordPress/local web, database, SMB/NFS, archival memory substrate
- AI role: do not use as primary LLM inference unless upgraded; useful for persistence and serving artifacts

## RBT-1 / rbt1

- IP: `192.168.1.133`
- OS: Ubuntu 22.04.5 LTS
- CPU: Intel Core i5-4460, 4 cores / 4 threads
- RAM: 7.6 GiB
- Disk: 98 GB root, 36 GB free
- Mounted warm storage: `192.168.1.254:/mnt/storage`, 916 GB total, 778 GB free
- GPU: none detected
- Services active: aeteros-worker, aeteros-transcription, aeteros-semantic, Docker
- LAN services seen: SSH `22`, worker health/API `8001`
- Best role: background worker, transcription queue, semantic extraction, indexing, scheduled jobs
- AI role: CPU-only small-model jobs, embeddings, chunking, ingestion, not serious LLM generation

## Old Mac Coordinator

- Handoff mentioned `192.168.1.184`, but this sweep did not confirm it online.
- Treat as unknown/offline until tested manually.

## Security Notes

- Keep Vault local-only unless firewalling is tightened.
- Before public tunnels, rotate reused passwords and move SSH to keys.
- PostgreSQL, SMB, NFS, Ollama, and WordPress should not be exposed publicly.
- Ollama on the workstation is reachable on the LAN at `192.168.1.91:11434`; that is convenient but should stay LAN-only.

## Capacity Read

The current network is not a hidden GPU cluster. It is one good inference box plus two useful service/worker boxes.

The winning architecture is:

1. Workstation RTX 3060 runs main local LLM inference.
2. RBT-1 runs background Aeteros jobs: transcription, semantic extraction, chunking, indexing, watchdogs.
3. Vault stores warm memory, media, WordPress, databases, archives, and shared datasets.
4. Router sends only lightweight jobs to CPU boxes; GPU generation stays on NickPC unless a worker GPU is added.

## Upgrade Direction

Best cheap improvements:

1. Add RAM to RBT-1 and/or Vault if they have spare slots.
2. Add a used 12 GB GPU to RBT-1 if the case/PSU supports it.
3. Upgrade NickPC RAM only if you need bigger CPU-offloaded models or heavy Adobe/browser/Aether multitasking.
4. Avoid Raspberry Pi for LLM inference at current inflated prices.
5. Consider Jetson only for robotics/vision/edge experiments, not as the main Aether LLM box.
