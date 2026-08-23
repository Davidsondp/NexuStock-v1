"use strict";

const configuracion = Object.freeze({
    apiAlertas: document.body.dataset.apiAlertas,
    permisoGestionar:
        document.body.dataset.permisoGestionar
        === "true",
});

const estado = {
    alertas: [],
};

const rutasAccion = Object.freeze({
    resolver: "/resolver",
    ignorar: "/ignorar",
});

const nombresTipo = Object.freeze({
    stock_bajo: "Stock bajo",
    sobrestock: "Sobrestock",
    riesgo_agotamiento: "Riesgo de agotamiento",
    sin_movimiento: "Sin movimiento",
    recomendacion_compra:
        "Recomendación de compra",
    lote_proximo_vencer:
        "Lote próximo a vencer",
    lote_vence_hoy: "Lote vence hoy",
    lote_vencido: "Lote vencido",
});

const nombresPrioridad = Object.freeze({
    baja: "Baja",
    media: "Media",
    alta: "Alta",
    critica: "Crítica",
});

function elemento(id) {
    return document.getElementById(id);
}

function crearElemento(
    etiqueta,
    clase = "",
    texto = "",
) {
    const nodo = document.createElement(etiqueta);

    if (clase) {
        nodo.className = clase;
    }

    if (texto) {
        nodo.textContent = texto;
    }

    return nodo;
}

function limpiar(nodo) {
    nodo.replaceChildren();
}

function obtenerTokenCsrf() {
    return (
        document.querySelector(
            'input[name="csrf_token"]'
        )?.value
        || ""
    );
}

function notificar(
    mensaje,
    tipo = "exito",
) {
    const contenedor = elemento("notificacion");

    if (!contenedor) {
        return;
    }

    contenedor.textContent = mensaje;
    contenedor.className = (
        `notificacion notificacion--${tipo}`
    );
    contenedor.hidden = false;

    window.clearTimeout(
        notificar.temporizador
    );

    notificar.temporizador = window.setTimeout(
        () => {
            contenedor.hidden = true;
        },
        3500,
    );
}

async function solicitarJson(
    url,
    opciones = {},
) {
    const respuesta = await fetch(
        url,
        {
            credentials: "same-origin",
            ...opciones,
        },
    );

    let datos = {};

    try {
        datos = await respuesta.json();
    }
    catch {
        datos = {};
    }

    if (!respuesta.ok) {
        throw new Error(
            datos.mensaje
            || datos.error
            || "No fue posible completar la operación.",
        );
    }

    return datos;
}

function normalizarListado(datos) {
    if (Array.isArray(datos)) {
        return datos;
    }

    if (Array.isArray(datos.alertas)) {
        return datos.alertas;
    }

    if (Array.isArray(datos.items)) {
        return datos.items;
    }

    return [];
}

function nombreTipo(tipo) {
    return (
        nombresTipo[tipo]
        || String(tipo || "Alerta")
            .replaceAll("_", " ")
    );
}

function nombrePrioridad(prioridad) {
    return (
        nombresPrioridad[prioridad]
        || prioridad
        || "Media"
    );
}

function fechaLegible(valor) {
    if (!valor) {
        return "";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return valor;
    }

    return fecha.toLocaleString(
        "es-CL",
        {
            dateStyle: "medium",
            timeStyle: "short",
        },
    );
}

function recomendacion(alerta) {
    if (alerta.recomendacion) {
        return alerta.recomendacion;
    }

    const recomendaciones = {
        stock_bajo:
            "Revisa el stock y considera crear una compra.",
        sobrestock:
            "Revisa la rotación o planifica una promoción.",
        riesgo_agotamiento:
            "Planifica la reposición del producto.",
        sin_movimiento:
            "Revisa la estrategia comercial del producto.",
        recomendacion_compra:
            "Evalúa la cantidad sugerida antes de comprar.",
        lote_proximo_vencer:
            "Revisa el lote y prioriza su salida.",
        lote_vence_hoy:
            "Revisa inmediatamente el lote afectado.",
        lote_vencido:
            "Aísla el lote vencido y revisa el inventario.",
    };

    return (
        recomendaciones[alerta.tipo]
        || "Revisa esta situación y toma una acción."
    );
}

function actualizarResumen() {
    const activas = estado.alertas.filter(
        (alerta) => alerta.estado === "activa"
    );

    const criticas = activas.filter(
        (alerta) => alerta.prioridad === "critica"
    );

    const altas = activas.filter(
        (alerta) => alerta.prioridad === "alta"
    );

    elemento(
        "resumen-alertas-activas"
    ).textContent = String(activas.length);

    elemento(
        "resumen-alertas-criticas"
    ).textContent = String(criticas.length);

    elemento(
        "resumen-alertas-altas"
    ).textContent = String(altas.length);
}

function crearBotonAccion(
    alerta,
    accion,
    texto,
    clase,
) {
    const boton = crearElemento(
        "button",
        clase,
        texto,
    );

    boton.type = "button";

    boton.addEventListener(
        "click",
        async () => {
            boton.disabled = true;

            try {
                await ejecutarAccion(
                    alerta.id,
                    accion,
                );
            }
            finally {
                boton.disabled = false;
            }
        },
    );

    return boton;
}

