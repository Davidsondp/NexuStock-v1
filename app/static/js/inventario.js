"use strict";

const configuracion = Object.freeze({
    apiInventario:
        document.body.dataset.apiInventario,
    apiStock:
        document.body.dataset.apiStock,
    apiLotes:
        document.body.dataset.apiLotes,
    apiMovimientos:
        document.body.dataset.apiMovimientos,
    apiProductos:
        document.body.dataset.apiProductos,
    bodegaId:
        Number(document.body.dataset.bodegaId),
    puedeEntrada:
        document.body.dataset.permisoEntrada === "true",
    puedeSalida:
        document.body.dataset.permisoSalida === "true",
    puedeAjuste:
        document.body.dataset.permisoAjuste === "true",
    puedeDevolucion:
        document.body.dataset.permisoDevolucion === "true",
});

const estado = {
    stock: [],
    lotes: [],
    movimientos: [],
    productos: [],
};

let temporizadorNotificacion = null;
let flujoCamara = null;
let detectorCodigos = null;
let cuadroEscaneo = null;
let escaneoEnCurso = false;

function elemento(id) {
    return document.getElementById(id);
}

function crearElemento(
    etiqueta,
    texto = "",
    clase = ""
) {
    const nodo = document.createElement(etiqueta);

    if (texto !== "") {
        nodo.textContent = String(texto);
    }

    if (clase) {
        nodo.className = clase;
    }

    return nodo;
}

function limpiar(nodo) {
    while (nodo?.firstChild) {
        nodo.removeChild(nodo.firstChild);
    }
}

function normalizarCodigo(valor) {
    return String(valor || "")
        .trim()
        .replace(/\s+/g, "")
        .toLocaleUpperCase("es");
}

function extraerCodigoEscaneado(valor) {
    const original = String(valor || "").trim();

    if (!original) {
        return "";
    }

    try {
        const datos = JSON.parse(original);
        const codigo = datos.codigo_barras
            || datos.codigoBarras
            || datos.codigo
            || datos.sku;

        if (codigo) {
            return String(codigo);
        }
    } catch (_error) {
        // El código no contiene JSON; se procesa como texto o URL.
    }

    try {
        const url = new URL(original);
        const codigo = url.searchParams.get("codigo_barras")
            || url.searchParams.get("codigo")
            || url.searchParams.get("sku");

        if (codigo) {
            return codigo;
        }
    } catch (_error) {
        // No es una URL y puede ser un EAN/UPC/Code 128 válido.
    }

    return original;
}

function seleccionarProductoEscaneado(valor) {
    const codigo = normalizarCodigo(
        extraerCodigoEscaneado(valor)
    );
    const producto = estado.productos.find(
        (candidato) =>
            normalizarCodigo(candidato.codigo_barras) === codigo
            || normalizarCodigo(candidato.codigo) === codigo
    );

    if (!codigo || !producto) {
        elemento("estado-escaner").textContent =
            "No encontramos un producto activo con ese código.";
        return false;
    }

    elemento("movimiento-producto").value = String(producto.id);
    elemento("producto-escaneado").textContent =
        `Producto detectado: ${producto.nombre}`;
    elemento("estado-escaner").textContent =
        `Listo: ${producto.nombre}`;
    actualizarCamposMovimiento();
    detenerEscaner();
    elemento("movimiento-cantidad")?.focus();
    return true;
}

async function detectarCuadro() {
    if (!escaneoEnCurso || !detectorCodigos) {
        return;
    }

    const video = elemento("video-escaner");

    if (video?.readyState >= 2) {
        try {
            const resultados = await detectorCodigos.detect(video);

            if (
                resultados.length
                && seleccionarProductoEscaneado(resultados[0].rawValue)
            ) {
                return;
            }
        } catch (_error) {
            elemento("estado-escaner").textContent =
                "Mantén el código dentro del recuadro y evita reflejos.";
        }
    }

    cuadroEscaneo = window.requestAnimationFrame(detectarCuadro);
}

