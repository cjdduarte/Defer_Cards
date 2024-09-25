# -*- coding: utf-8 -*-
# Copyright(C)| 2022 Carlos Duarte - Defer Cards
# Fork on    | Lovac42 code, in add-on "SlackersDelight" https://github.com/lovac42/SlackersDelight
# License     | GNU AGPL, version 3 ou posterior; http://www.gnu.org/licenses/agpl.html
# Source in   | https://github.com/cjdduarte/DeferCards

# == User Config =========================================

DEFERRED_DECK_NAME = "~Defer Cards~"  # Nome do deck alterado

# == End Config ==========================================
##########################################################

import aqt, time
from anki import decks  # Certifique-se de importar o módulo anki corretamente
from aqt import mw
from aqt.qt import *
from aqt.reviewer import Reviewer
from anki.hooks import addHook, wrap
from anki.utils import int_time
from aqt.utils import showWarning, showInfo, tooltip
from .config import Config

# Tente importar PyQt6, se não, use PyQt5
try:
    from PyQt6.QtCore import pyqtSlot
except ImportError:
    from PyQt5.QtCore import pyqtSlot

DEFERRED_DECK_DESC = """
<p><i>Defer Cards.</i></p><p>
<b>Warning:</b> On mobile, or without this addon,<br>
learning cards may behave differently, and could be converted to review or new cards<br>
if certain actions are taken.<br></p><br>"""

ADDON_NAME = "DeferCards"
conf = Config(ADDON_NAME)

class DeferCards:
    def __init__(self):
        self.timeId = int_time() % 100000
        addHook("Reviewer.contextMenuEvent", self.showContextMenu)

    def showContextMenu(self, r, m):
        hk = conf.get("hotkey", "_")
        a = m.addAction("Defer")
        a.setShortcut(QKeySequence(hk))
        a.triggered.connect(self.defer)

    def defer(self):
        "main operations"
        card = mw.reviewer.card
        did = self.getDynId()  # `did` é o valor retornado pelo método getDynId()
        if did and did != card.did:
            # Require reschedule for lrn card in filtered decks
            if card.odid and card.queue in (1, 3, 4):
                conf = mw.col.decks.confForDid(card.did)
                if not conf['resched']:
                    return

            # Use `did` em vez de `dynId`
            mw.col.db.execute("UPDATE cards SET did = ? WHERE id = ?", did, card.id)
            self.swap(did, card)
            mw.reset()
            tooltip("Card Deferred.", period=1000)

    def getDynId(self, create=True):
        "Built or select Dyn deck"
        dyn = mw.col.decks.by_name(DEFERRED_DECK_NAME)
        if not dyn:  # Create filtered deck
            if not create:
                return  # test only
            did = mw.col.decks.id(DEFERRED_DECK_NAME, type=decks.defaultDynamicDeck)
            dyn = mw.col.decks.get(did)
        elif not dyn['dyn']:  # Regular deck w/ same name
            showInfo("Please rename the existing %s deck first." % DEFERRED_DECK_NAME)
            return False
        return dyn['id']

    def swap(self, dynId, card):
        "Swap card info"
        if not card.odid:
            card.odid = card.did
            if card.queue == 1 and mw.col.sched.name != "std2":
                # Fix bad cards during db check
                card.odue = mw.col.sched.today
            else:  # new/rev cards
                card.odue = card.due
                card.due = -self.timeId
                self.timeId += 1
        card.did = dynId
        mw.col.update_card(card)  # Use o método atualizado

sd = DeferCards()

# Friendly Warning Message
def desc(self, deck, _old):
    if deck['name'] != DEFERRED_DECK_NAME:
        return _old(self, deck)
    return DEFERRED_DECK_DESC

# Handing keybinds
def shortcutKeys(self, _old):
    ret = _old(self)
    ret.append((conf.get("hotkey", "_"), sd.defer))
    return ret

# Prevent user from rebuilding this special deck
def sd_rebuildDyn(self, did=None, _old=None):
    did = did or self.col.decks.selected()
    dyn = mw.col.decks.get(did)
    if dyn['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.")
        return None
    return _old(self, did)

# Prevent user from changing deck options
def sd_onDeckConf(self, deck=None, _old=None):
    if not deck:
        deck = self.col.decks.current()
    if deck['name'] == DEFERRED_DECK_NAME:
        showWarning("Can't modify this deck.")
        return
    return _old(self, deck)

Reviewer._shortcutKeys = wrap(Reviewer._shortcutKeys, shortcutKeys, 'around')
aqt.main.AnkiQt.onDeckConf = wrap(aqt.main.AnkiQt.onDeckConf, sd_onDeckConf, 'around')
aqt.overview.Overview._desc = wrap(aqt.overview.Overview._desc, desc, 'around')

# Adiciona o botão personalizado na interface do Anki
def add_custom_button(self):
    # Verifica se a configuração permite exibir o botão
    if not conf.get("showButton", True):
        return
    
    # Adiciona o botão usando JavaScript diretamente na estrutura HTML do Anki
    js_code = """
    (function() {
        // Verifica se o botão já foi adicionado
        if (document.getElementById('customButton')) return;
        
        // Cria o botão
        var customButton = document.createElement('button');
        customButton.id = 'customButton';
        customButton.innerText = 'Defer';
        customButton.title = 'Shortcut key: _';

        // Define a ação do botão
        customButton.onclick = function() { pycmd('customButtonClick'); };

        // Adiciona classes de estilo para herdar o estilo dos outros botões
        customButton.className = 'btn';

        // Estiliza o botão para ser absoluto e ficar ao lado do botão "More"
        customButton.style.position = 'absolute';
        customButton.style.right = '90px'; // Ajuste a posição conforme necessário
        customButton.style.top = '10px';   // Ajuste a posição conforme necessário

        // Encontra o elemento do botão "More" para inserir o botão antes dele
        var moreButton = document.querySelector("td[class='stat'] > button[title*='M']");
        if (moreButton) {
            moreButton.parentNode.style.position = 'relative'; // Torna o container relativo
            moreButton.parentNode.appendChild(customButton);
        }
    })();
    """
    # Executa o JavaScript na página do Anki para adicionar o botão
    self.bottom.web.eval(js_code)

# Função personalizada que é chamada quando o botão é clicado
@pyqtSlot()
def on_custom_button_click():
    sd.defer()  # Chama a função defer() do DeferCards

# Função que intercepta o comando vindo do botão
def custom_pycmd_handler(self, cmd, _old):
    if cmd == "customButtonClick":
        on_custom_button_click()
    else:
        _old(self, cmd)

# Conectar o método ao Reviewer
Reviewer._initWeb = wrap(Reviewer._initWeb, add_custom_button)
Reviewer._linkHandler = wrap(Reviewer._linkHandler, custom_pycmd_handler, "around")
