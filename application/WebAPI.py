import json
import urllib2


class WebAPI:
    """Simple interface for Valve's WebAPI, containing only methods we are
       using, and returning only the data we're interested in."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.apiUrl = "http://api.steampowered.com/{interface}/{method}/{version}/{args}"

    def formatUrl(self, interface, method, version, args):
        return

    def request(self, interface, method, version, args):
        url = self.apiUrl.format(interface = interface,
                                  method = method,
                                  version = version,
                                  args = args)
        return json.loads(urllib2.urlopen(url).read())


    def ResolveVanityUrl(self, vanity):
        interface = "ISteamUser"
        method = "ResolveVanityUrl"
        version = "v0001"

        args = "?key={}&vanityurl={}".format(self.api_key, str(vanity))

        data = self.request(interface, method, version, args)["response"]

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

        data = self.request(interface, method, version, args)["response"]["players"]
        return data

    def GetFriendList(self, id64):
        interface = "ISteamUser"
        method = "GetFriendList"
        version = "v0001"

        args = "?key={}&steamid={}".format(self.api_key, str(id64))
        try:
            data = self.request(interface, method, version, args)["friendslist"]["friends"]
        except urllib2.HTTPError:
            data = []   # Hack while WebAPI permissions bug exists
        return data

    def GetAppList(self):
        interface = "ISteamApps"
        method = "GetAppList"
        version = "v0002"

        args = "?key={}".format(self.api_key)

        data = self.request(interface, method, version, args)["applist"]["apps"]
        return data
