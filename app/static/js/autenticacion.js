"use strict";

const NOMBRE_CABECERA_CSRF = "X-CSRFToken";

const IDENTIFICADORES_ALTERNADORES = Object.freeze([
    "alternar-password",
    "alternar-confirmacion",
]);

function alternarVisibilidad(boton) {
    const objetivoId = boton.dataset.alternarPassword;
    const campo = document.getElementById(objetivoId);

    if (!campo) {
        return;
    }

    const mostrar = campo.type === "password";

    campo.type = mostrar ? "text" : "password";
    boton.textContent = mostrar ? "Ocultar" : "Mostrar";
    boton.setAttribute(
        "aria-pressed",
        mostrar ? "true" : "false",
    );
    boton.setAttribute(
        "aria-label",
        mostrar
            ? "Ocultar contraseña"
            : "Mostrar contraseña",
    );
}

function configurarAlternadores() {
    for (
        const identificador
        of IDENTIFICADORES_ALTERNADORES
    ) {
        const boton = document.getElementById(
            identificador,
        );

        if (!boton) {
            continue;
        }

        boton.addEventListener(
            "click",
            () => alternarVisibilidad(boton),
        );
    }
}

function configurarEnvio() {
    for (
        const formulario of document.querySelectorAll(
            ".formulario-autenticacion",
        )
    ) {
        formulario.addEventListener(
            "submit",
            () => {
                const boton = formulario.querySelector(
                    "[type='submit']",
                );

                if (boton) {
                    boton.disabled = true;
                    boton.setAttribute(
                        "aria-busy",
                        "true",
                    );
                }
            },
        );
    }
}

function configurarRegistroGuiado() {
    const formulario = document.getElementById("formulario-registro");
    if (!formulario) return;

    const secciones = [...formulario.querySelectorAll("[data-paso]")];
    const indicadores = [...document.querySelectorAll("[data-ir-paso]")];
    const anterior = document.getElementById("registro-anterior");
    const siguiente = document.getElementById("registro-siguiente");
    const enviar = document.getElementById("registro-enviar");
    const conError = secciones.find((seccion) => seccion.querySelector(".campo__error"));
    let paso = Number(conError?.dataset.paso || 1);

    function mostrar(numero) {
        paso = Math.max(1, Math.min(numero, secciones.length));
        secciones.forEach((seccion) => {
            seccion.hidden = Number(seccion.dataset.paso) !== paso;
        });
        indicadores.forEach((indicador) => {
            const numeroIndicador = Number(indicador.dataset.irPaso);
            indicador.classList.toggle("registro-progreso__paso--activo", numeroIndicador === paso);
            indicador.classList.toggle("registro-progreso__paso--completo", numeroIndicador < paso);
            indicador.setAttribute("aria-current", numeroIndicador === paso ? "step" : "false");
        });
        anterior.hidden = paso === 1;
        siguiente.hidden = paso === secciones.length;
        enviar.hidden = paso !== secciones.length;
        document.querySelector(".tarjeta-autenticacion")?.scrollIntoView({behavior: "smooth", block: "start"});
    }

    function pasoValido() {
        const campos = [...secciones[paso - 1].querySelectorAll("input, select, textarea")];
        const invalido = campos.find((campo) => !campo.checkValidity());
        if (invalido) {
            invalido.reportValidity();
            invalido.focus();
            return false;
        }
        return true;
    }

    siguiente.addEventListener("click", () => {
        if (pasoValido()) mostrar(paso + 1);
    });
    anterior.addEventListener("click", () => mostrar(paso - 1));
    indicadores.forEach((indicador) => {
        indicador.addEventListener("click", () => {
            const destino = Number(indicador.dataset.irPaso);
            if (destino <= paso || pasoValido()) mostrar(destino);
        });
    });
    mostrar(paso);
}

function tokenCsrf() {
    return document.querySelector(
        "meta[name='csrf-token']",
    )?.content || "";
}

window.NexuStockAutenticacion = Object.freeze({
    nombreCabeceraCsrf: NOMBRE_CABECERA_CSRF,
    tokenCsrf,
});

document.addEventListener(
    "DOMContentLoaded",
    () => {
        configurarAlternadores();
        configurarRegistroGuiado();
        configurarEnvio();
    },
);
