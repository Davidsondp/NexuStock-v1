"use strict";

(() => {
    const abrir = document.getElementById(
        "escanear-producto"
    );
    const modal = document.getElementById(
        "modal-escaner"
    );

    if (!abrir || !modal) {
        return;
    }

    const video = document.getElementById(
        "video-escaner"
    );
    const estado = document.getElementById(
        "estado-escaner"
    );
    const entrada = document.getElementById(
        "codigo-escaner-manual"
    );

    let escaner = null;

    function informar(
        texto,
        error = false
    ) {
        estado.textContent = texto;
        estado.classList.toggle(
            "nx-escaner__error",
            error,
        );
    }

    function cerrar() {
        escaner?.detener();
        modal.hidden = true;
    }

    function buscar(codigo) {
        const valor = String(
            codigo || ""
        ).trim();

        if (!valor) {
            informar(
                "Ingresa un c\u00f3digo "
                + "v\u00e1lido.",
                true,
            );
            entrada.focus();
            return false;
        }

        cerrar();

        window.NexuStockProductos
            ?.buscar(valor);

        return true;
    }

    function obtenerEscaner() {
        if (escaner) {
            return escaner;
        }

        escaner = NexuEscaner.crear({
            video,
            alDetectar: buscar,
            alInformar: informar,
        });

        return escaner;
    }

    async function iniciar() {
        modal.hidden = false;
        entrada.value = "";

        informar(
            "Solicitando acceso a la "
            + "c\u00e1mara\u2026"
        );

        await obtenerEscaner().iniciar();
    }

    abrir.addEventListener(
        "click",
        iniciar,
    );

    document.getElementById(
        "cerrar-escaner"
    )?.addEventListener(
        "click",
        cerrar,
    );

    document.getElementById(
        "buscar-codigo-manual"
    )?.addEventListener(
        "click",
        () => buscar(entrada.value),
    );

    entrada.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                buscar(entrada.value);
            }
        },
    );

    modal.addEventListener(
        "click",
        (evento) => {
            if (evento.target === modal) {
                cerrar();
            }
        },
    );

    document.addEventListener(
        "keydown",
        (evento) => {
            if (
                evento.key === "Escape"
                && !modal.hidden
            ) {
                cerrar();
            }
        },
    );

    globalThis.addEventListener(
        "pagehide",
        cerrar,
    );
})();
