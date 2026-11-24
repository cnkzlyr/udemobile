(function () {
  'use strict';
  if (window.__eimzaEdevletInstalled) return;
  window.__eimzaEdevletInstalled = true;

  function nativeBridge() {
    return window.EimzaNative && typeof window.EimzaNative.edevletTransactionCode === 'function'
      ? window.EimzaNative : null;
  }

  function clean(value) {
    // The official JNLP sends transId verbatim.  Transaction codes are case
    // sensitive, so never uppercase or otherwise rewrite the displayed code.
    var match = String(value || '').match(/(?:^|[^A-Za-z0-9])([A-Za-z0-9]{6,10})(?:$|[^A-Za-z0-9])/);
    return match ? match[1] : '';
  }

  function attribute(node, name) {
    return node && node.getAttribute ? (node.getAttribute(name) || '') : '';
  }

  function identityOf(node) {
    if (!node) return '';
    return ((node.id || '') + ' ' + (node.name || '') + ' ' +
      (node.className || '') + ' ' + attribute(node, 'aria-label') + ' ' +
      attribute(node, 'placeholder') + ' ' + attribute(node, 'title') + ' ' +
      (node.textContent || '')).toLowerCase();
  }

  function isSecurityCode(node) {
    var context = identityOf(node);
    // Include the closest form/group because the captcha input itself can have
    // an opaque generated id.
    if (node && node.closest) {
      var owner = node.closest('form,.form-group,.input-group,.field,.row');
      if (owner && owner !== node) context += ' ' + identityOf(owner);
    }
    return /captcha|g[üu]venlik|security|do[gğ]rulama/.test(context);
  }

  function codeFromCopyControl(control) {
    if (!control || isSecurityCode(control)) return '';

    // Clipboard libraries commonly store the exact visible code on the copy
    // control. Read data only; never invoke the site's click handler.
    var directNames = ['data-clipboard-text', 'data-copy-text', 'data-copy',
      'data-code', 'data-value'];
    for (var i = 0; i < directNames.length; i++) {
      var direct = clean(attribute(control, directNames[i]));
      if (direct) return direct;
    }

    // Bootstrap/clipboard.js variants point at the input containing the code.
    var selector = attribute(control, 'data-clipboard-target') ||
      attribute(control, 'data-copy-target') || attribute(control, 'data-target');
    if (selector && document.querySelector) {
      try {
        var target = document.querySelector(selector);
        if (target && !isSecurityCode(target)) {
          var targetCode = clean(target.value || target.textContent || '');
          if (targetCode) return targetCode;
        }
      } catch (ignored) {}
    }

    // Some versions render the value and the Kopyala button in one group.
    var group = control.closest && control.closest('.input-group,.form-group,.row,div');
    if (group && !isSecurityCode(group)) {
      var labelled = (group.textContent || '').match(
        /(?:i[sş]lem|transaction)\s*(?:kodu|kod|code)\s*[:\-]?\s*([A-Za-z0-9]{6,10})(?:\b|$)/i);
      if (labelled) return labelled[1];
      if (group.querySelector) {
        var valueNode = group.querySelector('input[readonly],input,code,.code,.value');
        var siblingCode = valueNode && clean(valueNode.value || valueNode.textContent || '');
        if (siblingCode) return siblingCode;
      }
    }
    return '';
  }

  function nearbyCode() {
    // The e-Devlet page renders the transaction id after T.C./captcha succeeds
    // as: <div id="transid" contenteditable="false">881642</div>.
    // Read this exact portal-owned node before using any heuristic selector.
    var transId = document.getElementById && document.getElementById('transid');
    if (transId && !isSecurityCode(transId)) {
      var exactCode = clean(transId.textContent || transId.innerText || transId.value || '');
      if (exactCode) return exactCode;
    }

    // Prefer the portal's explicit copy-code UI. This is the least ambiguous
    // source and covers the page shown immediately after T.C./captcha succeeds.
    var copyControls = document.querySelectorAll(
      '[data-clipboard-text],[data-clipboard-target],[data-copy-text],[data-copy-target],' +
      'button[title*="kopya" i],button[aria-label*="kopya" i],a[title*="kopya" i],' +
      'button[title*="copy" i],button[aria-label*="copy" i],a[title*="copy" i]');
    for (var c = 0; c < copyControls.length; c++) {
      var copiedCode = codeFromCopyControl(copyControls[c]);
      if (copiedCode) return copiedCode;
    }

    var candidates = document.querySelectorAll(
      'input[id*="kod" i],input[name*="kod" i],input[id*="code" i],input[name*="code" i],' +
      '[id*="islem" i],[class*="islem" i],[id*="transaction" i],[class*="transaction" i],' +
      '[id="transid" i]');
    for (var i = 0; i < candidates.length; i++) {
      // The first e-Devlet form contains a security/captcha code.  It is not
      // the transaction code shown after identity verification.
      if (isSecurityCode(candidates[i])) continue;
      var value = candidates[i].value || candidates[i].textContent || '';
      var code = clean(value);
      if (code) return code;
    }
    var text = (document.body && document.body.innerText) || '';
    var labelled = text.match(/(?:e-?devlet\s+)?(?:işlem|islem|transaction)\s*(?:kodu|kod|code)\s*[:\-]?\s*([A-Z0-9]{6,10})(?:\b|$)/i);
    return labelled ? labelled[1] : '';
  }

  var last = '';
  function detect() {
    var bridge = nativeBridge();
    if (!bridge) return;
    var code = nearbyCode();
    if (code && code !== last) {
      last = code;
      bridge.edevletTransactionCode(location.origin, code);
    }
  }

  // Exposed only as a same-page retry hook. It does not contain the code and
  // keeps the manual Android menu path independent from DOM automation.
  window.__eimzaDetectEdevletCode = detect;

  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest ? event.target.closest('a') : null;
    if (!link || !/\.jnlp(?:$|[?#])/i.test(link.href || '')) return;
    detect();
    var bridge = nativeBridge();
    if (bridge && !nearbyCode() && typeof bridge.edevletJnlpRequested === 'function') {
      bridge.edevletJnlpRequested(location.origin);
      // The transaction code is inserted after the JNLP click by the portal.
      // Recheck after its async DOM update instead of treating the JNLP URL as
      // the code itself.
      setTimeout(detect, 250);
      setTimeout(detect, 750);
      setTimeout(detect, 1500);
    }
  }, true);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', detect);
  else detect();
  function observeDom() {
    if (!document.documentElement) return setTimeout(observeDom, 25);
    new MutationObserver(detect).observe(document.documentElement,
      {childList:true, subtree:true, characterData:true, attributes:true,
        attributeFilter:['value','data-clipboard-text','data-clipboard-target','data-copy-text']});
  }
  observeDom();
  setInterval(detect, 1500);
})();
