import time
import json

import urllib.request
import urllib.parse
import http.cookiejar
import ssl

BASE = 'http://127.0.0.1:3000'

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(path):
    r = opener.open(BASE + path)
    return r

def post(path, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=body, headers={'Content-Type':'application/json'})
    r = opener.open(req)
    return r

print('GET /')
r = get('/')
print('status', r.getcode())

print('POST /login')
try:
    r = post('/login', {'username':'admin','password':'1234'})
    print('status', r.getcode())
    print('cookies', [c.name+'='+c.value for c in cj])
    print('body', r.read().decode())
except Exception as e:
    print('login error', e)

print('GET /me')
try:
    r = get('/me')
    print('status', r.getcode())
    print('body', r.read().decode())
except Exception as e:
    print('me error', e)

print('GET /admin/users')
try:
    r = get('/admin/users')
    print('status', r.getcode())
    print('body', r.read().decode())
except Exception as e:
    print('admin/users error', e)
