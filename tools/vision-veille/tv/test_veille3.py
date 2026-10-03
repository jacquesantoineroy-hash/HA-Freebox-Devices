import json, ssl, urllib.request, urllib.error, time
d = json.load(open('/homeassistant/.storage/pc_parental'))['data']
pc = [p for p in d['pcs'].values() if 'TCL' in str(p.get('name'))][0]
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def post(chemin, extra):
    corps = dict(id=pc['id'], secret=pc['secret']); corps.update(extra)
    req = urllib.request.Request('https://172.30.32.1:8123' + chemin, data=json.dumps(corps).encode(), headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, context=ctx, timeout=30)
t0 = time.time()
r = json.loads(post('/api/pc_parental/veille', {}).read())
print('veille en', round(time.time() - t0, 2), 's')
print('reglages', r.get('reglages', {}).get('theme'), r.get('reglages', {}).get('nuit'), len(r.get('reglages', {}).get('radios', [])), 'radios')
for e in r.get('ecole', []):
    print('ecole', e['prenom'], e['jour'], e['debut'], e['fin'], len(e['cours']), 'cours', len(e['devoirs']), 'devoirs', e['controles'])
print('agenda', [(a['heure'], a['titre'], a['calendrier']) for a in r.get('agenda', [])][:5])
print('pluie', (r.get('pluie') or {}).get('pluie'), (r.get('pluie') or {}).get('dans'))
print('demandes', r.get('demandes'))
ch = r.get('chauffage') or {}
print('chauffage', {k: ch.get(k) for k in ('consigne', 'dedans', 'dehors', 'bruleur', 'mois', 'saison')}, len(ch.get('jours', [])), 'jours')
print('photos', len(r.get('photos', [])))
for a in r.get('avenir', []):
    print('avenir', a['sport'], a['titre'], time.strftime('%d/%m %H:%M', time.localtime(a['ts'])), bool(a['l1']))
