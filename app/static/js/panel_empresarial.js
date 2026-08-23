"use strict";

const API = Object.freeze({
    productos: "/api/reportes/productos",
    stock: "/api/reportes/stock",
    alertas: "/api/alertas",
    dineroDormido: "/api/reportes/dinero-dormido",
});

const contexto = Object.freeze({
    bodegaId: Number(document.body.dataset.bodegaId),
    sucursalId: Number(document.body.dataset.sucursalId),
});

function elemento(id) {
    return document.getElementById(id);
}

function limpiar(nodo) {
    while (nodo?.firstChild) {
        nodo.removeChild(nodo.firstChild);
    }
}

function crearElemento(etiqueta, texto = "", clase = "") {
    const nodo = document.createElement(etiqueta);

    if (texto !== "") {
        nodo.textContent = String(texto);
    }

    if (clase) {
        nodo.className = clase;
    }

    return nodo;
}

function asignarTexto(id, valor) {
    const destino = elemento(id);

    if (destino) {
        destino.textContent = valor ?? "—";
        destino.classList.remove("metrica--actualizada");
        window.requestAnimationFrame(() => {
            destino.classList.add("metrica--actualizada");
        });
    }
}

function prepararBienvenida() {
    const ahora = new Date();
    const hora = ahora.getHours();
    const saludo = hora < 12
        ? "Buenos días"
        : hora < 20
            ? "Buenas tardes"
            : "Buenas noches";

    asignarTexto("saludo-panel", saludo);
    asignarTexto(
        "fecha-panel",
        new Intl.DateTimeFormat("es-CL", {
            weekday: "long",
            day: "numeric",
            month: "long",
        }).format(ahora)
    );
}

function actualizarSalud(filasStock, alertas) {
    const criticas = alertas.filter(
        (alerta) => ["critica", "alta"].includes(alerta.prioridad)
    ).length;
    const agotados = filasStock.filter(
        (fila) => Number(fila.disponible || 0) <= 0
    ).length;
    const penalizacion = Math.min(55, (criticas * 9) + (agotados * 5));
    const salud = Math.max(45, 100 - penalizacion);

    asignarTexto("salud-inventario", `${salud}%`);
    asignarTexto(
        "resumen-salud",
        salud >= 90
            ? "Todo se ve estable. Buen momento para planificar."
            : salud >= 70
                ? `${criticas + agotados} prioridad(es) merecen revisión.`
                : "Hay situaciones críticas que requieren atención hoy."
    );
}

function formatearNumero(valor, decimales = 0) {
    return new Intl.NumberFormat("es-CL", {
        minimumFractionDigits: 0,
        maximumFractionDigits: decimales,
    }).format(Number(valor || 0));
}

function formatearDinero(valor, moneda = "CLP") {
    return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: moneda,
        maximumFractionDigits: moneda === "CLP" ? 0 : 2,
    }).format(Number(valor || 0));
}

function notificar(mensaje) {
    const notificacion = elemento("notificacion");

    if (!notificacion) {
        return;
    }

    notificacion.textContent = mensaje;
    notificacion.hidden = false;

    window.clearTimeout(notificar.temporizador);

    notificar.temporizador = window.setTimeout(() => {
        notificacion.hidden = true;
    }, 4500);
}

async function solicitarJson(url) {
    const respuesta = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: {
            Accept: "application/json",
        },
    });

    let datos = {};

    try {
        datos = await respuesta.json();
    } catch {
        datos = {};
    }

    if (!respuesta.ok) {
        throw new Error(
            datos.mensaje ||
            datos.error ||
            `La solicitud falló con estado ${respuesta.status}.`
        );
    }

    return datos;
}

function mostrarCargaStock() {
    const cuerpo = elemento("tabla-stock");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando inventario…",
        "estado-carga"
    );

    celda.colSpan = 5;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function mostrarErrorStock(mensaje) {
    const cuerpo = elemento("tabla-stock");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje || "No fue posible cargar el inventario.",
        "tabla__vacio"
    );

    celda.colSpan = 5;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function renderizarStock(filas) {
    const cuerpo = elemento("tabla-stock");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!filas.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No existe inventario registrado en esta bodega.",
            "tabla__vacio"
        );

        celda.colSpan = 5;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    filas.slice(0, 8).forEach((inventario) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento("td", inventario.producto || "—")
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearNumero(inventario.cantidad, 3)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearNumero(inventario.reservada, 3)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearNumero(inventario.disponible, 3)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(inventario.valor)
            )
        );

        cuerpo.appendChild(fila);
    });
}

