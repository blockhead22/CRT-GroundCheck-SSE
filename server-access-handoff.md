# Server Access Handoff

Private handoff note. Contains live LAN credentials and takeover details. Do not commit or share publicly.

## Current Task Context

Vault is now prepared as a local-only WordPress host and is serving the restored site at:

```text
http://192.168.1.254/
```

WordPress admin:

```text
URL:      http://192.168.1.254/wp-admin/
Username: hostadmin
Password: TempBarAdmin-2026-06-29!
```

The same WordPress credential file is stored on Vault at:

```text
/home/vault/site-archives/wordpress-local-credentials.txt
```

## SSH Access

### Vault / WordPress Host

```text
Host:     192.168.1.254
Hostname: thevault
User:     vault
Password: Nibl158322!
OS:       Ubuntu 22.04.5 LTS
Role:     WordPress local host, MariaDB, Nginx, PHP-FPM, PostgreSQL, NFS, SMB
```

Login:

```powershell
ssh vault@192.168.1.254
```

PuTTY/plink non-interactive pattern:

```powershell
$pw = New-TemporaryFile
Set-Content -LiteralPath $pw.FullName -Value 'Nibl158322!' -NoNewline
plink -batch -ssh -P 22 -l vault -pwfile $pw.FullName 192.168.1.254 "hostname; whoami; uptime"
Remove-Item -LiteralPath $pw.FullName -Force
```

Common paths:

```text
WordPress docroot: /var/www/wordpress-local
Archive staging:   /home/vault/site-archives
Uploaded archive:  /home/vault/site-archives/site-archive-wcgv14673site-live-1776999958-I4wb5FgfI6Y5TtPDlEb5LKbS42Wywbi7Kdui.zip
Pre-restore docroot backup, if present: /home/vault/site-archives/pre-restore-docroot.tar.gz
```

Services to check:

```bash
systemctl status nginx mariadb php8.1-fpm --no-pager
curl -I http://192.168.1.254/
curl -I http://192.168.1.254/wp-login.php
```

WordPress CLI checks:

```bash
sudo -u www-data wp --path=/var/www/wordpress-local core version
sudo -u www-data wp --path=/var/www/wordpress-local user get hostadmin --field=roles
sudo -u www-data wp --path=/var/www/wordpress-local option get home
```

### RBT-1 / Worker Box

```text
Host:     192.168.1.133
Hostname: rbt1
User:     rbt_1
Password: Nibl158322!
OS:       Ubuntu 22.04.5 LTS
Role:     Aeteros worker/transcription/semantic box
```

Login:

```powershell
ssh rbt_1@192.168.1.133
```

Known ED25519 host fingerprint seen by plink:

```text
SHA256:SvIOQCiYZNhBuML4a4bjnrMwNBzzxdqHvVpI8n8qQb4
```

PuTTY/plink non-interactive pattern:

```powershell
$pw = New-TemporaryFile
Set-Content -LiteralPath $pw.FullName -Value 'Nibl158322!' -NoNewline
plink -batch -ssh -P 22 -hostkey 'SHA256:SvIOQCiYZNhBuML4a4bjnrMwNBzzxdqHvVpI8n8qQb4' -l rbt_1 -pwfile $pw.FullName 192.168.1.133 "hostname; whoami; uptime"
Remove-Item -LiteralPath $pw.FullName -Force
```

Checks:

```bash
systemctl status aeteros-worker aeteros-transcription aeteros-semantic docker --no-pager
curl -fsS http://127.0.0.1:8001/health
df -h /mnt/aeteros-warm
```

### Mac Pro / Coordinator

Discovered in the old repo scripts, but not tested in this WordPress handoff.

```text
Host: 192.168.1.184
User: nickblock
Password: Bucks4010!
Role: old Aeteros coordinator/backend/frontend machine
```

## Current WordPress Restore State

Completed:

```text
Installed Nginx, MariaDB, PHP-FPM, PHP extensions, unzip
Restored files into /var/www/wordpress-local
Imported database into MariaDB database wordpress_local
Created database user wp_local
Set WordPress home/siteurl to http://192.168.1.254
Created takeover admin user hostadmin
Disabled object-cache.php and advanced-cache.php by renaming them with .disabled-local
Removed .maintenance file
Verified homepage returns 200 OK
Verified wp-login.php returns 200 OK
Verified /wp-admin/ redirects to login
```

