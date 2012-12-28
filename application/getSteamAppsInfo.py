import urllib2
import json

API_KEY = ""
url = "http://api.steampowered.com/ISteamApps/GetAppList/v0002/?key={}".format(API_KEY)

data = json.loads(urllib2.urlopen(url).read())["applist"]["apps"]

appDict = {}
for app in data:
    appInfo = {}
    appInfo["name"] = app["name"]

    url = "http://store.steampowered.com/app/{}".format(app["appid"])
    appInfo["url"] = url

    # Scrape info from url

    appDict[app["appid"]] = appInfo

f = open("SteamAppList.json", "w")
f.write(json.dumps(appDict))
f.close()