function detenerEscaner() {
    escaneoEnCurso = false;

    if (cuadroEscaneo) {
        window.cancelAnimationFrame(cuadroEscaneo);
        cuadroEscaneo = null;
    }

    flujoCamara?.getTracks().forEach((pista) => pista.stop());
    flujoCamara = null;

    const video = elemento("video-escaner");
    if (video) {
        video.srcObject = null;
    }

    const panel = elemento("panel-escaner");
    if (panel) {
        panel.hidden = true;
    }
}

async function abrirEscaner() {
    const panel = elemento("panel-escaner");
    const estadoEscaner = elemento("estado-escaner");
    panel.hidden = false;

    if (!window.isSecureContext) {
        estadoEscaner.textContent =
            "La cámara requiere HTTPS. Puedes ingresar el código abajo.";
        return;
    }

    if (!("BarcodeDetector" in window)) {
        estadoEscaner.textContent =
            "Este navegador no permite lectura automática. Ingresa el código abajo.";
        return;
    }

    try {
        const formatosSoportados = typeof window.BarcodeDetector
            .getSupportedFormats === "function"
            ? await window.BarcodeDetector.getSupportedFormats()
            : ["qr_code", "ean_13", "ean_8", "upc_a", "upc_e", "code_128"];
        const deseados = [
            "qr_code",
            "ean_13",
            "ean_8",
            "upc_a",
            "upc_e",
            "code_128",
            "code_39",
            "itf",
        ].filter((formato) => formatosSoportados.includes(formato));

        detectorCodigos = deseados.length
            ? new window.BarcodeDetector({formats: deseados})
            : new window.BarcodeDetector();
        flujoCamara = await navigator.mediaDevices.getUserMedia({
            audio: false,
            video: {
                facingMode: {ideal: "environment"},
                width: {ideal: 1280},
                height: {ideal: 720},
            },
        });
        const video = elemento("video-escaner");
        video.srcObject = flujoCamara;
        await video.play();
        escaneoEnCurso = true;
        estadoEscaner.textContent =
            "Apunta al QR o código de barras; la lectura es automática.";
        detectarCuadro();
    } catch (error) {
        detenerEscaner();
        panel.hidden = false;
        estadoEscaner.textContent = error.name === "NotAllowedError"
            ? "Permiso de cámara rechazado. Habilítalo o ingresa el código abajo."
            : "No fue posible iniciar la cámara. Ingresa el código abajo.";
    }
}

function numero(valor) {
    const resultado = Number(valor);

    return Number.isFinite(resultado)
        ? resultado
        : 0;
}

function formatearCantidad(valor) {
    return new Intl.NumberFormat(
        "es-CL",
        {
            minimumFractionDigits: 0,
            maximumFractionDigits: 3,
        }
    ).format(numero(valor));
}

function formatearMoneda(valor) {
    return new Intl.NumberFormat(
        "es-CL",
        {
            style: "currency",
            currency: "CLP",
            maximumFractionDigits: 0,
        }
    ).format(numero(valor));
}

function formatearFecha(valor) {
    if (!valor) {
        return "—";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return "—";
    }

    return new Intl.DateTimeFormat(
        "es-CL",
        {
            dateStyle: "short",
            timeStyle: "short",
        }
    ).format(fecha);
}

function obtenerTokenCsrf() {
    return elemento("csrf-token")?.value || "";
}

async function solicitarJson(
    url,
    opciones = {}
) {
    const respuesta = await fetch(
        url,
        {
            credentials: "same-origin",
            ...opciones,
        }
    );

    const tipoContenido = (
        respuesta.headers.get("content-type")
        || ""
    );

    let datos = null;

    if (
        tipoContenido.includes(
            "application/json"
        )
    ) {
        datos = await respuesta.json();
    }

    if (!respuesta.ok) {
        throw new Error(
            datos?.mensaje
            || "No fue posible completar la operación."
        );
    }

    return datos;
}

function notificar(
    mensaje,
    tipo = "error"
) {
    const nodo = elemento("notificacion");

    if (!nodo) {
        return;
    }

    if (temporizadorNotificacion) {
        window.clearTimeout(
            temporizadorNotificacion
        );
    }

    nodo.textContent = mensaje;
    nodo.className = (
        tipo === "exito"
            ? "notificacion--exito"
            : "notificacion--error"
    );
    nodo.hidden = false;

    temporizadorNotificacion = window.setTimeout(
        () => {
            nodo.hidden = true;
        },
        4500
    );
}

