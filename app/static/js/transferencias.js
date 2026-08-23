"use strict";

const cfg = {
    api: document.body.dataset.apiTransferencias,
    bodegas: document.body.dataset.apiBodegas,
    productos: document.body.dataset.apiProductos,
    crear: document.body.dataset.puedeCrear === "true",
    despachar: document.body.dataset.puedeDespachar === "true",
    recibir: document.body.dataset.puedeRecibir === "true",
};
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const csrf = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

async function pedir(url, opciones = {}) {
    const headers = { Accept: "application/json", ...(opciones.headers || {}) };
    if (opciones.body !== undefined) headers["Content-Type"] = "application/json";
    if (csrf()) headers["X-CSRFToken"] = csrf();
    const respuesta = await fetch(url, { credentials: "same-origin", ...opciones, headers });
    const datos = await respuesta.json().catch(() => ({}));
    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible completar la operación.");
    return datos;
}

function avisar(mensaje, error = false) {
    const nodo = $("notificacion");
    nodo.textContent = mensaje;
    nodo.classList.toggle("notificacion--error", error);
    nodo.hidden = false;
    window.setTimeout(() => { nodo.hidden = true; }, 3500);
}

function acciones(t) {
    const botones = [];
    if (cfg.crear && t.estado === "borrador") botones.push(`<button class="boton" data-accion="solicitar" data-id="${t.id}">Solicitar</button>`);
    if (cfg.despachar && t.estado === "solicitada") botones.push(`<button class="boton" data-accion="despachar" data-id="${t.id}">Despachar</button>`);
    if (cfg.recibir && t.estado === "en_transito") botones.push(`<button class="boton" data-accion="recibir" data-id="${t.id}">Recibir</button>`);
    if (cfg.crear && ["borrador", "solicitada"].includes(t.estado)) botones.push(`<button class="boton boton--peligro" data-accion="cancelar" data-id="${t.id}">Cancelar</button>`);
    return botones.join("") || "—";
}

function render(datos) {
    const lista = datos.transferencias || [];
    $("estado-lista").textContent = lista.length ? `${lista.length} transferencia(s)` : "No hay transferencias para este filtro.";
    $("lista-transferencias").innerHTML = lista.map((t) => `<tr>
        <td><strong>${esc(t.numero)}</strong></td>
        <td>${esc(t.bodega_origen)} → ${esc(t.bodega_destino)}</td>
        <td><span class="estado">${esc(t.estado.replaceAll("_", " "))}</span></td>
        <td class="detalle">${t.items.map((i) => `<p><strong>${esc(i.producto_codigo)}</strong> ${esc(i.producto_nombre)}<br>Solicitada ${esc(i.cantidad_solicitada)} · Despachada ${esc(i.cantidad_despachada)} · Recibida ${esc(i.cantidad_recibida)} · Diferencia ${esc(i.diferencia)}</p>`).join("")}</td>
        <td>${t.fecha_solicitud ? `Solicitud: ${new Date(t.fecha_solicitud).toLocaleString("es-CL")}` : "—"}<br>${t.fecha_despacho ? `Despacho: ${new Date(t.fecha_despacho).toLocaleString("es-CL")}` : ""}<br>${t.fecha_recepcion ? `Recepción: ${new Date(t.fecha_recepcion).toLocaleString("es-CL")}` : ""}</td>
        <td><div class="acciones-fila">${acciones(t)}</div></td>
    </tr>`).join("");
}

async function cargar() {
    const estado = $("filtro-estado").value;
    render(await pedir(`${cfg.api}${estado ? `?estado=${encodeURIComponent(estado)}` : ""}`));
}

async function cargarCatalogos() {
    const [bodegas, productos] = await Promise.all([pedir(cfg.bodegas), pedir(cfg.productos)]);
    const opcionesBodega = (bodegas.bodegas || []).filter((b) => b.activa).map((b) => `<option value="${b.id}">${esc(b.sucursal_nombre)} · ${esc(b.nombre)}</option>`).join("");
    $("origen").innerHTML = opcionesBodega;
    $("destino").innerHTML = opcionesBodega;
    $("producto").innerHTML = (productos.productos || []).map((p) => `<option value="${p.id}">${esc(p.codigo)} · ${esc(p.nombre)}</option>`).join("");
}

$("formulario-transferencia")?.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
        const seriales = $("seriales").value.split(/\r?\n|,/).map((s) => s.trim()).filter(Boolean);
        await pedir(cfg.api, { method: "POST", body: JSON.stringify({ numero: $("numero").value, bodega_origen_id: Number($("origen").value), bodega_destino_id: Number($("destino").value), items: [{ producto_id: Number($("producto").value), cantidad: $("cantidad").value, seriales }], observaciones: $("observaciones").value }) });
        evento.target.reset(); $("formulario-panel").hidden = true; await cargar(); avisar("Transferencia creada.");
    } catch (e) { avisar(e.message, true); }
});

$("lista-transferencias").addEventListener("click", async (evento) => {
    const boton = evento.target.closest("[data-accion]"); if (!boton) return;
    const accion = boton.dataset.accion;
    const cuerpo = accion === "cancelar" ? { motivo: window.prompt("Motivo de cancelación:", "Cancelada por el usuario") || "Cancelada por el usuario" } : {};
    try { await pedir(`${cfg.api}/${boton.dataset.id}/${accion}`, { method: "POST", body: JSON.stringify(cuerpo) }); await cargar(); avisar(`Transferencia ${accion === "recibir" ? "recibida" : accion === "despachar" ? "despachada" : accion === "solicitar" ? "solicitada" : "cancelada"}.`); } catch (e) { avisar(e.message, true); }
});

$("abrir-formulario")?.addEventListener("click", () => { $("formulario-panel").hidden = false; });
$("cerrar-formulario")?.addEventListener("click", () => { $("formulario-panel").hidden = true; });
$("actualizar").addEventListener("click", cargar);
$("filtro-estado").addEventListener("change", cargar);
Promise.all([cargarCatalogos(), cargar()]).catch((e) => avisar(e.message, true));
