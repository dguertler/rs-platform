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
  var PENDING_KEY = 'rs_watchlist_pending';
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
    if (!(opts && opts.silent)) { setPending(true); doPush(); }
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

  var pushing = false;

  /** Offene Änderung: gesetzt beim Klick, gelöscht erst nach bestätigtem Schreiben.
   *  Liegt im localStorage, damit sie einen Seitenwechsel übersteht — sonst ginge
   *  ein Klick verloren, auf den sofort ein Navigieren folgt. */
  function isPending() {
    try { return global.localStorage.getItem(PENDING_KEY) === '1'; } catch (e) { return false; }
  }

  function setPending(on) {
    try {
      if (on) global.localStorage.setItem(PENDING_KEY, '1');
      else global.localStorage.removeItem(PENDING_KEY);
    } catch (e) { /* privater Modus */ }
  }

  function doPush() {
    var token = api.getToken();
    if (!token) { status('local', 'nur auf diesem Gerät'); return Promise.resolve(false); }
    if (pushing) return Promise.resolve(false);
    pushing = true;
    status('busy', 'wird gespeichert …');

    var list = read();
    return fetchRemote()
      .then(function (remote) {
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
        setPending(false);
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

    add: function (ticker) { return write(read().concat([ticker])); },

    remove: function (ticker) {
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

    /** Schreibt den lokalen Stand sofort ins Repository. Bewusst ohne
     *  Verzögerung: Ein verzögerter Schreibvorgang geht verloren, wenn direkt
     *  nach dem Klick die Seite gewechselt wird. */
    push: function () { setPending(true); return doPush(); },

    /** Holt den Stand aus dem Repository — damit alle Geräte dieselbe Liste
     *  sehen. Das Repository gewinnt, lokale Änderungen sind ja gepusht. */
    pull: function () {
      if (isPending()) {
        // Lokal steht etwas, das noch nicht im Repository ist — den Stand von
        // dort NICHT übernehmen, sondern den offenen Schreibvorgang nachholen.
        return doPush().then(function () { return read(); });
      }
      return fetchRemote()
        .then(function (remote) {
          {
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

  // Änderungen aus einem anderen Tab kommen nur als natives storage-Event an —
  // ohne diese Brücke bliebe eine offene Watchlist-Seite auf altem Stand stehen.
  global.addEventListener('storage', function (e) {
    if (e.key === STORAGE_KEY) {
      global.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: read() }));
    }
  });

  // Jede Seite, die dieses Skript lädt, gleicht einmal mit dem Repository ab —
  // sonst schriebe ein Klick in einer Index-Tabelle gegen einen veralteten Stand.
  // Steht noch ein Schreibvorgang offen, wird er dabei nachgeholt.
  api.pull();

  global.RSWatchlist = api;
})(window);