function permisosDisponibles() {
    return [
        {
            valor: "entrada",
            etiqueta: "Entrada",
            permitido:
                configuracion.puedeEntrada,
        },
        {
            valor: "salida",
            etiqueta: "Salida",
            permitido:
                configuracion.puedeSalida,
        },
        {
            valor: "ajuste",
            etiqueta: "Ajuste de inventario",
            permitido:
                configuracion.puedeAjuste,
        },
        {
            valor: "devolucion",
            etiqueta: "Devolución de cliente",
            permitido:
                configuracion.puedeDevolucion,
        },
    ].filter(
        (operacion) => operacion.permitido
    );
}

function renderizarTiposMovimiento() {
    const selector = elemento(
        "movimiento-tipo"
    );

    if (!selector) {
        return;
    }

    limpiar(selector);

    permisosDisponibles().forEach(
        (operacion) => {
            const opcion = crearElemento(
                "option",
                operacion.etiqueta
            );

            opcion.value = operacion.valor;
            selector.appendChild(opcion);
        }
    );
}

function renderizarProductos() {
    const selector = elemento(
        "movimiento-producto"
    );

    if (!selector) {
        return;
    }

    const seleccionado = selector.value;

    limpiar(selector);

    const inicial = crearElemento(
        "option",
        "Selecciona un producto"
    );

    inicial.value = "";
    selector.appendChild(inicial);

    estado.productos
        .filter(
            (producto) =>
                producto.activo !== false
        )
        .sort(
            (primero, segundo) =>
                String(primero.nombre).localeCompare(
                    String(segundo.nombre),
                    "es"
                )
        )
        .forEach((producto) => {
            const codigo = producto.codigo
                ? ` · ${producto.codigo}`
                : "";

            const opcion = crearElemento(
                "option",
                `${producto.nombre}${codigo}`
            );

            opcion.value = String(producto.id);
            selector.appendChild(opcion);
        });

    const existeSeleccionado = [
        ...selector.options,
    ].some(
        (opcion) =>
            opcion.value === seleccionado
    );

    selector.value = existeSeleccionado
        ? seleccionado
        : "";
}

function obtenerStockFiltrado() {
    const busqueda = (
        elemento("buscar-inventario")
            ?.value
        || ""
    )
        .trim()
        .toLocaleLowerCase("es");

    const filtro = (
        elemento("filtrar-existencia")
            ?.value
        || "todos"
    );

    return estado.stock.filter((fila) => {
        const coincideBusqueda = (
            !busqueda
            || String(
                fila.producto_nombre || ""
            )
                .toLocaleLowerCase("es")
                .includes(busqueda)
            || String(
                fila.producto_codigo || ""
            )
                .toLocaleLowerCase("es")
                .includes(busqueda)
        );

        const cantidad = numero(
            fila.cantidad
        );
        const reservada = numero(
            fila.reservada
        );
        const disponible = numero(
            fila.disponible
        );

        let coincideFiltro = true;

        if (filtro === "disponible") {
            coincideFiltro = disponible > 0;
        } else if (filtro === "agotado") {
            coincideFiltro = cantidad <= 0;
        } else if (filtro === "reservado") {
            coincideFiltro = reservada > 0;
        }

        return (
            coincideBusqueda
            && coincideFiltro
        );
    });
}

function crearCeldaProducto(fila) {
    const celda = crearElemento("td");
    const contenedor = crearElemento(
        "div",
        "",
        "producto-celda"
    );

    contenedor.appendChild(
        crearElemento(
            "strong",
            fila.producto_nombre || "Producto"
        )
    );

    contenedor.appendChild(
        crearElemento(
            "span",
            fila.producto_codigo || "Sin código"
        )
    );

    celda.appendChild(contenedor);

    return celda;
}

