// ── Watchlist: Zustand im Browser ────────────────────────────────────────────
// Reine Zustandslogik ohne React, damit sie auch von Skripten ohne Babel
// genutzt werden kann. Gespeichert wird im localStorage des jeweiligen Geräts.
//
// Achtung: Der localStorage ist pro Gerät und für die Alert-Jobs (GitHub Actions)
// nicht lesbar. Für die Exit-Mails muss die Liste exportiert und als
// data/watchlist.json ins Repo gelegt werden — dafür gibt es exportJson().
(function (global) {
  'use strict';

  var STORAGE_KEY = 'rs_watchlist';
  var EVENT_NAME = 'rs-watchlist-changed';

  function read() {
    try {
      var raw = global.localStorage.getItem(STORAGE_KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.filter(function (t) { return typeof t === 'string'; }) : [];
    } catch (e) {
      return [];   // privater Modus, gesperrte Site-Daten, kaputter Eintrag
    }
  }

  function write(list) {
    var unique = [];
    for (var i = 0; i < list.length; i++) {
      var t = String(list[i]).toUpperCase().trim();
      if (t && unique.indexOf(t) === -1) unique.push(t);
    }
    unique.sort();
    try {
      global.localStorage.setItem(STORAGE_KEY, JSON.stringify(unique));
    } catch (e) {
      // Schreiben kann fehlschlagen (privater Modus, volles Kontingent) —
      // die Oberfläche soll trotzdem weiterlaufen.
    }
    global.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: unique }));
    return unique;
  }

  var api = {
    EVENT: EVENT_NAME,

    list: function () { return read(); },

    has: function (ticker) {
      return read().indexOf(String(ticker).toUpperCase().trim()) !== -1;
    },

    add: function (ticker) {
      return write(read().concat([ticker]));
    },

    remove: function (ticker) {
      var t = String(ticker).toUpperCase().trim();
      return write(read().filter(function (x) { return x !== t; }));
    },

    toggle: function (ticker) {
      return api.has(ticker) ? api.remove(ticker) : api.add(ticker);
    },

    replaceAll: function (list) { return write(list || []); },

    /** Inhalt von data/watchlist.json — für die Exit-Mails ins Repo zu legen. */
    exportJson: function () {
      return JSON.stringify({
        updated_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
        tickers: read(),
      }, null, 1);
    },

    /** Lädt die Datei herunter, die als data/watchlist.json committet wird. */
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

  global.RSWatchlist = api;
})(window);