function crearTarjeta(alerta) {
    const prioridad = (
        alerta.prioridad || "media"
    );

    const tarjeta = crearElemento(
        "article",
        (
            "alerta-tarjeta "
            + `alerta-tarjeta--${prioridad}`
        ),
    );

    const contenido = crearElemento(
        "div",
        "alerta-tarjeta__contenido",
    );

    const encabezado = crearElemento(
        "div",
        "alerta-tarjeta__encabezado",
    );

    const tipo = crearElemento(
        "span",
        "alerta-etiqueta",
        nombreTipo(alerta.tipo),
    );

    const prioridadNodo = crearElemento(
        "span",
        (
            "alerta-prioridad "
            + `alerta-prioridad--${prioridad}`
        ),
        nombrePrioridad(prioridad),
    );

    encabezado.append(
        tipo,
        prioridadNodo,
    );

    const titulo = crearElemento(
        "h3",
        "",
        alerta.titulo || nombreTipo(alerta.tipo),
    );

    const mensaje = crearElemento(
        "p",
        "alerta-tarjeta__mensaje",
        alerta.mensaje || "Requiere revisión.",
    );

    const recomendacionNodo = crearElemento(
        "p",
        "alerta-tarjeta__recomendacion",
        recomendacion(alerta),
    );

    contenido.append(
        encabezado,
        titulo,
        mensaje,
        recomendacionNodo,
    );

    const fecha = fechaLegible(
        alerta.creado_en
        || alerta.fecha
    );

    if (fecha) {
        contenido.append(
            crearElemento(
                "time",
                "alerta-tarjeta__fecha",
                fecha,
            ),
        );
    }

    tarjeta.append(contenido);

    if (
        configuracion.permisoGestionar
        && alerta.estado === "activa"
    ) {
        const acciones = crearElemento(
            "div",
            "alerta-tarjeta__acciones",
        );

        acciones.append(
            crearBotonAccion(
                alerta,
                "resolver",
                "Resolver",
                "boton boton--primario boton--pequeno",
            ),
            crearBotonAccion(
                alerta,
                "ignorar",
                "Ignorar",
                "boton boton--secundario boton--pequeno",
            ),
        );

        tarjeta.append(acciones);
    }

    return tarjeta;
}

function renderizarAlertas() {
    const lista = elemento(
        "lista-alertas"
    );
    const mensajeEstado = elemento(
        "estado-alertas"
    );

    limpiar(lista);

    if (!estado.alertas.length) {
        mensajeEstado.textContent = (
            "No hay alertas para los filtros seleccionados."
        );
        mensajeEstado.hidden = false;
        actualizarResumen();
        return;
    }

    mensajeEstado.hidden = true;

    for (const alerta of estado.alertas) {
        lista.append(
            crearTarjeta(alerta)
        );
    }

    actualizarResumen();
}

async function cargarAlertas() {
    const mensajeEstado = elemento(
        "estado-alertas"
    );

    mensajeEstado.textContent = (
        "Cargando alertas..."
    );
    mensajeEstado.hidden = false;

    const parametros = new URLSearchParams();

    const filtroEstado = elemento(
        "filtro-estado-alertas"
    ).value;

    const filtroTipo = elemento(
        "filtro-tipo-alertas"
    ).value;

    if (filtroEstado) {
        parametros.set(
            "estado",
            filtroEstado,
        );
    }

    if (filtroTipo) {
        parametros.set(
            "tipo",
            filtroTipo,
        );
    }

    const sufijo = parametros.toString();
    const url = (
        configuracion.apiAlertas
        + (sufijo ? `?${sufijo}` : "")
    );

    try {
        const datos = await solicitarJson(url);
        estado.alertas = normalizarListado(datos);
        renderizarAlertas();
    }
    catch (error) {
        estado.alertas = [];
        actualizarResumen();

        mensajeEstado.textContent = error.message;
        mensajeEstado.hidden = false;

        notificar(
            error.message,
            "error",
        );
    }
}

async function ejecutarAccion(
    alertaId,
    accion,
) {
    try {
        await solicitarJson(
            (
                `${configuracion.apiAlertas}/`
                + `${alertaId}`
                + rutasAccion[accion]
            ),
            {
                method: "POST",
                headers: {
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
            },
        );

        notificar(
            accion === "resolver"
                ? "Alerta resuelta correctamente."
                : "Alerta ignorada correctamente.",
        );

        await cargarAlertas();
    }
    catch (error) {
        notificar(
            error.message,
            "error",
        );
    }
}

function abrirMenu() {
    document.body.classList.add(
        "menu-abierto"
    );

    elemento("abrir-menu")?.setAttribute(
        "aria-expanded",
        "true",
    );
}

function cerrarMenu() {
    document.body.classList.remove(
        "menu-abierto"
    );

    elemento("abrir-menu")?.setAttribute(
        "aria-expanded",
        "false",
    );
}

function registrarEventos() {
    elemento(
        "filtro-estado-alertas"
    ).addEventListener(
        "change",
        cargarAlertas,
    );

    elemento(
        "filtro-tipo-alertas"
    ).addEventListener(
        "change",
        cargarAlertas,
    );

    elemento(
        "actualizar-alertas"
    ).addEventListener(
        "click",
        cargarAlertas,
    );

    elemento("abrir-menu")?.addEventListener(
        "click",
        abrirMenu,
    );

    elemento("cerrar-menu")?.addEventListener(
        "click",
        cerrarMenu,
    );
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();
        await cargarAlertas();
    },
);
