"use strict";

const cuerpo = document.body;

const registroBase = (
    cuerpo.dataset.registroBase
);

const selectorCiclo = document.getElementById(
    "selector-ciclo-publico",
);
const selectorProveedor = document.getElementById("selector-proveedor-publico");

const planesComerciales = document.getElementById(
    "planes-comerciales",
);

const comparacionPublica = document.getElementById(
    "comparacion-publica",
);

const ctaMovilPlanes = document.getElementById(
    "cta-movil-planes",
);

const estado = {
    ciclo: "mensual",
    proveedor: "webpay",
};

function moneda(valor) {
    return new Intl.NumberFormat(
        "es-CL",
        {
            style: "currency",
            currency: "CLP",
            maximumFractionDigits: 0,
        },
    ).format(valor);
}

function precioVisible(elementoPrecio) {
    const mensual = Number(
        elementoPrecio.dataset.precioMensual,
    );

    const anual = Number(
        elementoPrecio.dataset.precioAnual,
    );

    if (estado.ciclo === "anual") {
        return {
            precio: anual / 12,
            detalle: "/ mes, facturado anual",
        };
    }

    return {
        precio: mensual,
        detalle: "/ mes",
    };
}

function actualizarPrecios() {
    for (
        const elementoPrecio
        of document.querySelectorAll(
            ".plan-publico__precio[data-precio-mensual]",
        )
    ) {
        const resultado = precioVisible(
            elementoPrecio,
        );

        elementoPrecio.querySelector(
            "strong",
        ).textContent = moneda(
            resultado.precio,
        );

        elementoPrecio.querySelector(
            "span",
        ).textContent = resultado.detalle;

        elementoPrecio.dataset.ciclo = (
            estado.ciclo
        );
    }
}

function urlRegistro(plan) {
    const parametros = new URLSearchParams({
        plan,
        ciclo: estado.ciclo,
        proveedor: estado.proveedor,
    });

    return (
        registroBase
        + "?"
        + parametros.toString()
    );
}

function actualizarEnlacesRegistro() {
    for (
        const enlace
        of document.querySelectorAll(
            "a[data-plan]:not([data-cotizacion])",
        )
    ) {
        const plan = enlace.dataset.plan;

        if (!plan) {
            continue;
        }

        enlace.href = urlRegistro(plan);
        enlace.dataset.ciclo = estado.ciclo;
    }
}

function seleccionarCiclo(
    ciclo,
) {
    estado.ciclo = ciclo;

    for (
        const boton
        of selectorCiclo.querySelectorAll(
            "[data-ciclo]",
        )
    ) {
        const activo = (
            boton.dataset.ciclo === ciclo
        );

        boton.setAttribute(
            "aria-pressed",
            String(activo),
        );
    }

    actualizarPrecios();
    actualizarEnlacesRegistro();
}

function registrarSelectorCiclo() {
    selectorCiclo.addEventListener(
        "click",
        (evento) => {
            const boton = evento.target.closest(
                "[data-ciclo]",
            );

            if (!boton) {
                return;
            }

            seleccionarCiclo(
                boton.dataset.ciclo,
            );
        },
    );
}

function registrarSelectorProveedor() {
    selectorProveedor?.addEventListener("click", (evento) => {
        const boton = evento.target.closest("[data-proveedor]");
        if (!boton) return;
        estado.proveedor = boton.dataset.proveedor;
        for (const opcion of selectorProveedor.querySelectorAll("[data-proveedor]")) {
            opcion.setAttribute("aria-pressed", String(opcion === boton));
        }
        actualizarEnlacesRegistro();
    });
}

function registrarPreguntas() {
    const preguntas = (
        document.querySelectorAll(
            ".preguntas-planes details",
        )
    );

    for (const pregunta of preguntas) {
        pregunta.addEventListener(
            "toggle",
            () => {
                if (!pregunta.open) {
                    return;
                }

                for (const otra of preguntas) {
                    if (otra !== pregunta) {
                        otra.open = false;
                    }
                }
            },
        );
    }
}

function activarAnimaciones() {
    const elementos = document.querySelectorAll(
        [
            ".plan-publico",
            ".comparacion-publica__grupos article",
            ".preguntas-planes details",
            ".demostracion-producto",
        ].join(","),
    );

    if (
        window.matchMedia(
            "(prefers-reduced-motion: reduce)",
        ).matches
    ) {
        for (const elemento of elementos) {
            elemento.classList.add(
                "elemento-visible",
            );
        }

        return;
    }

    const observador = new IntersectionObserver(
        (entradas) => {
            for (const entrada of entradas) {
                if (!entrada.isIntersecting) {
                    continue;
                }

                entrada.target.classList.add(
                    "elemento-visible",
                );

                observador.unobserve(
                    entrada.target,
                );
            }
        },
        {
            threshold: 0.14,
            rootMargin: "0px 0px -30px",
        },
    );

    for (const elemento of elementos) {
        observador.observe(elemento);
    }
}

function controlarCtaMovil() {
    if (!ctaMovilPlanes) {
        return;
    }

    const portada = document.getElementById(
        "portada-planes",
    );

    const ctaFinal = document.getElementById(
        "cta-final-planes",
    );

    const observador = new IntersectionObserver(
        (entradas) => {
            for (const entrada of entradas) {
                if (
                    entrada.target === portada
                ) {
                    ctaMovilPlanes.classList.toggle(
                        "cta-movil-planes--visible",
                        !entrada.isIntersecting,
                    );
                }

                if (
                    entrada.target === ctaFinal
                    && entrada.isIntersecting
                ) {
                    ctaMovilPlanes.classList.remove(
                        "cta-movil-planes--visible",
                    );
                }
            }
        },
        {
            threshold: 0.15,
        },
    );

    observador.observe(portada);
    observador.observe(ctaFinal);
}

function resaltarPlanDesdeUrl() {
    const parametros = new URLSearchParams(
        window.location.search,
    );

    const plan = parametros.get("plan");
    const ciclo = parametros.get("ciclo");
    const proveedor = parametros.get("proveedor");

    if (
        ciclo === "mensual"
        || ciclo === "anual"
    ) {
        estado.ciclo = ciclo;
    }
    if (["webpay", "mercadopago"].includes(proveedor)) {
        estado.proveedor = proveedor;
        for (const opcion of selectorProveedor?.querySelectorAll("[data-proveedor]") || []) {
            opcion.setAttribute("aria-pressed", String(opcion.dataset.proveedor === proveedor));
        }
    }

    if (!plan) {
        return;
    }

    const tarjeta = planesComerciales.querySelector(
        `[data-plan="${plan}"]`,
    );

    tarjeta?.classList.add(
        "plan-publico--seleccionado",
    );
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        resaltarPlanDesdeUrl();
        registrarSelectorCiclo();
        registrarSelectorProveedor();
        registrarPreguntas();
        seleccionarCiclo(estado.ciclo);
        activarAnimaciones();
        controlarCtaMovil();
    },
);
