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
#web.config.debug = False

path = os.path.abspath(__file__)
path = os.path.dirname(path)

urls = (
        "/img/(.*)", 'images',
        "/css/(.*)", 'css',
        "/wishlist", 'wishlist',
        "/(.+)", 'static',
        "/", 'index')
render = web.template.render(path + '/templates/')
api_key = ""

app = web.application(urls, globals())

class WebAPI:
    """Simple interface for Valve's WebAPI, containing only methods we are
       using, and returning only the data we're interested in."""

    def __init__(self, api_key=api_key):
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

    def GetPlayerSummary(self, id64):
        # Helper function of the above; returning only 1 user, erroring when more are inputted.
        interface = "ISteamUser"
        method = "GetPlayerSummaries"
        version = "v0002"

        if len(id64.split(",")) > 1 or type(id64) == list:
            raise Exception("We only want one player ID, you horrible person.")

        args = "?key={}&steamids={}".format(self.api_key, str(id64))
        url = self.apiUrl.format(interface = interface, method = method, version = version, args = args)

        data = json.loads(urllib2.urlopen(url).read())["response"]["players"]
        return data[0]

    def GetFriendList(self, id64):
        interface = "ISteamUser"
        method = "GetFriendList"
        version = "v0001"

        args = "?key={}&steamid={}".format(self.api_key, str(id64))
        url = self.apiUrl.format(interface = interface, method = method, version = version, args = args)

        data = json.loads(urllib2.urlopen(url).read())["friendslist"]["friends"]
        return data

    def GetWishlist(self, id64):
        """Custom method to scrape id64's wishlist, and return a list of appids."""
        wishlist = []
        url = "http://steamcommunity.com/profiles/{}/wishlist".format(id64)
        data = urllib2.urlopen(url).read()
        for match in re.compile('<div\sclass="wishlistRow\s"\sid="game_([0-9]+)">').findall(data):
            wishlist.append(match)
        return wishlist

w = WebAPI()


friendInfo = {}

queue = Queue.Queue()
class ThreadedGetWishlist(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while True:
            data = self.queue.get()
            data["wishlist"] = w.GetWishlist(data["steamid"])
            id = data["id"]
            friendInfo[id]["data"].append(str(render.wishlistWidget(data)))
            friendInfo[id]["progress"] += 1
            self.queue.task_done()

for i in range(10):
    t = ThreadedGetWishlist(queue)
    t.setDaemon(True)
    t.start()

def GetAccountInfo(account, id):
    id = str(id)
    friends = w.GetFriendList(account)
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


    for data in dataOnFriends:
        data["id"] = id
        queue.put(data)

    queue.join()
    friendInfo[id]["done"] = True


class index:
    def GET(self):
        return render.index()


class wishlist:
    def GET(self):
        # Display friends wishlists in some useful manner.
        account = str(web.input().account)
        if not (str.isdigit(account) and len(account) == 17):
            # We have a vanity url.  Fixfixfix.
            account = w.ResolveVanityUrl(account)

        accountInfo = w.GetPlayerSummary(account)
        userWidget = render.userWidget(accountInfo)
        threadid = str(int(time.mktime(time.gmtime())))
        threading.Thread(target=GetAccountInfo, args=[account, threadid]).start()
        return render.wishlist(userWidget, threadid)

    def POST(self):
        id = str(web.data())
        try:
            if friendInfo[id]["done"] == False:
                ret = {}
                ret["success"] = False
                ret["count"] = friendInfo[id]["size"]
                ret["doneCount"] = friendInfo[id]["progress"]
                ret["progress"] =  (friendInfo[id]["progress"] / friendInfo[id]["size"]) * 100
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
        if name in os.listdir(path + '/images'):
            return open(path + '/images/{}'.format(name), "rb").read()
        else:
            raise web.notfound()


class css:
    def GET(self, name):
        if name in os.listdir(path + '/css'):
            return open(path + '/css/{}'.format(name), "rb").read()
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