Current local site title seen:

```text
Waukesha County Bar Association ( in Wisconsin)
```

Important follow-up before public/tunnel exposure:

```text
Audit/update old WordPress plugins and theme.
Pay special attention to wp-file-manager, WooCommerce, FooEvents, old WooCommerce extensions, ACF Pro, and custom SBG plugins.
Rotate all reused SSH/sudo/database passwords.
Move to SSH keys.
Firewall PostgreSQL, NFS, and SMB from any public ingress.
Add HTTPS before public access.
```

## Useful Local Windows Tools

Available on the Windows workstation:

```text
plink.exe: C:\Program Files\PuTTY\plink.exe
pscp.exe:  C:\Program Files\PuTTY\pscp.exe
ssh.exe:   C:\Windows\System32\OpenSSH\ssh.exe
```

The original archive on Windows was:

```text
C:\Users\block\Downloads\site-archive-wcgv14673site-live-1776999958-I4wb5FgfI6Y5TtPDlEb5LKbS42Wywbi7Kdui.zip
```

Transferred archive SHA256:

```text
f52057ef58f76baadbcc34476604e25a1e4569a38b20cb92a739e60b1d1a24fc
```
## 2026-06-29 Cloudflare temporary route

- Cloudflare Tunnel client installed on Windows at `C:\Program Files (x86)\cloudflared\cloudflared.exe`.
- Cloudflare tunnel auth completed for this Windows user. Origin cert is at `C:\Users\block\.cloudflared\cert.pem`.
- Named tunnel: `waukeshabar-local`
- Tunnel ID: `73471818-702b-48df-a5af-a627019ad1c5`
- Tunnel config: `C:\Users\block\.cloudflared\config.yml`
- Tunnel DNS route created: `waukeshabar.nickblock.dev` -> `waukeshabar-local`
- Tunnel process was started from Windows and should be checked with `Get-Process cloudflared`. Log files used:
  - `D:\AI_round2\tmp\cloudflared-waukeshabar.log`
  - `D:\AI_round2\tmp\cloudflared-waukeshabar.err.log`
- Public WordPress URL: `https://waukeshabar.nickblock.dev/`
- Public admin URL: `https://waukeshabar.nickblock.dev/wp-admin/`

WordPress changes on Vault:
- `wp-config.php` backup: `/var/www/wordpress-local/wp-config.php.bak-cloudflare-20260629`
- `WP_HOME` and `WP_SITEURL` set to `https://waukeshabar.nickblock.dev`.
- Added forwarded HTTPS handling for Cloudflare Tunnel:
  `HTTP_X_FORWARDED_PROTO=https` sets `$_SERVER['HTTPS']='on'`.
- Original WP Engine must-use plugins moved out of load path:
  `/var/www/wordpress-local/wp-content/mu-plugins.disabled-local-20260629`
- Local must-use shim kept active:
  `/var/www/wordpress-local/wp-content/mu-plugins/local-admin-auth.php`
  This sets the current user from the validated `auth_redirect` user ID so wp-admin menu loading works through the tunnel.
- `user-admin-simplifier` intentionally left inactive so the takeover admin account gets a normal dashboard.

Verification:
- `https://waukeshabar.nickblock.dev/` returns HTTP 200.
- `https://waukeshabar.nickblock.dev/wp-login.php` returns HTTP 200.
- `hostadmin` authenticated through `https://waukeshabar.nickblock.dev/wp-admin/` and reached Dashboard with HTTP 200.
- 2026-06-29 reset `hostadmin` password to `TempBarAdmin-2026-06-29!` because the earlier special-character password was easy to mistype/copy incorrectly.

Nickblock route prep:
- Local repo: `D:\AI_round2\tmp\nickblock.dev`
- Added React redirect route in `src/app.jsx` for `/waukeshabar` and `/waukeshabar/*`.
- Added Cloudflare Pages redirects in `public/_redirects`:
  `/waukeshabar` and `/waukeshabar/*` redirect to `https://waukeshabar.nickblock.dev/`.
- `npm run build` passes and copies `_redirects` into `dist`.
- Wrangler login was attempted with global Wrangler 3.99.0 and `npx wrangler@latest` 4.105.0, but both timed out waiting for browser OAuth. The `/waukeshabar` route is prepared locally but is not live on `nickblock.dev` until deployed/pushed.