function abrirFormulario(
    productoId = null,
    tipoInicial = null
) {
    const operaciones = permisosDisponibles();

    if (!operaciones.length) {
        notificar(
            "No tienes permisos para registrar movimientos."
        );
        return;
    }

    const formulario = elemento(
        "formulario-movimiento"
    );

    formulario?.reset();
    renderizarTiposMovimiento();
    renderizarProductos();

    const selectorTipo = elemento(
        "movimiento-tipo"
    );

    if (
        tipoInicial
        && operaciones.some(
            (operacion) =>
                operacion.valor === tipoInicial
        )
    ) {
        selectorTipo.value = tipoInicial;
    }

    if (productoId) {
        elemento(
            "movimiento-producto"
        ).value = String(productoId);
    }

    actualizarCamposMovimiento();

    const modal = elemento(
        "modal-movimiento"
    );

    modal.hidden = false;
    document.body.style.overflow = "hidden";

    window.setTimeout(
        () => {
            elemento(
                "movimiento-producto"
            )?.focus();
        },
        0
    );
}

function cerrarFormulario() {
    detenerEscaner();
    const modal = elemento(
        "modal-movimiento"
    );

    if (modal) {
        modal.hidden = true;
    }

    document.body.style.overflow = "";
}

function crearAccionesStock(fila) {
    const celda = crearElemento("td");
    const operaciones = permisosDisponibles();

    if (!operaciones.length) {
        celda.textContent = "Sin acciones";
        return celda;
    }

    const boton = crearElemento(
        "button",
        "Movimiento",
        "boton boton--pequeno boton--secundario"
    );

    boton.type = "button";
    boton.addEventListener(
        "click",
        () => abrirFormulario(
            fila.producto_id
        )
    );

    celda.appendChild(boton);

    return celda;
}

function renderizarStock() {
    const cuerpo = elemento("tabla-stock");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const filas = obtenerStockFiltrado();

    elemento("cantidad-stock").textContent = (
        `${filas.length} `
        + (
            filas.length === 1
                ? "producto"
                : "productos"
        )
    );

    if (!filas.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No hay existencias que coincidan con los filtros.",
            "tabla__vacio"
        );

        celda.colSpan = 7;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    filas.forEach((item) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearCeldaProducto(item)
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearCantidad(item.cantidad),
                "cantidad-destacada"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearCantidad(item.reservada)
            )
        );

        const disponible = numero(
            item.disponible
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearCantidad(disponible),
                disponible > 0
                    ? "cantidad-disponible"
                    : "cantidad-agotada"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearMoneda(
                    item.costo_promedio
                )
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearMoneda(item.valor)
            )
        );

        fila.appendChild(
            crearAccionesStock(item)
        );

        cuerpo.appendChild(fila);
    });
}

function renderizarResumen() {
    const productos = estado.stock.filter(
        (fila) => numero(fila.cantidad) > 0
    ).length;

    const unidades = estado.stock.reduce(
        (total, fila) =>
            total + numero(fila.cantidad),
        0
    );

    const reservadas = estado.stock.reduce(
        (total, fila) =>
            total + numero(fila.reservada),
        0
    );

    const valor = estado.stock.reduce(
        (total, fila) =>
            total + numero(fila.valor),
        0
    );

    elemento("resumen-productos").textContent = (
        new Intl.NumberFormat("es-CL")
            .format(productos)
    );

    elemento("resumen-unidades").textContent = (
        formatearCantidad(unidades)
    );

    elemento("resumen-reservadas").textContent = (
        formatearCantidad(reservadas)
    );

    elemento("resumen-valor").textContent = (
        formatearMoneda(valor)
    );
}

function claseTipoMovimiento(tipo) {
    const permitidos = new Set([
        "entrada",
        "salida",
        "ajuste",
        "devolucion",
    ]);

    return permitidos.has(tipo)
        ? `movimiento-tipo--${tipo}`
        : "";
}

