import json
import math
import os
import re
import urllib2
import web
import time
# import uwsgi
import gevent
# from gevent.pywsgi import WSGIServer
import wishlist as backend
backend = backend.Wishlist()
from gevent import monkey
monkey.patch_all()

#web.config.debug = False

path = os.path.dirname(os.path.abspath(__file__))

urls = (
        "/img/(.*)", 'images',
        "/css/(.*)", 'css',
        "/js/(.*)", 'js',
        "/wishlist", 'wishlist',
        "/api/(.+)/(.+)", 'api',
        "/(.+)", 'static',
        "/", 'index')
render = web.template.render(path + '/templates/')


class index:
    def GET(self):
        return render.index()


class wishlist:
    def GET(self):
        accountId = str(web.input().account)
        backend.updateAccount(accountId)

        account = backend.getAccount(accountId)

        [gevent.spawn(backend.updateAccount, friend)
            for friend in account.friends[:10]]

        return render.wishlist(account)


class api:
    def POST(self, interface, method):
        web.header("Content-Type", "application/json")
        data = web.input()
        ret = {}
        if interface == "Accounts":
            if method == "GetAccount":
                if data.get("accounts", None) != None:
                    ret["accounts"] = {}
                    accounts = [backend.getAccount(data.accounts.strip(","))]

                    for account in accounts:
                        accountDict = {}
                        accountDict["id64"] = account.id64
                        accountDict["name"] = account.name
                        accountDict["avatarUrl"] = account.avatarUrl
                        accountDict["url"] = account.url
                        accountDict["wishlist"] = account.wishlist
                        accountDict["friends"] = account.friends
                        ret["accounts"][account.id64] = accountDict
                else:
                    ret["error"] = "Error: Required parameter, accounts, not \
                    provided."
                return json.dumps(ret)

        elif interface == "Apps":
            if method == "GetApp":
                if data.get("apps", None) != None:
                    ret["apps"] = {}
                    apps = [backend.getApp(data.apps.strip(","))]

                    for app in apps:
                        appDict = {}
                        appDict["appid"] = app.appid
                        appDict["name"] = app.name
                        appDict["imageUrl"] = app.imageUrl
                        appDict["url"] = app.url
                        ret["apps"][app.appid] = appDict
                else:
                    ret["error"] = "Error: Required parameter, apps, not \
                    provided."
                return json.dumps(ret)



class images:
    def GET(self, name):
        ext = name.split(".")[-1]

        cType = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "gif": "image/gif",
            "ico": "image/x-icon"
            }

        if name in os.listdir(path + '/images'):
            web.header("Content-Type", cType[ext])
            return open(path + '/images/{}'.format(name), "rb").read()
        else:
            raise web.notfound()


class css:
    def GET(self, name):
        if name in os.listdir(path + '/css'):
            web.header("Content-Type", "text/css")
            return open(path + '/css/{}'.format(name), "r").read()
        else:
            raise web.notfound()


class js:
    def GET(self, name):
        if name in os.listdir(path + '/js'):
            web.header("Content-Type", "application/js")
            return open(path + '/js/{}'.format(name), "r").read()
        else:
            raise web.notfound()


class static:
    def GET(self, name):
        if name in os.listdir(path + os.sep + 'static'):
            return open(path + os.sep + 'static' + os.sep + '{}'.format(name), "rb").read()
        else:
            raise web.notfound()



app = web.application(urls, globals())
if __name__ == "__main__":
    app.run()

application = app.wsgifunc()
