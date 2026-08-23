"use strict";
(() => {
    const boton = document.getElementById("alternar-ubicacion");
    if (!boton) return;
    const api = document.body.dataset.apiUbicacion;
    let compartiendo = document.body.dataset.ubicacionConsentida === "true";
    let seguimiento = null;
    const csrf = () => document.querySelector('input[name="csrf_token"]')?.value || "";
    const texto = (mensaje) => { document.getElementById("ubicacion-estado").textContent = mensaje; document.getElementById("ubicacion-titulo").textContent = compartiendo ? "Dejar de compartir ubicación" : "Compartir mi ubicación"; };
    async function enviar(posicion) {
        const respuesta = await fetch(api, { method: "PATCH", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify({ consentimiento: true, latitud: posicion.coords.latitude, longitud: posicion.coords.longitude, precision_m: posicion.coords.accuracy }) });
        const datos = await respuesta.json().catch(() => ({})); if (!respuesta.ok) throw new Error(datos.mensaje || "No se pudo compartir la ubicación");
        compartiendo = true; texto(`Compartida · precisión aproximada ±${Math.round(posicion.coords.accuracy)} m`);
    }
    function iniciar() {
        if (!navigator.geolocation) { texto("Este navegador no permite geolocalización"); return; }
        if (seguimiento !== null) navigator.geolocation.clearWatch(seguimiento);
        texto("Esperando autorización del navegador…");
        seguimiento = navigator.geolocation.watchPosition(p => enviar(p).catch(e => texto(e.message)), e => texto(e.code === 1 ? "Permiso de ubicación denegado" : "No se pudo obtener la ubicación"), { enableHighAccuracy: true, maximumAge: 30000, timeout: 20000 });
    }
    async function detener() {
        const respuesta = await fetch(api, { method: "DELETE", credentials: "same-origin", headers: { "X-CSRFToken": csrf() } });
        if (!respuesta.ok) throw new Error("No se pudo revocar la ubicación");
        if (seguimiento !== null) navigator.geolocation.clearWatch(seguimiento); seguimiento = null; compartiendo = false; texto("Opcional, visible y revocable");
    }
    boton.addEventListener("click", () => { if (compartiendo) detener().catch(e => texto(e.message)); else if (confirm("NexuStock guardará tu última ubicación mientras este panel esté abierto. Puedes revocar el permiso en cualquier momento. ¿Continuar?")) iniciar(); });
    if (compartiendo) iniciar();
})();
