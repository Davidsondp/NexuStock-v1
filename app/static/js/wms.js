"use strict";

(() => {
    const cuerpo = document.body;

    const configuracion = Object.freeze({
        apiWms: cuerpo.dataset.apiWms,
        apiVentas: cuerpo.dataset.apiVentas,
        apiProductos: cuerpo.dataset.apiProductos,
        bodegaId: Number(
            cuerpo.dataset.bodegaId
        ),
    });

    const estado = {
        ordenes: [],
        ventas: [],
        productos: new Map(),
        orden: null,
        escaner: null,
    };

    const etiquetasEstado = Object.freeze({
        pendiente: "Pendiente",
        picking: "Picking",
        pickeada: "Picking terminado",
        packing: "Packing",
        empacada: "Empacada",
        despachada: "Despachada",
        cancelada: "Cancelada",
    });

    let temporizadorNotificacion = null;

    function elemento(id) {
        return document.getElementById(id);
    }

    function crearNodo(
        etiqueta,
        texto = "",
        clase = "",
    ) {
        const nodo = document.createElement(
            etiqueta
        );

        if (texto !== "") {
            nodo.textContent = String(texto);
        }

        if (clase) {
            nodo.className = clase;
        }

        return nodo;
    }

    function tokenCsrf() {
        return elemento("csrf-token")?.value || "";
    }

    async function solicitarJson(
        url,
        opciones = {},
    ) {
        const encabezados = new Headers(
            opciones.headers || {}
        );

        encabezados.set(
            "Accept",
            "application/json",
        );

        if (opciones.body) {
            encabezados.set(
                "Content-Type",
                "application/json",
            );
            encabezados.set(
                "X-CSRFToken",
                tokenCsrf(),
            );
        }

        const respuesta = await fetch(
            url,
            {
                credentials: "same-origin",
                ...opciones,
                headers: encabezados,
            },
        );

        const tipo = (
            respuesta.headers.get(
                "content-type"
            ) || ""
        );

        const datos = tipo.includes(
            "application/json"
        )
            ? await respuesta.json()
            : null;

        if (!respuesta.ok) {
            throw new Error(
                datos?.mensaje
                || "No fue posible completar "
                + "la operaci\u00f3n."
            );
        }

        return datos;
    }

    function notificar(
        mensaje,
        tipo = "error",
    ) {
        const nodo = elemento(
            "notificacion-wms"
        );

        if (temporizadorNotificacion) {
            window.clearTimeout(
                temporizadorNotificacion
            );
        }

        nodo.textContent = mensaje;
        nodo.className = (
            tipo === "exito"
                ? "wms-notificacion "
                    + "wms-notificacion--exito"
                : "wms-notificacion "
                    + "wms-notificacion--error"
        );
        nodo.hidden = false;

        temporizadorNotificacion =
            window.setTimeout(
                () => {
                    nodo.hidden = true;
                },
                5000,
            );
    }

    function formatearCantidad(valor) {
        const numero = Number(valor || 0);

        return new Intl.NumberFormat(
            "es-CL",
            {
                maximumFractionDigits: 3,
            },
        ).format(
            Number.isFinite(numero)
                ? numero
                : 0
        );
    }

    function normalizarCantidad(valor) {
        const limpio = String(
            valor ?? ""
        ).trim().replace(/\s/g, "");

        if (
            !limpio
            || !/^\d+(?:[.,]\d{1,3})?$/.test(
                limpio
            )
        ) {
            throw new Error(
                "Ingresa una cantidad v\u00e1lida "
                + "con hasta tres decimales."
            );
        }

        const normalizado = limpio.replace(
            ",",
            ".",
        );
        const numero = Number(normalizado);

        if (
            !Number.isFinite(numero)
            || numero <= 0
        ) {
            throw new Error(
                "La cantidad debe ser mayor "
                + "que cero."
            );
        }

        return normalizado;
    }

    function productoPorId(id) {
        return estado.productos.get(
            Number(id)
        );
    }

    function cerrarMenu() {
        elemento("barra-lateral")
            ?.classList.remove(
                "lateral--abierta"
            );
        document.body.classList.remove(
            "menu-abierto"
        );
        elemento("abrir-menu")
            ?.setAttribute(
                "aria-expanded",
                "false",
            );
    }

    function abrirMenu() {
        elemento("barra-lateral")
            ?.classList.add(
                "lateral--abierta"
            );
        document.body.classList.add(
            "menu-abierto"
        );
        elemento("abrir-menu")
            ?.setAttribute(
                "aria-expanded",
                "true",
            );
    }

    function detenerEscaner() {
        estado.escaner?.detener();

        const panel = elemento(
            "panel-camara-wms"
        );

        if (panel) {
            panel.hidden = true;
        }
    }

    function obtenerEscaner() {
        if (estado.escaner) {
            return estado.escaner;
        }

        estado.escaner = NexuEscaner.crear({
            video: elemento(
                "video-escaner-wms"
            ),
            alDetectar: async (codigo) => {
                elemento(
                    "codigo-manual-wms"
                ).value = codigo;

                await registrarLectura(codigo);
            },
            alInformar: (
                mensaje,
                error = false,
            ) => {
                const nodo = elemento(
                    "estado-escaner-wms"
                );

                nodo.textContent = mensaje;
                nodo.classList.toggle(
                    "wms-escaner__error",
                    error,
                );
            },
        });

        return estado.escaner;
    }

    async function abrirEscaner() {
        const panel = elemento(
            "panel-camara-wms"
        );

        panel.hidden = false;

        await obtenerEscaner().iniciar();
    }

    function renderizarVentas() {
        const selector = elemento(
            "venta-reservada"
        );
        const valorActual = selector.value;
        const ocupadas = new Set(
            estado.ordenes.map(
                (orden) => Number(
                    orden.venta_id
                )
            )
        );

        selector.replaceChildren();

        const inicial = crearNodo(
            "option",
            "Selecciona una venta",
        );
        inicial.value = "";
        selector.appendChild(inicial);

        estado.ventas
            .filter(
                (venta) =>
                    venta.estado === "reservada"
                    && Number(venta.bodega_id)
                        === configuracion.bodegaId
                    && !ocupadas.has(
                        Number(venta.id)
                    )
            )
            .forEach((venta) => {
                const opcion = crearNodo(
                    "option",
                    `${venta.numero} \u00b7 `
                    + `${formatearCantidad(
                        venta.items.length
                    )} l\u00ednea(s)`,
                );
                opcion.value = String(
                    venta.id
                );
                selector.appendChild(opcion);
            });

        if (
            [...selector.options].some(
                (opcion) =>
                    opcion.value === valorActual
            )
        ) {
            selector.value = valorActual;
        }
    }

    function renderizarOrdenes() {
        const contenedor = elemento(
            "lista-ordenes-wms"
        );
        const filtro = elemento(
            "filtro-estado-wms"
        ).value;

        const ordenes = estado.ordenes.filter(
            (orden) =>
                !filtro
                || orden.estado === filtro
        );

        contenedor.replaceChildren();

        if (!ordenes.length) {
            contenedor.appendChild(
                crearNodo(
                    "p",
                    "No hay \u00f3rdenes para "
                    + "este filtro.",
                    "wms-vacio",
                )
            );
            return;
        }

        ordenes.forEach((orden) => {
            const boton = crearNodo(
                "button",
                "",
                "wms-orden",
            );
            boton.type = "button";
            boton.dataset.ordenId = String(
                orden.id
            );

            if (
                estado.orden
                && Number(estado.orden.id)
                    === Number(orden.id)
            ) {
                boton.classList.add(
                    "wms-orden--activa"
                );
            }

            const fila = crearNodo(
                "div",
                "",
                "wms-orden__fila",
            );
            fila.appendChild(
                crearNodo(
                    "strong",
                    orden.numero,
                )
            );
            fila.appendChild(
                crearNodo(
                    "span",
                    etiquetasEstado[
                        orden.estado
                    ] || orden.estado,
                    "wms-estado",
                )
            );

            boton.appendChild(fila);
            boton.appendChild(
                crearNodo(
                    "small",
                    `Venta ${orden.venta_id} `
                    + `\u00b7 Bodega `
                    + `${orden.bodega_id}`,
                )
            );

            boton.addEventListener(
                "click",
                () => seleccionarOrden(
                    orden.id
                ),
            );

            contenedor.appendChild(boton);
        });
    }

    function progresoVisible(orden) {
        if (
            orden.estado === "packing"
            || orden.estado === "empacada"
            || orden.estado === "despachada"
        ) {
            return "empacados";
        }

        return "pickeados";
    }

    function renderizarProgreso(orden) {
        const contenedor = elemento(
            "progreso-wms"
        );
        const progreso = orden.progreso || {};
        const requeridos = (
            progreso.requeridos || {}
        );
        const clave = progresoVisible(orden);
        const registrados = (
            progreso[clave] || {}
        );

        contenedor.replaceChildren();

        Object.entries(requeridos).forEach(
            ([productoId, requerido]) => {
                const producto = productoPorId(
                    productoId
                );
                const articulo = crearNodo(
                    "article",
                    "",
                    "wms-item",
                );
                const informacion = crearNodo(
                    "div"
                );

                informacion.appendChild(
                    crearNodo(
                        "strong",
                        producto?.nombre
                        || `Art\u00edculo `
                            + `#${productoId}`,
                    )
                );

                informacion.appendChild(
                    crearNodo(
                        "small",
                        producto
                            ? (
                                `SKU ${producto.codigo}`
                                + (
                                    producto.codigo_barras
                                        ? ` \u00b7 `
                                            + producto
                                                .codigo_barras
                                        : ""
                                )
                            )
                            : "Producto no disponible",
                    )
                );

                articulo.appendChild(
                    informacion
                );
                articulo.appendChild(
                    crearNodo(
                        "span",
                        `${formatearCantidad(
                            registrados[
                                productoId
                            ] || 0
                        )} / `
                        + `${formatearCantidad(
                            requerido
                        )}`,
                        "wms-item__cantidad",
                    )
                );

                contenedor.appendChild(
                    articulo
                );
            }
        );
    }

    function botonAccion(
        texto,
        accion,
        principal = true,
    ) {
        const boton = crearNodo(
            "button",
            texto,
            principal
                ? "boton boton--primario"
                : "boton boton--secundario",
        );
        boton.type = "button";
        boton.addEventListener(
            "click",
            accion,
        );
        return boton;
    }

    function renderizarDetalle() {
        const detalle = elemento(
            "detalle-wms"
        );

        detenerEscaner();

        if (!estado.orden) {
            detalle.hidden = true;
            return;
        }

        const orden = estado.orden;

        detalle.hidden = false;

        elemento(
            "detalle-numero-wms"
        ).textContent = orden.numero;

        elemento(
            "detalle-estado-wms"
        ).textContent = (
            etiquetasEstado[orden.estado]
            || orden.estado
        );

        elemento(
            "detalle-meta-wms"
        ).textContent = (
            `Venta ${orden.venta_id} \u00b7 `
            + `Bodega ${orden.bodega_id}`
        );

        renderizarProgreso(orden);

        const acciones = elemento(
            "acciones-wms"
        );
        const zonaEscaner = elemento(
            "zona-escaner-wms"
        );
        const despacho = elemento(
            "despacho-wms"
        );

        acciones.replaceChildren();
        zonaEscaner.hidden = true;
        despacho.hidden = true;

        if (orden.estado === "pendiente") {
            acciones.appendChild(
                botonAccion(
                    "Iniciar picking",
                    avanzarOrden,
                )
            );
        } else if (orden.estado === "picking") {
            zonaEscaner.hidden = false;
            acciones.appendChild(
                botonAccion(
                    "Cerrar picking",
                    avanzarOrden,
                )
            );
        } else if (
            orden.estado === "pickeada"
        ) {
            acciones.appendChild(
                botonAccion(
                    "Iniciar packing",
                    avanzarOrden,
                )
            );
        } else if (
            orden.estado === "packing"
        ) {
            zonaEscaner.hidden = false;
            acciones.appendChild(
                botonAccion(
                    "Cerrar packing",
                    avanzarOrden,
                )
            );
        } else if (
            orden.estado === "empacada"
        ) {
            despacho.hidden = false;
        } else if (
            orden.estado === "despachada"
        ) {
            acciones.appendChild(
                crearNodo(
                    "p",
                    `Despachada por `
                    + `${orden.transportista}. `
                    + `Seguimiento: `
                    + `${orden.seguimiento}.`,
                )
            );
        }
    }

    async function cargarDatos() {
        detenerEscaner();

        try {
            const [
                datosWms,
                datosVentas,
                datosProductos,
            ] = await Promise.all([
                solicitarJson(
                    configuracion.apiWms
                ),
                solicitarJson(
                    `${configuracion.apiVentas}`
                    + "?estado=reservada"
                ),
                solicitarJson(
                    configuracion.apiProductos
                ),
            ]);

            estado.ordenes = (
                datosWms.ordenes || []
            );
            estado.ventas = (
                datosVentas.ventas || []
            );
            estado.productos = new Map(
                (datosProductos.productos || [])
                    .map(
                        (producto) => [
                            Number(producto.id),
                            producto,
                        ]
                    )
            );

            if (estado.orden) {
                const actual = estado.ordenes.find(
                    (orden) =>
                        Number(orden.id)
                        === Number(
                            estado.orden.id
                        )
                );
                estado.orden = actual || null;
            }

            renderizarVentas();
            renderizarOrdenes();
            renderizarDetalle();
        } catch (error) {
            notificar(error.message);
        }
    }

    async function seleccionarOrden(id) {
        try {
            estado.orden = await solicitarJson(
                `${configuracion.apiWms}/${id}`
            );
            renderizarOrdenes();
            renderizarDetalle();

            elemento("detalle-wms")
                ?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
        } catch (error) {
            notificar(error.message);
        }
    }

    async function crearOrden(evento) {
        evento.preventDefault();

        const ventaId = Number(
            elemento(
                "venta-reservada"
            ).value
        );
        const numero = elemento(
            "numero-orden-wms"
        ).value.trim();

        if (!ventaId || !numero) {
            notificar(
                "Selecciona una venta y "
                + "escribe el n\u00famero de orden."
            );
            return;
        }

        try {
            const creada = await solicitarJson(
                configuracion.apiWms,
                {
                    method: "POST",
                    body: JSON.stringify({
                        venta_id: ventaId,
                        numero,
                    }),
                },
            );

            estado.orden = creada;
            elemento(
                "crear-orden-wms"
            ).reset();

            await cargarDatos();
            await seleccionarOrden(creada.id);

            notificar(
                "Orden WMS creada correctamente.",
                "exito",
            );
        } catch (error) {
            notificar(error.message);
        }
    }

    async function avanzarOrden() {
        if (!estado.orden) {
            return;
        }

        try {
            estado.orden = await solicitarJson(
                `${configuracion.apiWms}/`
                + `${estado.orden.id}/avanzar`,
                {
                    method: "POST",
                    body: JSON.stringify({}),
                },
            );

            await cargarDatos();
            await seleccionarOrden(
                estado.orden.id
            );

            notificar(
                "La orden avanz\u00f3 de etapa.",
                "exito",
            );
        } catch (error) {
            notificar(error.message);
        }
    }

    async function registrarLectura(
        codigoIngresado,
    ) {
        if (
            !estado.orden
            || !["picking", "packing"].includes(
                estado.orden.estado
            )
        ) {
            notificar(
                "La orden no est\u00e1 en una "
                + "etapa de escaneo."
            );
            return;
        }

        const codigo = String(
            codigoIngresado || ""
        ).trim();

        if (!codigo) {
            notificar(
                "Ingresa o escanea un c\u00f3digo."
            );
            return;
        }

        let cantidad;

        try {
            cantidad = normalizarCantidad(
                elemento(
                    "cantidad-escaner-wms"
                ).value
            );
        } catch (error) {
            notificar(error.message);
            return;
        }

        const etapa = estado.orden.estado;
        const ordenId = estado.orden.id;

        try {
            estado.orden = await solicitarJson(
                `${configuracion.apiWms}/`
                + `${ordenId}/escanear`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        etapa,
                        codigo_producto: codigo,
                        cantidad,
                    }),
                },
            );

            elemento(
                "codigo-manual-wms"
            ).value = "";

            renderizarOrdenes();
            renderizarDetalle();

            notificar(
                "Lectura registrada correctamente.",
                "exito",
            );
        } catch (error) {
            detenerEscaner();
            notificar(error.message);
        }
    }

    async function despachar(evento) {
        evento.preventDefault();

        if (!estado.orden) {
            return;
        }

        const transportista = elemento(
            "transportista-wms"
        ).value.trim();
        const seguimiento = elemento(
            "seguimiento-wms"
        ).value.trim();

        try {
            estado.orden = await solicitarJson(
                `${configuracion.apiWms}/`
                + `${estado.orden.id}/avanzar`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        transportista,
                        seguimiento,
                    }),
                },
            );

            evento.currentTarget.reset();

            await cargarDatos();
            await seleccionarOrden(
                estado.orden.id
            );

            notificar(
                "Pedido despachado correctamente.",
                "exito",
            );
        } catch (error) {
            notificar(error.message);
        }
    }

    function registrarEventos() {
        elemento(
            "crear-orden-wms"
        ).addEventListener(
            "submit",
            crearOrden,
        );

        elemento(
            "actualizar-wms"
        ).addEventListener(
            "click",
            cargarDatos,
        );

        elemento(
            "filtro-estado-wms"
        ).addEventListener(
            "change",
            renderizarOrdenes,
        );

        elemento(
            "venta-reservada"
        ).addEventListener(
            "change",
            (evento) => {
                const venta = estado.ventas.find(
                    (item) =>
                        Number(item.id)
                        === Number(
                            evento.target.value
                        )
                );

                elemento(
                    "numero-orden-wms"
                ).value = venta
                    ? `OW-${venta.numero}`
                    : "";
            },
        );

        elemento(
            "abrir-escaner-wms"
        ).addEventListener(
            "click",
            abrirEscaner,
        );

        elemento(
            "cerrar-escaner-wms"
        ).addEventListener(
            "click",
            detenerEscaner,
        );

        elemento(
            "enviar-codigo-wms"
        ).addEventListener(
            "click",
            () => registrarLectura(
                elemento(
                    "codigo-manual-wms"
                ).value
            ),
        );

        elemento(
            "codigo-manual-wms"
        ).addEventListener(
            "keydown",
            (evento) => {
                if (evento.key === "Enter") {
                    evento.preventDefault();
                    registrarLectura(
                        evento.currentTarget.value
                    );
                }
            },
        );

        elemento(
            "despacho-wms"
        ).addEventListener(
            "submit",
            despachar,
        );

        elemento(
            "abrir-menu"
        )?.addEventListener(
            "click",
            abrirMenu,
        );

        elemento(
            "fondo-menu"
        )?.addEventListener(
            "click",
            cerrarMenu,
        );

        globalThis.addEventListener(
            "pagehide",
            detenerEscaner,
        );
    }

    document.addEventListener(
        "DOMContentLoaded",
        async () => {
            registrarEventos();
            await cargarDatos();
        },
    );
})();