function renderizarMovimientos() {
    const cuerpo = elemento(
        "tabla-movimientos"
    );

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    elemento(
        "cantidad-movimientos"
    ).textContent = (
        `${estado.movimientos.length} `
        + (
            estado.movimientos.length === 1
                ? "movimiento registrado"
                : "movimientos registrados"
        )
    );

    if (!estado.movimientos.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "Todavía no existen movimientos en esta bodega.",
            "tabla__vacio"
        );

        celda.colSpan = 7;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    estado.movimientos.forEach(
        (movimiento) => {
            const fila = crearElemento("tr");

            fila.appendChild(
                crearElemento(
                    "td",
                    formatearFecha(
                        movimiento.fecha
                    )
                )
            );

            fila.appendChild(
                crearCeldaProducto(
                    movimiento
                )
            );

            const celdaTipo = crearElemento("td");
            const tipo = crearElemento(
                "span",
                movimiento.tipo,
                (
                    "movimiento-tipo "
                    + claseTipoMovimiento(
                        movimiento.tipo
                    )
                ).trim()
            );

            celdaTipo.appendChild(tipo);
            fila.appendChild(celdaTipo);

            const cantidad = numero(
                movimiento.cantidad
            );

            fila.appendChild(
                crearElemento(
                    "td",
                    (
                        cantidad > 0
                            ? "+"
                            : ""
                    )
                    + formatearCantidad(
                        cantidad
                    ),
                    cantidad >= 0
                        ? (
                            "movimiento-cantidad"
                            + "--positiva"
                        )
                        : (
                            "movimiento-cantidad"
                            + "--negativa"
                        )
                )
            );

            fila.appendChild(
                crearElemento(
                    "td",
                    formatearCantidad(
                        movimiento.stock_anterior
                    )
                )
            );

            fila.appendChild(
                crearElemento(
                    "td",
                    formatearCantidad(
                        movimiento.stock_nuevo
                    ),
                    "cantidad-destacada"
                )
            );

            fila.appendChild(
                crearElemento(
                    "td",
                    movimiento.motivo || "—"
                )
            );

            cuerpo.appendChild(fila);
        }
    );
}

function metadatosVencimiento(estadoLote) {
    const estados = {
        vencido: {
            etiqueta: "Vencido",
            clase: "lote-estado--vencido",
        },
        vence_hoy: {
            etiqueta: "Vence hoy",
            clase: "lote-estado--hoy",
        },
        proximo_vencer: {
            etiqueta: "Próximo a vencer",
            clase: "lote-estado--proximo",
        },
        vigente: {
            etiqueta: "Vigente",
            clase: "lote-estado--vigente",
        },
        sin_vencimiento: {
            etiqueta: "Sin vencimiento",
            clase: "lote-estado--sin-fecha",
        },
    };

    return estados[estadoLote] || {
        etiqueta: "Sin clasificar",
        clase: "lote-estado--sin-fecha",
    };
}

function formatearFechaLote(valor) {
    if (!valor) {
        return "—";
    }

    const partes = String(valor).split("-");

    if (partes.length !== 3) {
        return valor;
    }

    return `${partes[2]}-${partes[1]}-${partes[0]}`;
}

function obtenerLotesFiltrados() {
    const estadoSeleccionado = elemento(
        "filtrar-vencimiento"
    )?.value || "";

    if (!estadoSeleccionado) {
        return estado.lotes;
    }

    return estado.lotes.filter(
        (lote) =>
            lote.estado_vencimiento
            === estadoSeleccionado
    );
}

function renderizarResumenLotes() {
    const contenedor = elemento(
        "resumen-lotes"
    );

    if (!contenedor) {
        return;
    }

    limpiar(contenedor);

    const resumen = [
        {
            etiqueta: "Lotes activos",
            valor: estado.lotes.length,
            clase: "resumen-lote--total",
        },
        {
            etiqueta: "Vencidos",
            valor: estado.lotes.filter(
                (lote) =>
                    lote.estado_vencimiento
                    === "vencido"
            ).length,
            clase: "resumen-lote--vencido",
        },
        {
            etiqueta: "Vencen hoy",
            valor: estado.lotes.filter(
                (lote) =>
                    lote.estado_vencimiento
                    === "vence_hoy"
            ).length,
            clase: "resumen-lote--hoy",
        },
        {
            etiqueta: "Próximos a vencer",
            valor: estado.lotes.filter(
                (lote) =>
                    lote.estado_vencimiento
                    === "proximo_vencer"
            ).length,
            clase: "resumen-lote--proximo",
        },
    ];

    resumen.forEach((item) => {
        const tarjeta = crearElemento(
            "article",
            "",
            `resumen-lote ${item.clase}`
        );
        const etiqueta = crearElemento(
            "span",
            item.etiqueta,
            "resumen-lote__etiqueta"
        );
        const valor = crearElemento(
            "strong",
            new Intl.NumberFormat("es-CL")
                .format(item.valor),
            "resumen-lote__valor"
        );

        tarjeta.appendChild(etiqueta);
        tarjeta.appendChild(valor);
        contenedor.appendChild(tarjeta);
    });
}

