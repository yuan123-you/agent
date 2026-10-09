from pathlib import Path
import os
base=Path('/srv/aimall/secrets')
env=dict(line.split('=',1) for line in (base/'production.env').read_text().splitlines() if '=' in line)
p=base/'admin-access.txt'
p.write_text('AI Mall private owner access\nUsername: admin\nPassword: '+env['SEED_PASSWORD']+'\nDomain: https://aimall.novo.ccwu.cc/aimall/login\nDo not share or commit this file.\n')
os.chmod(p,0o600)
print('Owner handoff saved privately; credentials not printed.')
