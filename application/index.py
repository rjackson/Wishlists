import json
import math
import os
import re
import urllib2
import web
import threading
import time
import webbrowser
import json
import Queue
import uwsgi

#web.config.debug = False

path = os.path.abspath(__file__)
path = os.path.dirname(path)

urls = (
        "/img/(.*)", 'images',
        "/css/(.*)", 'css',
        "/js/(.*)", 'js',
        "/wishlist", 'wishlist',
        "/(.+)", 'static',
        "/", 'index')
render = web.template.render(path + '/templates/')
API_KEY = ""
THREAD_COUNT = 10
PER_USER_THREAD_COUNT = 100
appListFile = "SteamAppList.json"

app = web.application(urls, globals())

class WebAPI:
    """Simple interface for Valve's WebAPI, containing only methods we are
       using, and returning only the data we're interested in."""


    def __init__(self, api_key):
        self.api_key = api_key
        self.apiUrl = "http://api.steampowered.com/{interface}/{method}/{version}/{args}"

    def ResolveVanityUrl(self, vanity):
        interface = "ISteamUser"
        method = "ResolveVanityUrl"
        version = "v0001"

        args = "?key={}&vanityurl={}".format(self.api_key, str(vanity))
        url = self.apiUrl.format(interface = interface, method = method, version = version, args = args)

        data = json.loads(urllib2.urlopen(url).read())["response"]

        if data["success"]:
            return data["steamid"]
        else:
            return False

    def GetPlayerSummaries(self, id64s):
        interface = "ISteamUser"
        method = "GetPlayerSummaries"
        version = "v0002"
        if type(id64s) == list:
            id64s = ','.join(str(x) for x in id64s)
        args = "?key={}&steamids={}".format(self.api_key, str(id64s))
        url = self.apiUrl.format(interface = interface, method = method, version = version, args = args)

        data = json.loads(urllib2.urlopen(url).read())["response"]["players"]
        return data

    def GetFriendList(self, id64):
        interface = "ISteamUser"
        method = "GetFriendList"
        version = "v0001"

        args = "?key={}&steamid={}".format(self.api_key, str(id64))
        url = self.apiUrl.format(interface = interface, method = method, version = version, args = args)

        data = json.loads(urllib2.urlopen(url).read())["friendslist"]["friends"]
        return data

w = WebAPI(API_KEY)


def hack_cache(path, url, timeout = (10 * 60)):
    """Simple disk-based caching.  If a file does not exist, or
    it was last modified a time longer than timeout -> recreate it with new data."""
    if os.path.exists(path):
        if not (os.path.getmtime(path) < (time.time() - timeout)):
            return None
    f = open(path, "w")
    f.write(urllib2.urlopen(url).read())
    f.close()


def GetWishlist(id64):
    """Custom method to scrape id64's wishlist, and return a list of appids."""
    wishlist = []
    url = "http://steamcommunity.com/profiles/{}/wishlist".format(id64)

    file_str = path + "/cache_hack/wishlist_{}.txt".format(id64)
    hack_cache(file_str, url, timeout = 60 * 60)  # 1 hour timeout

    data = open(file_str, "r").read()
    for match in re.compile('<div\sclass="wishlistRow\s"\sid="game_([0-9]+)">').findall(data):
        wishlist.append(match)

    return wishlist


gameDefinitions = {"data": json.loads(open(path + os.sep + appListFile, "r").read()),
            "lastOpened": time.mktime(time.gmtime()),
            "timeout": 60 * 60}
def GetGameDefinition(appid):
    global gameDefinitions
    if (gameDefinitions["lastOpened"] < (time.time() - gameDefinitions["timeout"])):
        gameDefinitions["data"] = json.loads(open(path + os.sep + appListFile, "r").read())
        gameDefinitions["lastOpened"] = time.mktime(time.gmtime())

    appid = str(appid)
    if gameDefinitions["data"].get(appid, None) == None:
        return {"name": "Definition not found ({})".format(appid), "url": "http://store.steampowered.com/app/{}".format(appid)}
    else:
        return gameDefinitions["data"][appid]


