/* ArkSigner's supplied connector contract -> Android card signer.
 * No task contents, certificates, PINs or signatures are logged. */
(function () {
  'use strict';
  // OBS's final callback page contains its own inline SSO script.  It is not
  // an ArkSigner page and must remain byte-for-byte untouched.
  if (window.location && window.location.hostname === 'obs.saglik.gov.tr'
      && /^\/Account\/SsoLogin$/i.test(window.location.pathname || '')) return;
  // Adalet portals use their own local client, not ArkSigner's transport.
  if (!/^https:\/\/(?:[^/]+\.)?(?:enabiz\.gov\.tr|saglik\.gov\.tr|test\.arksigner\.com)(?::\d+)?(?:\/|$)/i.test(window.location.href)) return;
  if (window.__eimzaArkInstalled) return;
  window.__eimzaArkInstalled = true;
  var pending = Object.create(null);
  var routes = Object.create(null);
  var undelivered = Object.create(null);
  function registerRoute(tx) {
    if (window.parent && window.parent !== window)
      window.parent.postMessage({direction:'eimza-ark-route', transactionUUID:tx}, '*');
  }
  function note(text) {
    if (window.EimzaNative && window.EimzaNative.arkTransportStatus)
      window.EimzaNative.arkTransportStatus(text);
  }
  function errorKind(error) {
    var name=error && error.name;
    return /^(?:TypeError|ReferenceError|SyntaxError|RangeError|Error|DOMException)$/.test(name || '') ? name : 'Error';
  }
  function errorDetail(error, fallback) {
    var text = String(error && error.message || fallback || '').replace(/[\r\n\t]+/g, ' ');
    // Diagnostics may name a missing property/function, but never echo task,
    // certificate, PIN or signature payloads into the UI.
    return text.replace(/[^A-Za-z0-9_$.'()\[\]: -]/g, '?').slice(0, 140);
  }
  window.addEventListener('error',function (event) {
    if (event.error) note('ArkSigner sayfa hatası: ' + errorKind(event.error) + ': '
      + errorDetail(event.error, event.message) + '; satır=' + (Number(event.lineno) || 0)
      + '; sütun=' + (Number(event.colno) || 0)
      + '; kaynak=' + String(event.filename || '').split('?')[0].slice(-100));
  });
  window.addEventListener('unhandledrejection',function (event) {
    note('ArkSigner sayfa Promise hatası: ' + errorKind(event.reason) + ': ' + errorDetail(event.reason));
  });
  function taskOf(encoded) {
    return JSON.parse(decodeURIComponent(Array.prototype.map.call(atob(encoded), function (c) {
      return '%' + c.charCodeAt(0).toString(16).padStart(2, '0');
    }).join('')));
  }
  function send(encoded, deliver) {
    var task = taskOf(encoded), tx = task.transactionUUID || '';
    note('ArkSigner gönderim: ' + String(task.action || '').replace(/[^A-Za-z0-9_.]/g, '').slice(0,80));
    if (pending[tx]) throw new Error('Duplicate ArkSigner transaction');
    var timer = setTimeout(function () {
      var entry = pending[tx];
      if (!entry) return;
      delete pending[tx]; note('Yanıt zaman aşımı: ' + task.action);
      entry.deliver([{responseCode:'61', transactionUUID:tx}], null);
    }, 180000);
    pending[tx] = {deliver:deliver, timer:timer, action:String(task.action || '')};
    registerRoute(tx);
    try { window.EimzaNative.accept(window.location.origin, encoded); }
    catch (error) {
      clearTimeout(timer); delete pending[tx];
      deliver([{responseCode:'1001', transactionUUID:tx}], null);
    }
  }
  function resolve(text) {
    var rows;
    try { rows = JSON.parse(text); }
    catch (error) {
      note('ArkSigner yanıt JSON hatası: ' + errorDetail(error));
      return;
    }
    var tx = rows[0] && rows[0].transactionUUID || '';
    var entry = pending[tx];
    if (entry) {
      clearTimeout(entry.timer); delete pending[tx];
      try {
        entry.deliver(rows, text);
        note('ArkSigner geri çağrısı teslim edildi: ' + entry.action.replace(/[^A-Za-z0-9_.]/g,'').slice(0,80));
      }
      catch (error) {
        note('ArkSigner portal geri çağrısı başarısız: ' + errorKind(error)
          + ': ' + errorDetail(error));
      }
    }
    // evaluateJavascript targets the main frame. Route the native reply down to
    // the frame that actually owns its transaction callback, including nesting.
    var route = routes[tx];
    if (route) {
      delete routes[tx];
      if (route.expires > Date.now()) route.source.postMessage({direction:'eimza-ark-native-response', message:text}, route.origin);
    } else if (!entry) {
      Object.keys(undelivered).forEach(function (key) { if (undelivered[key].expires <= Date.now()) delete undelivered[key]; });
      if (Object.keys(undelivered).length < 1024) undelivered[tx]={text:text, expires:Date.now()+180000};
    }
  }
  window.__eimzaArkResolve = resolve;
  window.addEventListener('message', function (event) {
    if (event.data && event.data.direction === 'eimza-ark-route' &&
        /^https:\/\/(?:[^/]+\.)?(?:enabiz\.gov\.tr|saglik\.gov\.tr|test\.arksigner\.com)(?::\d+)?$/i.test(event.origin || '')) {
      for (var i=0; i<(window.frames && window.frames.length || 0); i++) if (event.source === window.frames[i]) {
        var tx=event.data.transactionUUID;
        if (typeof tx === 'string' && tx.length <= 256) {
          Object.keys(routes).forEach(function (key) { if (routes[key].expires <= Date.now()) delete routes[key]; });
          if (Object.keys(routes).length < 1024) {
            routes[tx]={source:event.source, origin:event.origin, expires:Date.now()+180000}; registerRoute(tx);
            if (undelivered[tx]) {
              var reply=undelivered[tx]; delete undelivered[tx];
              if (reply.expires > Date.now()) resolve(reply.text);
            }
          }
        }
        return;
      }
    }
    if (event.source === window.parent && window.parent !== window && event.data &&
        event.data.direction === 'eimza-ark-native-response' && typeof event.data.message === 'string') {
      resolve(event.data.message); return;
    }
    if (event.source !== window || !event.data) return;
    if (event.data.direction === 'what-is-firefox-extension-id') {
      window.postMessage({direction:'echo-from-firefox-content-script', message:'moz-extension://eimzaone/content-script.js'}, '*');
    } else if (event.data.direction === 'from-page-script' && typeof event.data.message === 'string') {
      send(event.data.message, function (rows, text) {
        window.postMessage({direction:'from-firefox-content-script', message:text || JSON.stringify(rows)}, '*');
      });
    }
  });
  // The original ArkSignerJS resource calls pwsigner.connector.send and
  // pwsigner.processResponse. Keep its transaction registry and callbacks.
  function bindConnector(signer, connector) {
    if (!connector || typeof signer.processResponse !== 'function') return;
    if (connector.send && connector.send.__eimzaNative) return;
    var nativeSend = function (encoded) {
      send(encoded, function (rows, text) { signer.processResponse(text || JSON.stringify(rows)); });
    };
    nativeSend.__eimzaNative = true;
    var descriptor = Object.getOwnPropertyDescriptor(connector, 'send');
    if (!descriptor || descriptor.configurable) {
      // Connector initialization can replace send immediately after assignment.
      // Keep the native transport bound without the polling gap.
      Object.defineProperty(connector, 'send', {configurable:true, enumerable:true,
        get:function () { return nativeSend; }, set:function () {}});
    } else connector.send = nativeSend;
    note('ArkSigner JavaScript bağlayıcısı uygulamaya bağlandı');
  }
  function attach(signer) {
    if (!signer || (typeof signer !== 'object' && typeof signer !== 'function')) return;
    if (!signer.__eimzaConnectorWatched) {
      var descriptor = Object.getOwnPropertyDescriptor(signer, 'connector');
      if (!descriptor || (descriptor.configurable && !descriptor.get && !descriptor.set)) {
        var connector = signer.connector;
        Object.defineProperty(signer, 'connector', {configurable:true, enumerable:true,
          get:function () { return connector; },
          set:function (value) { connector = value; bindConnector(signer, value); }});
        Object.defineProperty(signer, '__eimzaConnectorWatched', {value:true});
      }
    }
    bindConnector(signer, signer.connector);
  }
  var signerDescriptor = Object.getOwnPropertyDescriptor(window, 'pwsigner');
  if (!signerDescriptor || (signerDescriptor.configurable && !signerDescriptor.get && !signerDescriptor.set)) {
    var currentSigner = window.pwsigner;
    Object.defineProperty(window, 'pwsigner', {configurable:true, enumerable:true,
      get:function () { return currentSigner; },
      set:function (value) { currentSigner = value; attach(value); }});
  }
  // Also catch the bootstrap JSONP request before the signer is initialized.
  function localRequest(node) {
    if (!node || String(node.tagName).toUpperCase() !== 'SCRIPT' || !node.src) return false;
    var url;
    try { url = new URL(node.src, window.location.href); } catch (_) { return false; }
    var hosts = ['127.0.0.1', 'localhost', 'local.pwsigner.ark-teknoloji.com', 'local.api.arksigner.net'];
    if (hosts.indexOf(url.hostname) < 0 || ['16356','16357'].indexOf(url.port) < 0) return false;
    var parameters = url.searchParams.get('parameters'), callback = url.searchParams.get('callback');
    if (!parameters || !callback || !/^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(callback)) return false;
    send(parameters, function (rows) {
      var parts = callback.split('.'), owner = window;
      for (var i = 0; i < parts.length - 1 && owner; i++) owner = owner[parts[i]];
      var fn = owner && owner[parts[parts.length - 1]];
      if (typeof fn === 'function') fn.call(owner, rows);
      else note('ArkSigner JSONP geri çağrısı bulunamadı');
      if (node.dispatchEvent) node.dispatchEvent(new Event('load'));
      attach(window.pwsigner);
    });
    note('ArkSigner yerel JSONP isteği uygulamaya yönlendirildi');
    return true;
  }
  if (window.Node) ['appendChild','insertBefore','replaceChild'].forEach(function (method) {
    var original = window.Node.prototype[method];
    window.Node.prototype[method] = function (node) {
      if (localRequest(node)) return method === 'replaceChild' ? arguments[1] : node;
      return original.apply(this, arguments);
    };
  });
  attach(window.pwsigner);
  setInterval(function () { attach(window.pwsigner); }, 100);

  // Bootstrap may use fetch/XHR before pwsigner.connector exists. Handle only
  // ArkSigner's known loopback hosts, ports and encoded parameters contract.
  function localUrl(value) {
    try {
      var url = new URL(String(value), window.location.href);
      return ['http:','https:'].indexOf(url.protocol) >= 0 &&
        ['127.0.0.1','localhost','local.pwsigner.ark-teknoloji.com','local.api.arksigner.net'].indexOf(url.hostname) >= 0 &&
        ['16356','16357'].indexOf(url.port) >= 0 ? url : null;
    } catch (_) { return null; }
  }
  function httpTask(url, body) {
    var parameters = url.searchParams.get('parameters');
    if (!parameters && body && typeof body.get === 'function') parameters = body.get('parameters');
    if (!parameters && typeof body === 'string') {
      var trimmed = body.trim();
      if (trimmed.charAt(0) === '{') {
        var json;
        try { json = JSON.parse(trimmed); } catch (_) { throw httpError('JSON gövdesi ayrıştırılamadı'); }
        if (typeof json.parameters === 'string') parameters = json.parameters;
        else if (typeof json.action === 'string') parameters = btoa(encodeURIComponent(trimmed).replace(/%([0-9A-F]{2})/g,function (_,hex) {return String.fromCharCode(parseInt(hex,16));}));
      } else {
        parameters = new URLSearchParams(body).get('parameters');
        if (!parameters && /^[A-Za-z0-9+\/\s]+={0,2}$/.test(trimmed)) parameters = trimmed;
      }
    }
    if (!parameters) throw httpError('parameters alanı yok');
    parameters = String(parameters).replace(/ /g,'+');
    try {
      var task = taskOf(parameters);
      if (!task || typeof task.action !== 'string') throw new Error();
    } catch (_) { throw httpError('Base64 görev çözümlenemedi'); }
    return parameters;
  }
  function httpError(reason) {
    var error = new Error('ArkSigner HTTP'); error.arkReason = reason; return error;
  }
  function httpReply(url, parameters) {
    note('ArkSigner yerel HTTP isteği uygulamaya yönlendirildi');
    return new Promise(function (resolve) {
      send(parameters, function (rows, text) {
        var callback = url.searchParams.get('callback');
        var data = text || JSON.stringify(rows);
        resolve(callback && /^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(callback)
          ? callback + '(' + data + ')' : '(' + data + ')');
      });
    });
  }
  function unwrapHttpReply(text) {
    var value=String(text || '').trim();
    return value.charAt(0)==='(' && value.charAt(value.length-1)===')'
      ? value.slice(1,-1) : value;
  }
  var originalFetch = window.fetch;
  if (originalFetch) window.fetch = function (input, init) {
    var url = localUrl(typeof input === 'string' ? input : input.url);
    if (!url) return originalFetch.apply(this, arguments);
    var self = this, args = arguments;
    var body = init && init.body;
    return (body !== undefined || typeof input === 'string' ? Promise.resolve(body) : input.clone().text()).then(function (text) {
      var parameters = httpTask(url, text);
      if (!parameters) return originalFetch.apply(self, args);
      return httpReply(url, parameters).then(function (data) {
        return new Response(data, {status:200, headers:{'Content-Type':url.searchParams.has('callback') ? 'application/javascript' : 'application/json'}});
      });
    }).catch(function (error) {
      note('ArkSigner HTTP: ' + (error.arkReason || 'fetch aktarımı başarısız'));
      throw error;
    });
  };
  var X = window.XMLHttpRequest;
  if (X) {
    var open = X.prototype.open, xhrSend = X.prototype.send, abort = X.prototype.abort;
    var header = X.prototype.setRequestHeader, getHeader = X.prototype.getResponseHeader, allHeaders = X.prototype.getAllResponseHeaders;
    function property(xhr, name, value) { Object.defineProperty(xhr, name, {value:value, writable:true, configurable:true}); }
    function emit(xhr, name) { xhr.dispatchEvent(new Event(name)); }
    X.prototype.open = function (method, value, async) {
      var url = localUrl(value);
      if (url && !url.searchParams.has('parameters') && String(method).toUpperCase() !== 'POST') url = null;
      this.__eimzaArkHttp = url ? {url:url, aborted:false} : null;
      ['readyState','status','statusText','response','responseText','responseURL'].forEach(function (name) {
        if (Object.prototype.hasOwnProperty.call(this,name)) delete this[name];
      },this);
      if (!url) return open.apply(this,arguments);
      if (async === false) throw new Error('Senkron ArkSigner isteği desteklenmiyor');
      property(this,'readyState',1); property(this,'status',0); emit(this,'readystatechange');
    };
    X.prototype.setRequestHeader = function () { if (!this.__eimzaArkHttp) return header.apply(this,arguments); };
    X.prototype.send = function (body) {
      var xhr = this, task = xhr.__eimzaArkHttp;
      if (!task) return xhrSend.apply(this,arguments);
      emit(xhr,'loadstart');
      Promise.resolve().then(function () {
        var parameters = httpTask(task.url,body);
        if (!parameters) throw new Error('ArkSigner parameters yok');
        return httpReply(task.url,parameters);
      }).then(function (text) {
        if (task.aborted) return;
        property(xhr,'status',200); property(xhr,'statusText','OK'); property(xhr,'responseURL',task.url.href);
        property(xhr,'responseText',text); property(xhr,'response',xhr.responseType === 'json' ? JSON.parse(unwrapHttpReply(text)) : text);
        property(xhr,'readyState',4); emit(xhr,'readystatechange'); emit(xhr,'load'); emit(xhr,'loadend');
      }).catch(function (error) {
        if (task.aborted) return;
        note('ArkSigner HTTP: ' + (error.arkReason || 'XHR yanıtı işlenemedi'));
        property(xhr,'status',0); property(xhr,'readyState',4); emit(xhr,'readystatechange'); emit(xhr,'error'); emit(xhr,'loadend');
      });
    };
    X.prototype.abort = function () {
      if (!this.__eimzaArkHttp) return abort.apply(this,arguments);
      this.__eimzaArkHttp.aborted = true; property(this,'readyState',0); emit(this,'abort'); emit(this,'loadend');
    };
    X.prototype.getResponseHeader = function (name) {
      if (!this.__eimzaArkHttp) return getHeader.apply(this,arguments);
      return this.readyState === 4 && String(name).toLowerCase() === 'content-type' ?
        (this.__eimzaArkHttp.url.searchParams.has('callback') ? 'application/javascript' : 'application/json; charset=utf-8') : null;
    };
    X.prototype.getAllResponseHeaders = function () {
      return this.__eimzaArkHttp ? (this.readyState === 4 ? 'content-type: application/json; charset=utf-8\r\n' : '') : allHeaders.apply(this,arguments);
    };
  }
})();
