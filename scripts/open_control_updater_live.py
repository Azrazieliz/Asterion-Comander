"""Navigate real Samsung launcher to Control's existing signed updater.
Does not install an APK or bypass Android confirmation dialogs.
"""
import json,os,time,urllib.request,urllib.parse,ipaddress
from pathlib import Path
paired=json.loads((Path(os.getenv('ASTERION_CONTROL_STATE',str(Path.home()/'.asterion-control')))/'phone-pairing.json').read_text('utf-8'))
base=paired['base_url'].rstrip('/')
p=urllib.parse.urlparse(base);ip=ipaddress.ip_address(p.hostname or '')
if p.scheme!='http' or not (ip.is_private or ip in ipaddress.ip_network('100.64.0.0/10')):raise ValueError('Private paired phone only')
def call(path,body=None):
    payload=None if body is None else json.dumps(body).encode()
    headers={'Authorization':'Bearer '+paired['token'],'Accept':'application/json'}
    if payload is not None:headers['Content-Type']='application/json'
    req=urllib.request.Request(base+path,data=payload,headers=headers,method='POST' if body is not None else 'GET')
    with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
def input(**kw):
    r=call('/input',kw)
    if not r.get('ok'):raise RuntimeError('input failed '+str(kw))
    time.sleep(.38)
def dump():
    d=call('/ui')
    a=[]
    def walk(n):
        if not isinstance(n,dict):return
        if n.get('text') or n.get('description'):a.append(n.get('text') or n.get('description'))
        for c in n.get('children',[]):walk(c)
    walk(d.get('root',{}))
    return d.get('foreground_package',''),a
pkg,labels=dump()
print('START_FOREGROUND',pkg)
if pkg!='com.asterion.control':
    input(action='home')
    input(action='swipe',x=530,y=1860,x2=530,y2=700,duration_ms=300)
    input(action='tap',x=440,y=2115)
    input(action='type',text='Asterion Control')
    pkg,labels=dump()
    print('SEARCH_RESULTS',labels[:18])
    if 'Asterion Control' not in labels:raise RuntimeError('Control app not found in launcher')
    input(action='click_text',text='Asterion Control')
    pkg,labels=dump()
    if pkg!='com.asterion.control':raise RuntimeError('Control was not foreground after launcher')
if 'Check for updates' not in labels:
    input(action='click_text',text='Connect')
    input(action='swipe',x=600,y=1830,x2=600,y2=780,duration_ms=350)
    pkg,labels=dump()
if pkg!='com.asterion.control':raise RuntimeError('Control not foreground')
if 'Check for updates' not in labels:raise RuntimeError('Updater not in Control accessibility hierarchy')
input(action='click_text',text='Check for updates')
pkg,labels=dump()
print('UPDATER_FOREGROUND',pkg)
print('UPDATE_UI',json.dumps(labels[-36:],ensure_ascii=False))
