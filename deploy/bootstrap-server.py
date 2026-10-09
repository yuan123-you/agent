from pathlib import Path
import secrets, os, re
base=Path('/srv/aimall')
secret_dir=base/'secrets'
secret_dir.mkdir(mode=0o700,exist_ok=True)
path=secret_dir/'production.env'
if not path.exists():
 values={key:secrets.token_hex(32) for key in ['MYSQL_ROOT_PASSWORD','MYSQL_PASSWORD','REDIS_PASSWORD','JWT_SECRET','INTERNAL_TOKEN','SEED_PASSWORD','MINIO_ROOT_PASSWORD']}
 values['MINIO_ROOT_USER']='aimall-storage'
 path.write_text(''.join(key+'='+value+'\n' for key,value in values.items()))
 os.chmod(path,0o600)
conf=base/'repo/deploy/aimall.nginx.conf'
s=conf.read_text()
existing=Path('/etc/nginx/sites-enabled/glint.novo.ccwu.cc').read_text()
trusted='\n'.join(line for line in existing.splitlines() if 'set_real_ip_from ' in line or 'real_ip_header ' in line)
s=s.replace('    server_tokens off;', '    server_tokens off;\n'+trusted)
conf.write_text(s)
print('Production secrets created without displaying values; trusted proxy ranges configured.')
