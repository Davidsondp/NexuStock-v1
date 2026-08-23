"use strict";
const apiReportes = document.body.dataset.api;
const csrfReportes = document.querySelector('meta[name="csrf-token"]').content;
async function pedirReporte(url, opciones = {}) {
    const headers = { Accept: "application/json", "X-CSRFToken": csrfReportes };
    if (opciones.body) headers["Content-Type"] = "application/json";
    const respuesta = await fetch(url, { ...opciones, headers });
    if (respuesta.status === 204) return {};
    const datos = await respuesta.json();
    if (!respuesta.ok) throw new Error(datos.mensaje || "No fue posible completar la operación");
    return datos;
}
function botonReporte(texto, atributo, id) {
    const boton = document.createElement("button"); boton.type = "button"; boton.textContent = texto; boton.dataset[atributo] = String(id); return boton;
}
async function cargarReportes() {
    const datos = await pedirReporte(apiReportes), lista = document.getElementById("lista"); lista.replaceChildren();
    for (const reporte of datos.reportes || []) {
        const tarjeta = document.createElement("article"); tarjeta.className = "tarjeta";
        const titulo = document.createElement("h2"); titulo.textContent = reporte.nombre;
        const tipo = document.createElement("p"); tipo.textContent = reporte.tipo;
        tarjeta.append(titulo, tipo, botonReporte("Ejecutar", "ejecutar", reporte.id), document.createTextNode(" "), botonReporte("Eliminar", "eliminar", reporte.id)); lista.append(tarjeta);
    }
}
document.getElementById("crear").addEventListener("submit", async (evento) => { evento.preventDefault(); const f = new FormData(evento.target); await pedirReporte(apiReportes, { method: "POST", body: JSON.stringify({ nombre: f.get("nombre"), tipo: f.get("tipo"), configuracion: {} }) }); evento.target.reset(); await cargarReportes(); });
document.getElementById("lista").addEventListener("click", async (evento) => { const b = evento.target.closest("button"); if (!b) return; if (b.dataset.ejecutar) { const d = await pedirReporte(`${apiReportes}/${b.dataset.ejecutar}/ejecutar`), salida = document.getElementById("resultado"); salida.hidden = false; salida.querySelector("pre").textContent = JSON.stringify(d.datos, null, 2); } if (b.dataset.eliminar) { await pedirReporte(`${apiReportes}/${b.dataset.eliminar}`, { method: "DELETE" }); await cargarReportes(); } });
cargarReportes();
