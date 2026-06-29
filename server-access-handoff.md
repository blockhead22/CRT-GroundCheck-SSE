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
Password: &#8%AJ71Ejp-Ix9*CHYKOL+$
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