function renderizarLotes() {
    const cuerpo = elemento("tabla-lotes");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const lotes = obtenerLotesFiltrados();

    if (!lotes.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No hay lotes que coincidan "
            + "con el filtro seleccionado.",
            "tabla__vacio"
        );

        celda.colSpan = 6;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    lotes.forEach((lote) => {
        const fila = crearElemento("tr");
        const metadatos = metadatosVencimiento(
            lote.estado_vencimiento
        );

        fila.className = (
            `fila-lote ${metadatos.clase}`
        );

        fila.appendChild(
            crearCeldaProducto(lote)
        );

        fila.appendChild(
            crearElemento(
                "td",
                lote.numero,
                "lote-numero"
            )
        );

        const textoVencimiento = (
            formatearFechaLote(
                lote.fecha_vencimiento
            )
        );
        const dias = lote.dias_para_vencer;

        const celdaVencimiento = crearElemento(
            "td"
        );
        const fecha = crearElemento(
            "strong",
            textoVencimiento
        );
        const detalle = crearElemento(
            "small",
            (
                dias === null
                    ? "Sin fecha registrada"
                    : (
                        dias < 0
                            ? `${Math.abs(dias)} días vencido`
                            : (
                                dias === 0
                                    ? "Vence hoy"
                                    : `${dias} días restantes`
                            )
                    )
            ),
            "lote-vencimiento__detalle"
        );

        celdaVencimiento.appendChild(fecha);
        celdaVencimiento.appendChild(detalle);
        fila.appendChild(celdaVencimiento);

        const celdaEstado = crearElemento("td");
        const insignia = crearElemento(
            "span",
            metadatos.etiqueta,
            `lote-estado ${metadatos.clase}`
        );

        celdaEstado.appendChild(insignia);
        fila.appendChild(celdaEstado);

        fila.appendChild(
            crearElemento(
                "td",
                formatearCantidad(
                    lote.cantidad
                ),
                "cantidad-destacada"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearMoneda(lote.valor)
            )
        );

        cuerpo.appendChild(fila);
    });
}

function actualizarCamposMovimiento() {
    const selectorTipo = elemento(
        "movimiento-tipo"
    );
    const selectorProducto = elemento(
        "movimiento-producto"
    );

    let tipo = selectorTipo?.value || "";

    const productoId = Number(
        selectorProducto?.value
    );
    const producto = estado.productos.find(
        (item) => Number(item.id) === productoId
    );

    const controlaLotes = Boolean(
        producto?.controla_lotes
        || producto?.controla_vencimiento
    );
    const controlaVencimiento = Boolean(
        producto?.controla_vencimiento
    );

    const opcionAjuste = [
        ...(selectorTipo?.options || []),
    ].find(
        (opcion) => opcion.value === "ajuste"
    );

    if (opcionAjuste) {
        opcionAjuste.disabled = controlaLotes;
    }

    if (
        controlaLotes
        && tipo === "ajuste"
    ) {
        selectorTipo.value = "";
        tipo = "";

        notificar(
            "Los productos controlados deben "
            + "ajustarse mediante movimientos "
            + "específicos por lote."
        );
    }

    const esAjuste = tipo === "ajuste";
    const usaCosto = (
        tipo === "entrada"
        || tipo === "devolucion"
    );
    const usaPrecio = tipo === "salida";
    const usaTrazabilidad = (
        usaCosto
        && controlaLotes
    );

    elemento("grupo-cantidad").hidden = (
        esAjuste
    );

    elemento(
        "grupo-stock-final"
    ).hidden = !esAjuste;

    elemento(
        "grupo-costo-unitario"
    ).hidden = !usaCosto;

    elemento(
        "grupo-precio-unitario"
    ).hidden = !usaPrecio;

    elemento(
        "grupo-numero-lote"
    ).hidden = !usaTrazabilidad;

    elemento(
        "grupo-fecha-vencimiento"
    ).hidden = !(
        usaTrazabilidad
        && controlaVencimiento
    );

    elemento(
        "ayuda-trazabilidad"
    ).hidden = !usaTrazabilidad;

    elemento(
        "movimiento-cantidad"
    ).required = !esAjuste;

    elemento(
        "movimiento-stock-final"
    ).required = esAjuste;

    elemento(
        "movimiento-costo-unitario"
    ).required = usaCosto;

    elemento(
        "movimiento-precio-unitario"
    ).required = false;

    elemento(
        "movimiento-numero-lote"
    ).required = usaTrazabilidad;

    elemento(
        "movimiento-fecha-vencimiento"
    ).required = (
        usaTrazabilidad
        && controlaVencimiento
    );
}

