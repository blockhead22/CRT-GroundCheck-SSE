# Aeteros Docs Deployment Check

Last checked: 2026-06-27

## Current Site Shape

The public docs site is a static Cloudflare Pages-style folder:

```text
D:\AI_round2\docs
```

There is no checked-in `wrangler.toml`.

There are currently no Pages support files in the deploy folder:

```text
docs\_worker.js     not found
docs\_headers       not found
docs\_redirects     not found
```

An older changelog entry says the site was live at:

```text
aeteros-research.pages.dev
```

That likely means the Pages project name is:

```text
aeteros-research
```

## CLI Status

Wrangler is installed and runnable:

```text
wrangler 3.99.0
```

Wrangler reported that a newer major version exists, but the installed version can still run basic commands.

Cloudflare auth is not currently available in this non-interactive environment:

```text
CLOUDFLARE_API_TOKEN is not set
wrangler whoami -> Not logged in
wrangler pages project list -> requires CLOUDFLARE_API_TOKEN
```

## Local Static Check

The edited pages served successfully from a temporary local static server:

```text
http://127.0.0.1:8787/index.html       200
http://127.0.0.1:8787/start-here.html  200
http://127.0.0.1:8787/home.html        200
```

Basic local link check passed for:

```text
index.html
start-here.html
home.html
```

JavaScript syntax check passed:

```text
node --check docs\docs.js
```

## Deploy Command Once Auth Exists

From the docs folder:

```powershell
cd D:\AI_round2\docs
npx wrangler pages deploy . --project-name aeteros-research --branch main --commit-dirty=true
```

If Cloudflare project visibility fails, first verify the project name:

```powershell
cd D:\AI_round2\docs
npx wrangler pages project list
```

## Blocker

Deployment cannot be verified or performed from this environment until either:

- `wrangler login` is completed interactively, or
- a scoped `CLOUDFLARE_API_TOKEN` is available in the environment.

