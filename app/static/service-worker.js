"use strict";
const VERSION="nexustock-shell-v1";
const RECURSOS=["/static/offline.html","/static/css/offline.css","/static/css/sistema_visual.css","/static/img/logo-nexustock-isotipo.png"];
self.addEventListener("install",evento=>{evento.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(RECURSOS)));self.skipWaiting()});
self.addEventListener("activate",evento=>{evento.waitUntil(caches.keys().then(claves=>Promise.all(claves.filter(clave=>clave!==VERSION).map(clave=>caches.delete(clave)))));self.clients.claim()});
self.addEventListener("fetch",evento=>{const solicitud=evento.request;if(solicitud.method!=="GET")return;const url=new URL(solicitud.url);if(url.origin!==self.location.origin||url.pathname.startsWith("/api/"))return;if(solicitud.mode==="navigate"){evento.respondWith(fetch(solicitud).catch(()=>caches.match("/static/offline.html")));return}if(url.pathname.startsWith("/static/")){evento.respondWith(caches.match(solicitud).then(cacheada=>cacheada||fetch(solicitud).then(respuesta=>{if(respuesta.ok){const copia=respuesta.clone();caches.open(VERSION).then(cache=>cache.put(solicitud,copia))}return respuesta})))}});