friendInfo = {}
class ThreadedGetWishlist(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            data = self.queue.get()
            data["wishlist"] = GetWishlist(data["steamid"])

            for i in range(len(data["wishlist"])):
                item = data["wishlist"][i]
                data["wishlist"][i] = str(render.gameTile(GetGameDefinition(item)))

            id = data["id"]
            friendInfo[id]["data"].append(str(render.wishlistWidget(data)))
            friendInfo[id]["progress"] += 1
            self.queue.task_done()


getAccountQueue = Queue.Queue()
class ThreadedGetAccountInfo(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            data = self.queue.get()
            id = str(data["id"])
            friends = w.GetFriendList(data["account"])
            if (friendInfo.get(id, None) == None):
                friendInfo[id] = {}
            friendInfo[id]["progress"] = 0.0
            friendInfo[id]["done"] = False
            friendInfo[id]["size"] = len(friends)
            friendInfo[id]["data"] = []

            dataOnFriends = []
            if len(friends) <= 100:
                dataOnFriends.extend(w.GetPlayerSummaries([x["steamid"] for x in friends]))
            else:
                steamidList = [x["steamid"] for x in friends]
                friendCount = len(friends)
                requiredIterations = math.ceil(float(friendCount) / 100)
                print requiredIterations
                i = 0
                while i < requiredIterations:
                    min = i * 100
                    max = min + 100
                    if len(steamidList[min:]) < max:
                        max = min + len(steamidList[min:])
                    trimmedList = steamidList[min:max]
                    dataOnFriends.extend(w.GetPlayerSummaries(trimmedList))
                    i += 1

            getWishlistQueue = Queue.Queue()
            if len(dataOnFriends) < PER_USER_THREAD_COUNT:
                workersNeeded = len(dataOnFriends)
            else:
                workersNeeded = PER_USER_THREAD_COUNT

            for i in range(workersNeeded):
                t = ThreadedGetWishlist(getWishlistQueue)
                t.setDaemon(True)
                t.start()

            for data in dataOnFriends:
                data["id"] = id
                getWishlistQueue.put(data)

            getWishlistQueue.join()
            friendInfo[id]["done"] = True


def spawnAccountInfoWorkers():
    for i in range(THREAD_COUNT):
        t = ThreadedGetAccountInfo(getAccountQueue)
        t.setDaemon(True)
        t.start()

# To test with the Webpy's inbuilt httpserver uncomment this line:
# spawnAccountInfoWorkers()

# and comment out this line, and the "import uwsgi" line above:
uwsgi.post_fork_hook = spawnAccountInfoWorkers


class index:
    def GET(self):
        return render.index()


class wishlist:
    def GET(self):
        account = str(web.input().account)
        if not (str.isdigit(account) and len(account) == 17):
            # We have a vanity url.  Fixfixfix.
            account = w.ResolveVanityUrl(account)

        accountInfo = w.GetPlayerSummaries(account)[0]
        userWidget = render.userWidget(accountInfo)
        threadid = str(int(time.mktime(time.gmtime())))
        args = {"account": account, "id": threadid}
        getAccountQueue.put(args)
        return render.wishlist(userWidget, threadid)

    def POST(self):
        #web.header("Content-Type", "application/json")
        id = str(web.input().id)
        try:
            if friendInfo[id]["done"] == False:
                ret = {}
                ret["success"] = False
                ret["count"] = friendInfo[id]["size"]
                ret["doneCount"] = friendInfo[id]["progress"]
                ret["progress"] = (friendInfo[id]["progress"] / friendInfo[id]["size"]) * 100
                return json.dumps(ret)
            else:
                ret = {}
                ret["success"] = True
                ret["data"] = friendInfo[id]["data"]
                return json.dumps(ret)
        except KeyError:
            ret = {}
            ret["success"] = False
            ret["error"] = "ID Not Found"
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

if __name__ == "__main__":
    app = web.application(urls, globals())
    app.run()

application = app.wsgifunc()
