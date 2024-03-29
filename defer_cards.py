# -*- coding: utf-8 -*-
# Copyright(C)| 2022 Carlos Duarte - Defer Cards
# Fork on    | Lovac42 code, in add-on "SlackersDelight" https://github.com/lovac42/SlackersDelight
# License     | GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
# Source in   | https://github.com/cjdduarte/DeferCards

# == User Config =========================================

DEFERRED_DECK_NAME = "~Defer Cards~"  # Nome do deck alterado

# == End Config ==========================================
##########################################################

import aqt, time
import anki.sched
from aqt import mw
from aqt.qt import *
from aqt.reviewer import Reviewer
from anki.hooks import addHook, wrap
from anki.utils import intTime, ids2str
from aqt.utils import showWarning, showInfo, tooltip
# from anki.lang import _
# import anki.schedv2

from anki import version
ANKI21 = version.startswith("2.1.")

from .config import Config

DEFERRED_DECK_DESC = """
<p><i>Defer Cards.</i></p><p>
<b>Warning:</b> On mobile, or without this addon,<br>
learning cards are converted to review or new cards<br>
when the empty button is clicked.<br>
<i>(Default behavior on the V1 Scheduler,<br>
not a problem on the V2 or V3 Scheduler.)</i></p><br>"""

ADDON_NAME = "DeferCards"
conf = Config(ADDON_NAME)

class DeferCards:
    def __init__(self):
        self.timeId=intTime()%100000
        addHook("Reviewer.contextMenuEvent", self.showContextMenu)

    def showContextMenu(self, r, m):
        hk=conf.get("hotkey","_")
        a=m.addAction("Defer")
        a.setShortcut(QKeySequence(hk))
        a.triggered.connect(self.defer)

    def defer(self):
        "main operations"
        card = mw.reviewer.card
        did = self.getDynId()
        if did and did != card.did:
            #Require reschedule for lrn card in filtered decks
            if card.odid and card.queue in (1,3,4):
                conf=mw.col.decks.confForDid(card.did)
                if not conf['resched']: return

            mw.col.log(did,[card.id])
            self.swap(did, card)
            mw.reset()
            tooltip(_("Card Deferred."), period=1000)

    def getDynId(self, create=True):
        "Built or select Dyn deck"
        dyn=mw.col.decks.byName(_(DEFERRED_DECK_NAME))
        if not dyn: #Create filtered deck
            if not create: return #test only
            did =  mw.col.decks.id(_(DEFERRED_DECK_NAME), 
                        type=anki.decks.defaultDynamicDeck)
            dyn = mw.col.decks.get(did)
        elif not dyn['dyn']: #Regular deck w/ same name
            showInfo("Please rename the existing %s deck first."%DEFERRED_DECK_NAME)
            return False
        return dyn['id']

    def swap(self, dynId, card):
        "Swap card info"
        if not card.odid:
            card.odid=card.did
            if card.queue==1 and mw.col.sched.name != "std2":
                #fix bad cards during db check
                card.odue=mw.col.sched.today
            else: #new/rev cards
                card.odue=card.due
                card.due=-self.timeId
                self.timeId+=1
        card.did=dynId
        card.flushSched()

sd=DeferCards()

#Friendly Warning Message
def desc(self, deck, _old):
    if deck['name'] != DEFERRED_DECK_NAME:
        return _old(self, deck)
    return DEFERRED_DECK_DESC

#Handing keybinds Anki2.0
def keyHandler(self, evt, _old):
    if unicode(evt.text()) == conf.get("hotkey","_"):
        sd.defer()
    else:
        return _old(self, evt)

#Handing keybinds Anki2.1
def shortcutKeys(self, _old):
    ret=_old(self)
    ret.append((conf.get("hotkey","_"), sd.defer))
    return ret

#Add button on bottom bar
def initWeb(self):
    if conf.get("show_defer_button",True):
        card = mw.reviewer.card
        if card.did==sd.getDynId(False): return
        lnkcmd="pycmd" if ANKI21 else "py.link"
        dbtn = """<td width="50" class="align-right stat"><button title="Shortcut key: _" id="defbut" onclick="%s(&quot;deferbtn&quot;);">Defer</button></td>""" % lnkcmd
        self.bottom.web.eval("""$("#middle").closest('tr').append('%s');""" % dbtn)
        self.bottom.web.eval("""$("<style>.align-right { text-align: right; }</style>").appendTo("head");""")

#handles callback from button
def linkHandler(self, url, _old):
    if url == "deferbtn":
        sd.defer()
    else:
        return _old(self, url)

#For V1 Scheduler:
#This is necessary to keep the learning card status if user clicks empty.
#Default is to change type1=0 new, type2=2 review
def sd_emptyDyn(self, did, lim=None, _old=None):
    dyn = mw.col.decks.get(did)
    if dyn['name'] != DEFERRED_DECK_NAME:
        return _old(self, did, lim)
    if not lim:
        lim = "did = %s" % did
    self.col.log(self.col.db.list("select id from cards where %s" % lim))
    self.col.db.execute("""
update cards set did = odid,
due = (case when queue in (1,3) then due else odue end),
odue = 0, odid = 0, usn = ? where %s""" %
lim, self.col.usn())

# In case user changes decks in Browser or other altercations.
# Since the Deck ID is not given, we are checking each card one by one.
# This is a taxing process, so we are limiting it to 10 cards max.
# If more than 10, we are using the first card only.
# Defered decks and normal decks should not be mixed.
def sd_remFromDyn(self, cids, _old):
    if len(cids)>10:
        did=mw.col.getCard(cids[0]).did
        self.emptyDyn(did, "id in %s and odid" % ids2str(cids))
    else:
        for id in cids:
            did=mw.col.getCard(id).did
            self.emptyDyn(did, "id = %d and odid" % id)

#Prevent user from rebuilding this special deck
def sd_rebuildDyn(self, did=None, _old=None):
    did = did or self.col.decks.selected()
    dyn = mw.col.decks.get(did)
    if dyn['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.")
        return None
    return _old(self, did)

#Prevent user from changing deck options
def sd_onDeckConf(self, deck=None, _old=None):
    if not deck:
        deck = self.col.decks.current()
    if deck['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.")
        return
    return _old(self, deck)

Reviewer._initWeb = wrap(Reviewer._initWeb, initWeb, 'after')
Reviewer._linkHandler = wrap(Reviewer._linkHandler, linkHandler, 'around')
Reviewer._shortcutKeys = wrap(Reviewer._shortcutKeys, shortcutKeys, 'around')

aqt.main.AnkiQt.onDeckConf = wrap(aqt.main.AnkiQt.onDeckConf, sd_onDeckConf, 'around')
aqt.overview.Overview._desc = wrap(aqt.overview.Overview._desc, desc, 'around')

'''
anki.sched.Scheduler.emptyDyn = wrap(anki.sched.Scheduler.emptyDyn, sd_emptyDyn, 'around')
anki.sched.Scheduler.remFromDyn = wrap(anki.sched.Scheduler.remFromDyn, sd_remFromDyn, 'around')
anki.sched.Scheduler.rebuildDyn = wrap(anki.sched.Scheduler.rebuildDyn, sd_rebuildDyn, 'around')
anki.schedv2.Scheduler.rebuildDyn = wrap(anki.schedv2.Scheduler.rebuildDyn, sd_rebuildDyn, 'around')
'''