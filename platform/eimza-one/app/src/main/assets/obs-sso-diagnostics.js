(function () {
  'use strict';
  if (!window.location || window.location.hostname !== 'obs.saglik.gov.tr'
      || !/^\/Account\/SsoLogin$/i.test(window.location.pathname || '')) return;
  function clean(value) {
    return String(value || '').replace(/[A-Za-z0-9+\/_=%-]{80,}/g, '[gizli]')
      .replace(/[\r\n\t]+/g, ' ').slice(0, 220);
  }
  function note(value) {
    try {
      if (window.EimzaNative && window.EimzaNative.arkTransportStatus)
        window.EimzaNative.arkTransportStatus(value);
    } catch (_) {}
  }
  window.addEventListener('error', function (event) {
    window.__eimzaObsErrorLine = Number(event.lineno) || 0;
    window.__eimzaObsErrorColumn = Number(event.colno) || 0;
    note('OBS SSO JS hatası: ' + clean(event.message) + '; satır='
      + (Number(event.lineno) || 0) + '; sütun=' + (Number(event.colno) || 0)
      + '; kaynak=' + clean(String(event.filename || '').split('?')[0].slice(-100)));
  });
  window.addEventListener('unhandledrejection', function (event) {
    note('OBS SSO Promise hatası: ' + clean(event.reason && event.reason.message || event.reason));
  });
})();
