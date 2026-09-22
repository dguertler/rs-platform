// ── Watchlist: Zustand im Browser + Abgleich mit dem Repository ──────────────
// Reine Zustandslogik ohne React, damit sie auch von Skripten ohne Babel
// genutzt werden kann.
//
// Zwei Ebenen:
//   1. localStorage — sofortige Anzeige, funktioniert immer, auch ohne Token.
//   2. data/watchlist.json im Repo — das ist die Liste, die der nächtliche
//      Verkaufssignal-Job (check_exits.py) liest. Ohne diesen Schritt bleibt
//      die Watchlist im Browser und erreicht die Mails nicht.
//
// Lesen geht ohne Token (öffentliches Repository), Schreiben braucht einen
// fine-grained Personal Access Token mit "Contents: Read and write", begrenzt
// auf genau dieses Repository. Der Token liegt nur im localStorage dieses
// Geräts — er steht nirgends im Seitenquelltext.
(function (global) {
  'use strict';

  var STORAGE_KEY = 'rs_watchlist';
  var TOKEN_KEY = 'rs_watchlist_token';
  var EVENT_NAME = 'rs-watchlist-changed';
  var SYNC_EVENT = 'rs-watchlist-sync';

  var REPO = { owner: 'dguertler', name: 'rs-platform', branch: 'master', path: 'data/watchlist.json' };
  var API = 'https://api.github.com/repos/' + REPO.owner + '/' + REPO.name + '/contents/' + REPO.path;

  // ── localStorage ───────────────────────────────────────────────────────────

  function read() {
    try {
      var raw = global.localStorage.getItem(STORAGE_KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.filter(function (t) { return typeof t === 'string'; }) : [];
    } catch (e) {
      return [];   // privater Modus, gesperrte Site-Daten, kaputter Eintrag
    }
  }

  function normalize(list) {
    var unique = [];
    for (var i = 0; i < list.length; i++) {
      var t = String(list[i]).toUpperCase().trim();
      if (t && unique.indexOf(t) === -1) unique.push(t);
    }
    return unique.sort();
  }

  function write(list, opts) {
    var unique = normalize(list);
    try {
      global.localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
    } catch (e) {
      // Schreiben kann fehlschlagen (privater Modus, volles Kontingent) —
      // die Oberfläche soll trotzdem weiterlaufen.
    }
    global.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: unique }));
    if (!(opts && opts.silent)) api.push();
    return unique;
  }

  // ── Abgleich mit dem Repository ────────────────────────────────────────────

  function status(state, message) {
    global.dispatchEvent(new CustomEvent(SYNC_EVENT, { detail: { state: state, message: message } }));
  }

  function toBase64(text) {
    var bytes = new TextEncoder().encode(text);
    var binary = '';
    for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return global.btoa(binary);
  }

  function fromBase64(b64) {
    var binary = global.atob(String(b64).replace(/\s/g, ''));
    var bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }

  function fileBody(list) {
    return JSON.stringify({
      updated_at: new Date().toISOString().slice(0, 16).replace('T', ' '),
      tickers: list,
    }, null, 1) + '\n';
  }

  function headers() {
    var h = { 'Accept': 'application/vnd.github+json' };
    var token = api.getToken();
    if (token) h['Authorization'] = 'Bearer ' + token;
    return h;
  }

  /** Aktuellen Stand samt sha holen. sha wird zum Schreiben gebraucht. */
  function fetchRemote() {
    return fetch(API + '?ref=' + REPO.branch + '&t=' + Date.now(), { headers: headers() })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (json) {
        var parsed = JSON.parse(fromBase64(json.content));
        return { sha: json.sha, tickers: normalize(parsed.tickers || []) };
      });
  }

  var pushTimer = null;
  var pushing = false;
  var dirty = false;          // lokale Änderung, die noch nicht im Repo steht
  var pulledBeforeChange = false;

  function doPush() {
    var token = api.getToken();
    if (!token) { status('local', 'nur auf diesem Gerät'); return Promise.resolve(false); }
    if (pushing) return Promise.resolve(false);
    pushing = true;
    status('busy', 'wird gespeichert …');

    var list = read();
    return fetchRemote()
      .then(function (remote) {
        // Wurde geklickt, bevor der Stand aus dem Repository da war, ist die
        // lokale Liste womöglich veraltet — dann vereinigen statt ersetzen,
        // damit Einträge anderer Geräte nicht verloren gehen. Eine Löschung
        // greift in diesem Fall erst beim nächsten Klick.
        if (!pulledBeforeChange) list = normalize(remote.tickers.concat(list));
        if (remote.tickers.join(',') === list.join(',')) return null;   // nichts zu tun
        return fetch(API, {
          method: 'PUT',
          headers: Object.assign({ 'Content-Type': 'application/json' }, headers()),
          body: JSON.stringify({
            message: 'Watchlist aktualisiert (' + list.length + ' Titel)',
            content: toBase64(fileBody(list)),
            sha: remote.sha,
            branch: REPO.branch,
          }),
        }).then(function (r) {
          if (!r.ok) return r.text().then(function (t) { throw new Error('HTTP ' + r.status + ' ' + t.slice(0, 120)); });
          return r.json();
        });
      })
      .then(function () {
        if (list.join(',') !== read().join(',')) write(list, { silent: true });
        dirty = false;
        status('ok', 'im Repository gespeichert');
        return true;
      })
      .catch(function (e) { status('error', 'nicht gespeichert: ' + e.message); return false; })
      .then(function (ok) { pushing = false; return ok; });
  }

  // ── Öffentliche Schnittstelle ──────────────────────────────────────────────

  var api = {
    EVENT: EVENT_NAME,
    SYNC_EVENT: SYNC_EVENT,

    list: function () { return read(); },

    has: function (ticker) {
      return read().indexOf(String(ticker).toUpperCase().trim()) !== -1;
    },

    add: function (ticker) { dirty = true; return write(read().concat([ticker])); },

    remove: function (ticker) {
      dirty = true;
      var t = String(ticker).toUpperCase().trim();
      return write(read().filter(function (x) { return x !== t; }));
    },

    toggle: function (ticker) {
      return api.has(ticker) ? api.remove(ticker) : api.add(ticker);
    },

    replaceAll: function (list, opts) { return write(list || [], opts); },

    getToken: function () {
      try { return global.localStorage.getItem(TOKEN_KEY) || ''; } catch (e) { return ''; }
    },

    setToken: function (token) {
      try {
        if (token) global.localStorage.setItem(TOKEN_KEY, String(token).trim());
        else global.localStorage.removeItem(TOKEN_KEY);
      } catch (e) { /* privater Modus */ }
      status(token ? 'idle' : 'local', token ? 'Token hinterlegt' : 'nur auf diesem Gerät');
    },

    /** Schreibt den lokalen Stand ins Repository (gebündelt, damit schnelle
     *  Klickfolgen nur einen Commit erzeugen). */
    push: function () {
      if (pushTimer) clearTimeout(pushTimer);
      pushTimer = setTimeout(doPush, 800);
    },

    /** Holt den Stand aus dem Repository — damit alle Geräte dieselbe Liste
     *  sehen. Das Repository gewinnt, lokale Änderungen sind ja gepusht. */
    pull: function () {
      return fetchRemote()
        .then(function (remote) {
          if (!dirty) {
            pulledBeforeChange = true;
            if (remote.tickers.join(',') !== read().join(',')) {
              write(remote.tickers, { silent: true });
            }
          }
          status(api.getToken() ? 'ok' : 'readonly', 'Stand aus dem Repository');
          return remote.tickers;
        })
        .catch(function (e) {
          status('error', 'Repository nicht erreichbar: ' + e.message);
          return read();
        });
    },

    /** Inhalt von data/watchlist.json — Notausgang ohne Token. */
    exportJson: function () { return fileBody(read()); },

    download: function () {
      var blob = new Blob([api.exportJson()], { type: 'application/json' });
      var url = URL.createObjectURL(blob);
      var a = global.document.createElement('a');
      a.href = url;
      a.download = 'watchlist.json';
      a.click();
      URL.revokeObjectURL(url);
    },
  };

  // Jede Seite, die dieses Skript lädt, gleicht einmal mit dem Repository ab —
  // sonst schriebe ein Klick in einer Index-Tabelle gegen einen veralteten Stand.
  api.pull();

  global.RSWatchlist = api;
})(window);
