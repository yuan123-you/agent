from pathlib import Path
import subprocess, shutil, datetime
repo=Path('/srv/aimall/repo/deploy')
backup=Path('/srv/aimall/backups')/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
backup.mkdir(parents=True, mode=0o700, exist_ok=True)
site=Path('/etc/nginx/sites-available/aimall.novo.ccwu.cc')
ip=Path('/etc/nginx/sites-available/oracle-ip-access')
shutil.copy2(site,backup/'aimall.novo.ccwu.cc')
shutil.copy2(ip,backup/'oracle-ip-access')
conf=(repo/'aimall.nginx.conf').read_text()
existing=Path('/etc/nginx/sites-enabled/glint.novo.ccwu.cc').read_text()
trusted='\n'.join(line for line in existing.splitlines() if 'set_real_ip_from ' in line or 'real_ip_header ' in line)
site.write_text(conf.replace('    server_tokens off;', '    server_tokens off;\n'+trusted))
for filename in ['aimall-proxy.conf','aimall-subpath-proxy.conf','aimall-forward-headers.conf']:
 shutil.copy2(repo/filename,Path('/etc/nginx/snippets')/filename)
shutil.copy2(repo/'ip-access.locations.conf',Path('/etc/nginx/snippets/aimall-ip-access.locations.conf'))
s=ip.read_text()
include='    include /etc/nginx/snippets/aimall-ip-access.locations.conf;\n'
if include not in s:
 assert '    root /opt/online-exam/dist;' in s
 s=s.replace('    root /opt/online-exam/dist;',include+'    root /opt/online-exam/dist;')
 ip.write_text(s)
result=subprocess.run(['nginx','-t'])
if result.returncode:
 shutil.copy2(backup/'aimall.novo.ccwu.cc',site)
 shutil.copy2(backup/'oracle-ip-access',ip)
 raise SystemExit(result.returncode)
subprocess.run(['systemctl','reload','nginx'],check=True)
hook=Path('/etc/letsencrypt/renewal-hooks/deploy/aimall-reload-nginx')
hook.write_text('#!/bin/sh\nset -eu\nif [ "${RENEWED_LINEAGE:-}" = "/etc/letsencrypt/live/aimall.novo.ccwu.cc" ]; then nginx -t && systemctl reload nginx; fi\n')
hook.chmod(0o755)
print('Nginx installed with rollback copies, IP entry points disabled and certificate renewal reload hook.')
