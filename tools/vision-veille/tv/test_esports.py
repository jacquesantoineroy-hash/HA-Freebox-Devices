import json, ssl, urllib.request, urllib.error, time
d = json.load(open('/homeassistant/.storage/pc_parental'))['data']
pc = [p for p in d['pcs'].values() if 'TCL' in str(p.get('name'))][0]
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def post(chemin, extra):
    corps = dict(id=pc['id'], secret=pc['secret']); corps.update(extra)
    req = urllib.request.Request('https://172.30.32.1:8123' + chemin, data=json.dumps(corps).encode(), headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, context=ctx, timeout=30)
r = json.loads(post('/api/pc_parental/veille', {}).read())
for jeu in r.get('esports', []):
    print(jeu['jeu'])
    for m in jeu['resultats']:
        print('  ', m['e1'], m['s1'], '-', m['s2'], m['e2'], '|', m['serie'], '|', m['evenement'], '|', time.strftime('%d/%m %H:%M', time.localtime(m['ts'])), '|', bool(m['l1']), bool(m['l2']))
    if jeu['resultats']:
        url = jeu['resultats'][0]['l1']
        if url:
            rep = post('/api/pc_parental/veille/logo', {'url': url})
            print('   logo', rep.headers.get('Content-Type'), len(rep.read()), 'octets')
for sp in r.get('courses', []):
    print(sp['sport'])
    for e in sp['epreuves']:
        print('  ', e['manche'], e['nom'], time.strftime('%d/%m', time.localtime(e['ts'])) if e['ts'] else '?', [(p['pos'], p['pilote'], p['equipe'], bool(p['logo'])) for p in e['podium']])
print('esports:', len(r.get('esports', [])), 'jeux ; courses:', len(r.get('courses', [])), 'sports')