function construirMovimiento() {
    const tipo = elemento(
        "movimiento-tipo"
    ).value;

    const productoId = Number(
        elemento("movimiento-producto").value
    );

    const motivo = elemento(
        "movimiento-motivo"
    ).value.trim();

    if (!tipo) {
        throw new Error(
            "Selecciona el tipo de movimiento."
        );
    }

    if (!productoId) {
        throw new Error(
            "Selecciona un producto."
        );
    }

    if (!motivo) {
        throw new Error(
            "El motivo es obligatorio."
        );
    }

    const datos = {
        tipo,
        producto_id: productoId,
        motivo,
    };

    if (tipo === "ajuste") {
        const stockFinal = numero(
            elemento(
                "movimiento-stock-final"
            ).value
        );

        if (stockFinal < 0) {
            throw new Error(
                "El stock final no puede ser negativo."
            );
        }

        datos.stock_final = stockFinal;
    } else {
        const cantidad = numero(
            elemento(
                "movimiento-cantidad"
            ).value
        );

        if (cantidad <= 0) {
            throw new Error(
                "La cantidad debe ser mayor que cero."
            );
        }

        datos.cantidad = cantidad;
    }

    if (
        tipo === "entrada"
        || tipo === "devolucion"
    ) {
        const costo = numero(
            elemento(
                "movimiento-costo-unitario"
            ).value
        );

        if (costo < 0) {
            throw new Error(
                "El costo no puede ser negativo."
            );
        }

        datos.costo_unitario = costo;
    }

    if (tipo === "salida") {
        const valorPrecio = elemento(
            "movimiento-precio-unitario"
        ).value;

        if (valorPrecio !== "") {
            const precio = numero(valorPrecio);

            if (precio < 0) {
                throw new Error(
                    "El precio no puede ser negativo."
                );
            }

            datos.precio_unitario = precio;
        }
    }

    const producto = estado.productos.find(
        (item) =>
            Number(item.id) === productoId
    );
    const controlaLotes = Boolean(
        producto?.controla_lotes
        || producto?.controla_vencimiento
    );
    const controlaVencimiento = Boolean(
        producto?.controla_vencimiento
    );

    if (
        tipo === "ajuste"
        && controlaLotes
    ) {
        throw new Error(
            "No se permite un ajuste global "
            + "en productos controlados por lote."
        );
    }

    if (
        (
            tipo === "entrada"
            || tipo === "devolucion"
        )
        && controlaLotes
    ) {
        const numeroLote = elemento(
            "movimiento-numero-lote"
        ).value.trim();
        const fechaVencimiento = elemento(
            "movimiento-fecha-vencimiento"
        ).value;

        if (!numeroLote) {
            throw new Error(
                "El número de lote es obligatorio."
            );
        }

        if (
            controlaVencimiento
            && !fechaVencimiento
        ) {
            throw new Error(
                "La fecha de vencimiento "
                + "es obligatoria."
            );
        }

        datos.numero_lote = numeroLote;

        if (fechaVencimiento) {
            datos.fecha_vencimiento = (
                fechaVencimiento
            );
        }
    }

    return datos;
}

async function guardarMovimiento(evento) {
    evento.preventDefault();

    const boton = elemento(
        "guardar-movimiento"
    );

    try {
        const datos = construirMovimiento();

        boton.disabled = true;
        boton.textContent = "Registrando…";

        await solicitarJson(
            configuracion.apiInventario,
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
                body: JSON.stringify(datos),
            }
        );

        cerrarFormulario();

        await cargarPanel();

        notificar(
            "Movimiento registrado correctamente.",
            "exito"
        );
    } catch (error) {
        notificar(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = (
            "Registrar movimiento"
        );
    }
}

