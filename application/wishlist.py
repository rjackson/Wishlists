from datetime import datetime, timedelta
import urllib
import urllib2
import cookielib
import json
import re
import gevent
import time

from WebAPI import WebAPI
apiKey = ""
webAPI = WebAPI(apiKey)


class ItemNotReady(Exception):
    def __init__(self, expr, msg):
        self.expr = expr
        self.msg = msg


class Account:
    """Class representing a Steam user account."""
    _PRIVATE = 1
    _FRIENDS_ONLY = 2
    _VISIBLE = 3

    def __init__(self, id64):
        self.id64 = id64

        # Info to fetch on update:
        self.name = ""
        self.avatarUrl = ""
        self.wishlist = []  # Collection of appids
        self.friends = []  # Collection of id64s
        self.visible = False
        self.lastUpdated = None

        # Helpers
        self.url = "http://steamcommunity.com/profiles/{}".format(
            self.id64)
        self.visible = False

        self.update()

    def update(self):
        playerData = webAPI.GetPlayerSummaries(self.id64)[0]

        self.name = playerData["personaname"]
        self.avatarUrl = playerData["avatarfull"]
        self.wishlist = [str(item) for item in self.getWishlist()]

        self.visibility = playerData["communityvisibilitystate"]
        if self.visibility == Account._VISIBLE:
            self.visible = True
            self.friends = [str(friend["steamid"])
                for friend in webAPI.GetFriendList(self.id64)]
        else:
            self.visible = False

        self.lastUpdated = datetime.now()

    def getWishlist(self):
        wishlist = []
        url = "{}/wishlist".format(self.url)
        data = urllib2.urlopen(url).read()
        for match in re.compile(
            '<div\sclass="wishlistRow\s"\sid="game_([0-9]+)">').findall(data):
            wishlist.append(match)
        return wishlist


class App:
    """Class representing a Steam app"""
    _RETRY_ATTEMPTS = 2
    def __init__(self, appid):
        self.appid = appid

        # Info to fetch on update
        self.name = ""
        self.imageUrl = ""
        self.lastUpdated = None

        # Helpers
        self.url = "http://store.steampowered.com/app/{}".format(self.appid)

        self.update()

    def update(self, attempts=0):
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
        data = opener.open(self.url).read()
        if "<div id=\"agegate_box\">" in data:
            postUrl = re.compile(
                "<form\saction=\"(.+)\"\smethod=\"post\"\sstyle=\"margin:0;padding:0;\">"
                ).findall(data)[0]
            data = opener.open(postUrl, urllib.urlencode({
                "snr": "1_agecheck_agecheck__age-gate",
                "ageDay": "1",
                "ageMonth": "January",
                "ageYear": "1970"
                })).read()
        try:
            self.name = re.compile(
                "<div\sclass=\"apphub_AppName\">(.+)</div>").findall(data)[0]
            self.imageUrl = re.compile(
                "<img\sclass=\"game_header_image\"\ssrc=\"(.*)\">"
                ).findall(data)[0]
        except IndexError:
            if attempts < App._RETRY_ATTEMPTS:
                attempts += 1
                self.update(attempts)
            else:
                self.name = "App {} not found".format(self.appid)
                self.imageUrl = "/img/unknown_app.png"

        self.lastUpdated = datetime.now()


class Wishlist:
    """Back end for Steam Wishlist.  Stores apps and accounts, maintains them,
    and has functions for front-end to retrieve them."""

    def __init__(self):
        self.apps = {}
        self.accounts = {}
        self.appExpiry = timedelta(
            seconds=(24 * 60 * 60))  # 24 hours
        self.accountExpiry = timedelta(
            seconds=(.5 * 60 * 60))  # 30 mins

    # Base methods

    def _updateItem(self, _class, _dict, expiry, id):
        """Checks items in _dict for id.  If id is not in _dict, it is created
        and added; if id is in _dict, but has expired - it is updated.

        Base method for updateApp and updateAccount"""
        id = str(id)
        if _dict.get(id, None) != None:
            if _dict[id].lastUpdated == None:
                raise ItemNotReady
            expireTime = _dict[id].lastUpdated + expiry
            if datetime.now() > expireTime:
                _dict[id].update()
        else:
            _dict[id] = _class(id)

    def _getItem(self, _dict, id, ignoremissing=False):
        """Takes a single, or list of, ids(s). Returns the relevant entries
        from _dict.  Raises ItemNotReady if item is missing and ignoremissing
        is false (default)"""
        if type(id) == list:
            ret = []
            if len([item for item in id
                if item not in _dict]) > 0:
                if ignoremissing:
                    id = [item for item in id
                        if item in _dict]
                else:
                    raise ItemNotReady
            for id in id:
                ret.append(_dict[id])
        else:
            id = str(id)
            ret = None
            if id not in _dict:
                if ignoremissing:
                    pass
            else:
                ret = _dict[id]
        return ret

    # Account methods

    def _validateAccountId(self, id64):
        """Takes an id64, checks whether it is an id64 or a vanity url; if it
        is a vanity url it is resolved into an id64.  id64 is then returned."""

        id64 = str(id64)
        if not (str.isdigit(id64) and len(id64) == 17):
            id64 = webAPI.ResolveVanityUrl(id64)
        return id64

    def updateAccount(self, id64):
        """Runs _updateItem for an account"""

        id64 = self._validateAccountId(id64)
        self._updateItem(Account, self.accounts,
                                  self.accountExpiry, id64)

    def getAccount(self, id64, ignoremissing=False):
        """Runs _getApp for an account"""

        id64 = self._validateAccountId(id64)
        self.updateAccount(id64)
        return self._getItem(self.accounts, id64, ignoremissing)

    # App methods

    def updateApp(self, appid):
        """Runs _updateItem for an app"""
        self._updateItem(App, self.apps, self.appExpiry, appid)

    def getApp(self, appid, ignoremissing=False):
        """Runs _getApp for an app"""

        self.updateApp(appid)
        return self._getItem(self.apps, appid, ignoremissing)
