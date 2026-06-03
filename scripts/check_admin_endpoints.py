import urllib.request, urllib.parse, http.cookiejar
BASE='http://127.0.0.1:3000'
cj=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# login first
req = urllib.request.Request(BASE + '/login', data=b'{"username":"admin","password":"1234"}', headers={'Content-Type':'application/json'})
try:
    r = opener.open(req)
    print('/login', r.getcode(), r.read().decode())
except Exception as e:
    print('login error', e)

for path in ['/admin/stats','/admin/logs']:
    try:
        r = opener.open(BASE + path)
        print(path, r.getcode(), r.read().decode())
    except Exception as e:
        print(path, 'error', e)