function clasePrioridad(prioridad) {
    if (prioridad === "critica" || prioridad === "alta") {
        return "insignia insignia--peligro";
    }

    if (prioridad === "media") {
        return "insignia insignia--advertencia";
    }

    return "insignia";
}

function renderizarAlertas(alertas) {
    const lista = elemento("lista-alertas");

    if (!lista) {
        return;
    }

    limpiar(lista);

    if (!alertas.length) {
        lista.appendChild(
            crearElemento(
                "li",
                "No existen alertas activas.",
                "estado-carga"
            )
        );
        return;
    }

    alertas.slice(0, 8).forEach((alerta) => {
        const item = crearElemento("li", "", "lista__item");

        const punto = crearElemento(
            "span",
            "",
            "lista__punto"
        );

        punto.setAttribute("aria-hidden", "true");

        const contenido = crearElemento("div");

        const cabecera = crearElemento("div");
        cabecera.appendChild(
            crearElemento(
                "p",
                alerta.titulo || "Alerta de inventario",
                "lista__titulo"
            )
        );

        cabecera.appendChild(
            crearElemento(
                "span",
                alerta.prioridad || "sin prioridad",
                clasePrioridad(alerta.prioridad)
            )
        );

        contenido.appendChild(cabecera);

        contenido.appendChild(
            crearElemento(
                "p",
                alerta.mensaje || "Sin detalles.",
                "lista__detalle"
            )
        );

        item.appendChild(punto);
        item.appendChild(contenido);
        lista.appendChild(item);
    });
}

async function cargarPanel() {
    mostrarCargaStock();

    const listaAlertas = elemento("lista-alertas");

    if (listaAlertas) {
        limpiar(listaAlertas);
        listaAlertas.appendChild(
            crearElemento(
                "li",
                "Cargando alertas…",
                "estado-carga"
            )
        );
    }

    try {
        const [productos, stock, alertas, dineroDormido] = await Promise.all([
            solicitarJson(API.productos),
            solicitarJson(
                `${API.stock}?bodega_id=${encodeURIComponent(contexto.bodegaId)}`
            ),
            solicitarJson(
                `${API.alertas}?estado=activa&bodega_id=${encodeURIComponent(contexto.bodegaId)}`
            ),
            elemento("metrica-dinero-dormido")
                ? solicitarJson(`${API.dineroDormido}?bodega_id=${encodeURIComponent(contexto.bodegaId)}`)
                : Promise.resolve(null),
        ]);

        const filasStock = stock.stock || [];
        const alertasActivas = alertas.alertas || [];

        const unidadesDisponibles = filasStock.reduce(
            (total, fila) => total + Number(fila.disponible || 0),
            0
        );

        const valorInventario = filasStock.reduce(
            (total, fila) => total + Number(fila.valor || 0),
            0
        );

        asignarTexto(
            "metrica-productos",
            formatearNumero((productos.productos || []).length)
        );

        actualizarSalud(filasStock, alertasActivas);

        asignarTexto(
            "metrica-stock",
            formatearNumero(unidadesDisponibles, 3)
        );

        asignarTexto(
            "metrica-valor",
            formatearDinero(valorInventario)
        );

        asignarTexto(
            "metrica-alertas",
            formatearNumero(alertasActivas.length)
        );

        if (dineroDormido) {
            asignarTexto("metrica-dinero-dormido", formatearDinero(dineroDormido.monto));
            asignarTexto(
                "detalle-dinero-dormido",
                dineroDormido.productos
                    ? `${formatearNumero(dineroDormido.productos)} producto(s) · ${formatearNumero(dineroDormido.unidades, 3)} unidades inmovilizadas`
                    : "Sin capital inmovilizado según las reglas actuales"
            );
        }

        renderizarStock(filasStock);
        renderizarAlertas(alertasActivas);
    } catch (error) {
        mostrarErrorStock(error.message);
        renderizarAlertas([]);
        notificar(error.message);
    }
}

function abrirMenu() {
    document.body.classList.add("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "true");
}

function cerrarMenu() {
    document.body.classList.remove("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "false");
}

function registrarEventos() {
    elemento("actualizar-panel")?.addEventListener(
        "click",
        cargarPanel
    );

    elemento("abrir-menu")?.addEventListener(
        "click",
        abrirMenu
    );

    elemento("cerrar-menu")?.addEventListener(
        "click",
        cerrarMenu
    );

    window.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape") {
            cerrarMenu();
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    prepararBienvenida();
    registrarEventos();
    cargarPanel();
});
