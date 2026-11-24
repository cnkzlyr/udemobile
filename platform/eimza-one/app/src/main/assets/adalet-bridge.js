(function () {
  'use strict';
  if (window.location && !/^https:\/\/(?:[^/]+\.)?(?:uyap|adalet|yargitay|danistay)\.gov\.tr(?::\d+)?(?:\/|$)/i.test(window.location.href)) return;
  if (window.__eimzaAdaletHook) return;
  window.__eimzaAdaletHook = true;
  var local = /^https?:\/\/(localhost|127\.0\.0\.1)(:5975)?\/(api\/v1\/(signature|docsignature)(\/|$)|client\/info\/?$)/i;
  var sequence = 0, pending = Object.create(null);
  var routes = Object.create(null);
  var undelivered = Object.create(null);
  function registerRoute(id) {
    if (window.parent && window.parent !== window)
      window.parent.postMessage({direction:'eimza-adalet-route', id:id}, '*');
  }
  var documentId = Math.random().toString(36).slice(2);
  window.__eimzaAdaletResolve = function (id, text) {
    var task = pending[id];
    if (task) {
      delete pending[id];
      clearTimeout(task.timer);
      task.resolve(text);
    }
    var route=routes[id];
    if (route) {
      delete routes[id];
      if (route.expires > Date.now()) route.source.postMessage({direction:'eimza-adalet-native-response', id:id, message:text}, route.origin);
    } else if (!task) {
      Object.keys(undelivered).forEach(function (key) { if (undelivered[key].expires <= Date.now()) delete undelivered[key]; });
      if (Object.keys(undelivered).length < 1024) undelivered[id]={text:text, expires:Date.now()+180000};
    }
  };
  if (window.addEventListener) window.addEventListener('message', function (event) {
    if (event.data && event.data.direction === 'eimza-adalet-route' &&
        /^https:\/\/(?:[^/]+\.)?(?:uyap|adalet|yargitay|danistay)\.gov\.tr(?::\d+)?$/i.test(event.origin || '')) {
      for (var i=0; i<(window.frames && window.frames.length || 0); i++) if (event.source === window.frames[i]) {
        var id=event.data.id;
        if (typeof id === 'string' && id.length <= 256) {
          Object.keys(routes).forEach(function (key) { if (routes[key].expires <= Date.now()) delete routes[key]; });
          if (Object.keys(routes).length < 1024) {
            routes[id]={source:event.source, origin:event.origin, expires:Date.now()+180000}; registerRoute(id);
            if (undelivered[id]) {
              var reply=undelivered[id]; delete undelivered[id];
              if (reply.expires > Date.now()) window.__eimzaAdaletResolve(id,reply.text);
            }
          }
        }
        return;
      }
    }
    if (window.parent !== window && event.source === window.parent && event.data &&
        event.data.direction === 'eimza-adalet-native-response' && typeof event.data.message === 'string')
      window.__eimzaAdaletResolve(event.data.id, event.data.message);
  });
  function bridge(method, url, body) {
    return new Promise(function (resolve, reject) {
      var id = documentId + ':' + (++sequence);
      var timer = setTimeout(function () {
        delete pending[id];
        reject(new Error('E-imza işlemi zaman aşımına uğradı'));
      }, 180000);
      pending[id] = {resolve: resolve, timer: timer};
      registerRoute(id);
      try {
        window.EimzaNative.adaletRequest(id, method, String(url), body == null ? '' : String(body));
      } catch (error) {
        clearTimeout(timer);
        delete pending[id];
        reject(error);
      }
    });
  }
  var originalFetch = window.fetch;
  if (originalFetch) window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : input.url;
    if (!local.test(url)) return originalFetch.apply(this, arguments);
    var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    var body = init && init.body;
    var content = body !== undefined || typeof input === 'string' ? Promise.resolve(body) : input.clone().text();
    return content.then(function (text) { return bridge(method, url, text); }).then(function (text) {
      return new Response(text, {status: 200, headers: {'Content-Type': 'application/json; charset=utf-8'}});
    });
  };
  var X = window.XMLHttpRequest;
  if (!X) return;
  var open = X.prototype.open, send = X.prototype.send, abort = X.prototype.abort;
  var getHeader = X.prototype.getResponseHeader, getHeaders = X.prototype.getAllResponseHeaders;
  var setHeader = X.prototype.setRequestHeader;
  X.prototype.setRequestHeader = function (name, value) {
    if (!this.__eimza) return setHeader.apply(this, arguments);
    if (this.readyState !== 1) throw new Error("İstek açılmadı");
  };
  function property(xhr, name, value) {
    Object.defineProperty(xhr, name, {value: value, writable: true, configurable: true});
  }
  function emit(xhr, name) { xhr.dispatchEvent(new Event(name)); }
  X.prototype.open = function (method, url, asynchronous) {
    this.__eimza = local.test(String(url)) ? {method: method, url: String(url), aborted: false} : null;
    if (!this.__eimza) {
      ['readyState', 'status', 'statusText', 'response', 'responseText', 'responseURL'].forEach(function (name) {
        if (Object.prototype.hasOwnProperty.call(this, name)) delete this[name];
      }, this);
      return open.apply(this, arguments);
    }
    if (asynchronous === false) throw new Error('Senkron e-imza isteği desteklenmiyor');
    property(this, 'readyState', 1);
    property(this, 'status', 0);
    emit(this, 'readystatechange');
  };
  X.prototype.send = function (body) {
    var xhr = this, task = xhr.__eimza;
    if (!task) return send.apply(this, arguments);
    emit(xhr, 'loadstart');
    bridge(task.method, task.url, body).then(function (text) {
      if (task.aborted) return;
      property(xhr, 'status', 200);
      property(xhr, 'statusText', 'OK');
      property(xhr, 'responseURL', task.url);
      property(xhr, 'responseText', text);
      property(xhr, 'response', xhr.responseType === 'json' ? JSON.parse(text) : text);
      property(xhr, 'readyState', 4);
      emit(xhr, 'readystatechange');
      emit(xhr, 'load');
      emit(xhr, 'loadend');
    }).catch(function () {
      if (task.aborted) return;
      property(xhr, 'status', 0);
      property(xhr, 'readyState', 4);
      emit(xhr, 'readystatechange');
      emit(xhr, 'error');
      emit(xhr, 'loadend');
    });
  };
  X.prototype.abort = function () {
    if (!this.__eimza) return abort.apply(this, arguments);
    this.__eimza.aborted = true;
    property(this, 'readyState', 0);
    emit(this, 'abort');
    emit(this, 'loadend');
  };
  X.prototype.getResponseHeader = function (name) {
    if (!this.__eimza) return getHeader.apply(this, arguments);
    return this.readyState === 4 && String(name).toLowerCase() === 'content-type' ? 'application/json; charset=utf-8' : null;
  };
  X.prototype.getAllResponseHeaders = function () {
    if (!this.__eimza) return getHeaders.apply(this, arguments);
    return this.readyState === 4 ? 'content-type: application/json; charset=utf-8\r\n' : '';
  };
}());
