"use strict";
const api = document.body.dataset.api;
const esc = (v) => String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
function parametros() { return new URLSearchParams(new FormData(document.getElementById("filtros"))); }
async function cargar() {
    const consulta = parametros(); const respuesta = await fetch(`${api}?${consulta}`); const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.mensaje);
    const selector = document.querySelector('[name="usuario_id"]'); const elegido = selector.value;
    selector.innerHTML = '<option value="">Todos</option>' + datos.usuarios.map((u) => `<option value="${u.id}">${esc(u.nombre)}</option>`).join(""); selector.value = elegido;
    document.getElementById("resumen").textContent = `${datos.auditoria.length} registro(s)`;
    document.getElementById("registros").innerHTML = datos.auditoria.map((r) => `<tr><td>${new Date(r.fecha).toLocaleString("es-CL")}</td><td>${esc(r.usuario)}</td><td><strong>${esc(r.modulo)}</strong><br>${esc(r.accion)}</td><td>${esc(r.entidad_tipo)} #${esc(r.entidad_id)}</td><td><details><summary>Ver</summary><pre>${esc(JSON.stringify(r.datos_nuevos, null, 2))}</pre></details></td><td>${esc(r.ip)}</td></tr>`).join("");
    document.getElementById("exportar").href = `${api}/exportar.csv?${consulta}`;
}
document.getElementById("filtros").addEventListener("submit", (e) => { e.preventDefault(); cargar().catch((error) => alert(error.message)); });
cargar().catch((error) => alert(error.message));
