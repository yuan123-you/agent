import urllib.request, urllib.error, json, secrets, time, subprocess
from pathlib import Path

DOMAIN='https://aimall.novo.ccwu.cc'
# Functional checks use the private loopback proxy, not a public IP entry.
BASE='http://127.0.0.1:18100/api/v1'

def call(path, data=None, token=None, base=BASE):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    request=urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=60) as response:
            return response.status,json.loads(response.read())
    except urllib.error.HTTPError as error:
        content=error.read()
        return error.code,json.loads(content) if content.startswith(b'{') else {}

# Cloudflare rejects the default Python User-Agent; curl is used for public domain checks.
html=subprocess.check_output(['curl','-fsS','--max-time','30',DOMAIN+'/aimall/']).decode()
assert '/aimall/assets/' in html
body=json.loads(subprocess.check_output(['curl','-fsS','--max-time','30',DOMAIN+'/aimall/api/v1/products?page=1&size=2']))
assert body['code']==0 and len(body['data']['records'])==2
print('PASS HTTPS domain frontend + products:',DOMAIN,'total=',body['data']['total'])
for path in ['/aimall/internal/users','/aimall/actuator/health']:
    status=subprocess.check_output(['curl','-sS','--max-time','15','-o','/dev/null','-w','%{http_code}',DOMAIN+path]).decode()
    assert status=='404'
print('PASS domain internal endpoints blocked')

status,body=call('/admin/dashboard')
assert status==401
print('PASS anonymous administrator access denied')
status,body=call('/auth/login',{'username':'admin','password':'123456'})
assert body.get('code')!=0
print('PASS default administrator password rejected')
username='deploycheck_'+str(int(time.time()))
password=secrets.token_urlsafe(20)
status,body=call('/auth/register/customer',{'username':username,'password':password,'nickname':'Deployment check','role':'ADMIN'})
assert status==200 and body['code']==0 and body['data']['user']['role']=='CUSTOMER'
status,body=call('/auth/login',{'username':username,'password':password})
assert status==200 and body['code']==0
token=body['data']['accessToken']
status,body=call('/auth/me',token=token)
assert body['data']['role']=='CUSTOMER'
status,body=call('/admin/dashboard',token=token)
assert status==403
print('PASS buyer registration/login + role escalation/admin access rejected')
env=dict(line.split('=',1) for line in Path('/srv/aimall/secrets/production.env').read_text().splitlines() if '=' in line)
status,body=call('/auth/login',{'username':'admin','password':env['SEED_PASSWORD']})
assert body['code']==0 and body['data']['user']['role']=='ADMIN'
admin=body['data']['accessToken']
status,body=call('/admin/dashboard',token=admin)
assert status==200 and body['code']==0
print('PASS private administrator login/dashboard')
status,body=call('/chat/conversations',{},token)
assert status==200 and body['code']==0
conversation=body['data']['conversationId']
payload={'conversationId':conversation,'content':'你好，帮我用一句话解释什么是性价比。','webSearchEnabled':False}
request=urllib.request.Request(BASE+'/chat/messages',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'Accept':'text/event-stream'})
start=time.time()
with urllib.request.urlopen(request,timeout=240) as response:
    stream=response.read().decode()
    Path('/srv/aimall/smoke-ai-stream.txt').write_text(stream)
    assert response.status==200 and 'event:done' in stream.replace('event: ', 'event:')
    assert 'event:error' not in stream.replace('event: ', 'event:')
    assert '本次查询耗时较长' not in stream
    assert 'token' in stream
print('PASS AI SSE completed in',round(time.time()-start,1),'seconds; response saved (no credentials)')
print('Smoke username:',username)