async function cargarProductos() {
    const datos = await solicitarJson(
        configuracion.apiProductos
    );

    estado.productos = datos.productos || [];
    renderizarProductos();
}

async function cargarStock() {
    const datos = await solicitarJson(
        configuracion.apiStock
    );

    estado.stock = datos.stock || [];
    renderizarResumen();
    renderizarStock();
}

async function cargarLotes() {
    if (!configuracion.apiLotes) {
        estado.lotes = [];
        renderizarResumenLotes();
        renderizarLotes();
        return;
    }

    const datos = await solicitarJson(
        configuracion.apiLotes
    );

    estado.lotes = datos.lotes || [];
    renderizarResumenLotes();
    renderizarLotes();
}

async function cargarMovimientos() {
    const separador = (
        configuracion.apiMovimientos.includes("?")
            ? "&"
            : "?"
    );

    const datos = await solicitarJson(
        `${configuracion.apiMovimientos}`
        + `${separador}limite=100`
    );

    estado.movimientos = (
        datos.movimientos || []
    );

    renderizarMovimientos();
}

async function cargarPanel() {
    const boton = elemento(
        "actualizar-inventario"
    );

    try {
        if (boton) {
            boton.disabled = true;
            boton.textContent = "Actualizando…";
        }

        await Promise.all([
            cargarProductos(),
            cargarStock(),
            cargarLotes(),
            cargarMovimientos(),
        ]);
    } catch (error) {
        notificar(error.message);
    } finally {
        if (boton) {
            boton.disabled = false;
            boton.textContent = "Actualizar";
        }
    }
}

function registrarEventos() {
    elemento("abrir-escaner")?.addEventListener("click", abrirEscaner);
    elemento("cerrar-escaner")?.addEventListener("click", detenerEscaner);
    elemento("buscar-codigo-manual")?.addEventListener(
        "click",
        () => seleccionarProductoEscaneado(
            elemento("codigo-escaneado-manual")?.value
        )
    );
    elemento("codigo-escaneado-manual")?.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                seleccionarProductoEscaneado(evento.currentTarget.value);
            }
        }
    );
    elemento(
        "nuevo-movimiento"
    )?.addEventListener(
        "click",
        () => abrirFormulario()
    );

    elemento(
        "actualizar-inventario"
    )?.addEventListener(
        "click",
        cargarPanel
    );

    elemento(
        "cerrar-modal-movimiento"
    )?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento(
        "cancelar-movimiento"
    )?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento(
        "formulario-movimiento"
    )?.addEventListener(
        "submit",
        guardarMovimiento
    );

    elemento(
        "movimiento-tipo"
    )?.addEventListener(
        "change",
        actualizarCamposMovimiento
    );

    elemento(
        "movimiento-producto"
    )?.addEventListener(
        "change",
        actualizarCamposMovimiento
    );

    elemento(
        "buscar-inventario"
    )?.addEventListener(
        "input",
        renderizarStock
    );

    elemento(
        "filtrar-existencia"
    )?.addEventListener(
        "change",
        renderizarStock
    );

    elemento(
        "filtrar-vencimiento"
    )?.addEventListener(
        "change",
        renderizarLotes
    );

    elemento(
        "modal-movimiento"
    )?.addEventListener(
        "click",
        (evento) => {
            if (
                evento.target
                === elemento("modal-movimiento")
            ) {
                cerrarFormulario();
            }
        }
    );

    window.addEventListener(
        "keydown",
        (evento) => {
            if (
                evento.key === "Escape"
                && !elemento(
                    "modal-movimiento"
                )?.hidden
            ) {
                cerrarFormulario();
            }
        }
    );
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();
        renderizarTiposMovimiento();

        const botonNuevo = elemento(
            "nuevo-movimiento"
        );

        if (
            botonNuevo
            && !permisosDisponibles().length
        ) {
            botonNuevo.hidden = true;
        }

        await cargarPanel();

        const parametros = new URLSearchParams(window.location.search);
        if (parametros.has("accion") || parametros.get("escanear") === "1") {
            abrirFormulario();
        }
        if (parametros.get("escanear") === "1") {
            await abrirEscaner();
        }
    }
);
