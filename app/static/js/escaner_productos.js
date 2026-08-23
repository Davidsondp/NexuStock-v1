"use strict";

(() => {
    const abrir = document.getElementById("escanear-producto");
    const modal = document.getElementById("modal-escaner");
    if (!abrir || !modal) return;

    const video = document.getElementById("video-escaner");
    const estado = document.getElementById("estado-escaner");
    const entrada = document.getElementById("codigo-escaner-manual");
    let flujo = null;
    let detector = null;
    let activo = false;
    let fotograma = null;

    function informar(texto, error = false) {
        estado.textContent = texto;
        estado.classList.toggle("nx-escaner__error", error);
    }

    function buscar(codigo) {
        const valor = String(codigo || "").trim();
        if (!valor) {
            informar("Ingresa un código válido.", true);
            entrada.focus();
            return;
        }
        cerrar();
        window.NexuStockProductos?.buscar(valor);
    }

    async function detectar() {
        if (!activo || !detector || video.readyState < 2) {
            if (activo) fotograma = requestAnimationFrame(detectar);
            return;
        }
        try {
            const codigos = await detector.detect(video);
            if (codigos.length) {
                buscar(codigos[0].rawValue);
                return;
            }
        } catch {
            informar("No pudimos leer este cuadro. Mantén el código estable.");
        }
        if (activo) fotograma = requestAnimationFrame(detectar);
    }

    async function iniciar() {
        modal.hidden = false;
        entrada.value = "";
        informar("Solicitando acceso a la cámara…");

        if (!("mediaDevices" in navigator) || !navigator.mediaDevices.getUserMedia) {
            informar("La cámara no está disponible. Usa el ingreso manual o un lector USB.", true);
            entrada.focus();
            return;
        }

        try {
            flujo = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" } },
                audio: false,
            });
            video.srcObject = flujo;
            await video.play();
            activo = true;

            if ("BarcodeDetector" in window) {
                detector = new BarcodeDetector({
                    formats: ["ean_13", "ean_8", "code_128", "code_39", "upc_a", "upc_e", "qr_code"],
                });
                informar("Alinea el código dentro del marco.");
                detectar();
            } else {
                informar("Tu navegador no admite lectura automática. Usa el campo manual o un lector USB.");
                entrada.focus();
            }
        } catch {
            informar("No se pudo abrir la cámara. Revisa el permiso del navegador o usa el campo manual.", true);
            entrada.focus();
        }
    }

    function cerrar() {
        activo = false;
        if (fotograma) cancelAnimationFrame(fotograma);
        flujo?.getTracks().forEach((pista) => pista.stop());
        flujo = null;
        video.srcObject = null;
        modal.hidden = true;
    }

    abrir.addEventListener("click", iniciar);
    document.getElementById("cerrar-escaner")?.addEventListener("click", cerrar);
    document.getElementById("buscar-codigo-manual")?.addEventListener("click", () => buscar(entrada.value));
    entrada.addEventListener("keydown", (evento) => {
        if (evento.key === "Enter") {
            evento.preventDefault();
            buscar(entrada.value);
        }
    });
    modal.addEventListener("click", (evento) => {
        if (evento.target === modal) cerrar();
    });
    document.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape" && !modal.hidden) cerrar();
    });
})();
