"use strict";
const api = document.body.dataset.api;
const token = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
async function pedir(url, opciones = {}) {
    const headers = { Accept: "application/json", ...(opciones.headers || {}) };
    if (opciones.body) headers["Content-Type"] = "application/json";
    if (token()) headers["X-CSRFToken"] = token();
    const respuesta = await fetch(url, { credentials: "same-origin", ...opciones, headers });
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible guardar.");
    return datos;
}
function mensaje(texto, error = false) {
    const nodo = document.getElementById("mensaje");
    nodo.textContent = texto; nodo.classList.toggle("error", error); nodo.hidden = false;
    setTimeout(() => { nodo.hidden = true; }, 3500);
}
function asignar(formulario, datos) {
    Object.entries(datos).forEach(([nombre, valor]) => {
        const campo = formulario.elements.namedItem(nombre); if (!campo) return;
        if (campo.type === "checkbox") campo.checked = Boolean(valor); else campo.value = valor ?? "";
    });
}
function mostrar(datos) {
    asignar(document.getElementById("empresa"), datos.empresa);
    asignar(document.getElementById("preferencias"), { ...datos.preferencias, ...(datos.preferencias.opciones || {}) });
    document.getElementById("plan").textContent = `Plan ${datos.suscripcion.plan} · ${datos.suscripcion.estado}`;
}
function extraer(formulario) {
    return Object.fromEntries(Array.from(formulario.elements).filter((c) => c.name).map((c) => [c.name, c.type === "checkbox" ? c.checked : c.value]));
}
document.getElementById("empresa").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try { mostrar(await pedir(`${api}/empresa`, { method: "PATCH", body: JSON.stringify(extraer(evento.target)) })); mensaje("Datos empresariales actualizados."); } catch (error) { mensaje(error.message, true); }
});
document.getElementById("preferencias").addEventListener("submit", async (evento) => {
    evento.preventDefault(); const datos = extraer(evento.target);
    datos.opciones = { mostrar_costos_dashboard: datos.mostrar_costos_dashboard, mostrar_stock_cero: datos.mostrar_stock_cero, decimales_cantidad: Number(datos.decimales_cantidad), formato_fecha: datos.formato_fecha };
    ["mostrar_costos_dashboard", "mostrar_stock_cero", "decimales_cantidad", "formato_fecha"].forEach((clave) => delete datos[clave]);
    datos.dias_sin_movimiento = Number(datos.dias_sin_movimiento);
    try { mostrar(await pedir(`${api}/preferencias`, { method: "PATCH", body: JSON.stringify(datos) })); mensaje("Preferencias actualizadas."); } catch (error) { mensaje(error.message, true); }
});
pedir(api).then(mostrar).catch((error) => mensaje(error.message, true));
