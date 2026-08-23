"use strict";

const configuracion = Object.freeze({
    apiStock: document.body.dataset.apiStock,
    apiMovimientos:
        document.body.dataset.apiMovimientos,
    apiAnalitica:
        document.body.dataset.apiAnalitica,
    apiResumen:
        document.body.dataset.apiResumen,
    apiExportar:
        document.body.dataset.apiExportar,
    bodegaId:
        document.body.dataset.bodegaId,
    permisoAnalitica:
        document.body.dataset.permisoAnalitica
        === "true",
    permisoExportar:
        document.body.dataset.permisoExportar
        === "true",
    permisoEjecutivo:
        document.body.dataset.permisoEjecutivo
        === "true",
});

const estado = {
    stock: [],
    movimientos: [],
    analitica: null,
    productos: new Map(),
};

const formatoMoneda = new Intl.NumberFormat(
    "es-CL",
    {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
    },
);

const formatoNumero = new Intl.NumberFormat(
    "es-CL",
    {
        maximumFractionDigits: 3,
    },
);

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

    if (texto !== "") {
        nodo.textContent = texto;
    }

    return nodo;
}

function limpiar(nodo) {
    nodo.replaceChildren();
}

function numero(valor) {
    const resultado = Number(valor);

    return Number.isFinite(resultado)
        ? resultado
        : 0;
}

function moneda(valor) {
    return formatoMoneda.format(
        numero(valor)
    );
}

function cantidad(valor) {
    return formatoNumero.format(
        numero(valor)
    );
}

function fechaIsoLocal(fecha) {
    const anio = fecha.getFullYear();
    const mes = String(
        fecha.getMonth() + 1
    ).padStart(2, "0");
    const dia = String(
        fecha.getDate()
    ).padStart(2, "0");

    return `${anio}-${mes}-${dia}`;
}

function configurarPeriodoInicial() {
    const hasta = new Date();
    const desde = new Date();

    desde.setDate(
        hasta.getDate() - 29
    );

    elemento(
        "filtro-desde-reportes"
    ).value = fechaIsoLocal(desde);

    elemento(
        "filtro-hasta-reportes"
    ).value = fechaIsoLocal(hasta);
}

function parametrosPeriodo() {
    const parametros = new URLSearchParams();

    parametros.set(
        "desde",
        elemento(
            "filtro-desde-reportes"
        ).value,
    );

    parametros.set(
        "hasta",
        elemento(
            "filtro-hasta-reportes"
        ).value,
    );

    parametros.set(
        "bodega_id",
        configuracion.bodegaId,
    );

    return parametros;
}

function notificar(
    mensaje,
    tipo = "exito",
) {
    const contenedor = elemento(
        "notificacion"
    );

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
        4000,
    );
}

async function solicitarJson(url) {
    const respuesta = await fetch(
        url,
        {
            credentials: "same-origin",
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
            || (
                "No fue posible cargar "
                + "el reporte."
            ),
        );
    }

    return datos;
}

function celda(texto) {
    return crearElemento(
        "td",
        "",
        texto,
    );
}

function actualizarResumenStock() {
    const totales = estado.stock.reduce(
        (acumulado, fila) => {
            acumulado.stock += numero(
                fila.cantidad
            );
            acumulado.disponible += numero(
                fila.disponible
            );
            acumulado.valor += numero(
                fila.valor
            );

            return acumulado;
        },
        {
            stock: 0,
            disponible: 0,
            valor: 0,
        },
    );

    elemento(
        "resumen-valor-inventario"
    ).textContent = moneda(totales.valor);

    elemento(
        "resumen-stock-total"
    ).textContent = cantidad(totales.stock);

    elemento(
        "resumen-stock-disponible"
    ).textContent = cantidad(
        totales.disponible
    );
}

function renderizarStock() {
    const cuerpo = elemento(
        "tabla-stock-reportes"
    );
    const mensaje = elemento(
        "estado-stock-reportes"
    );

    limpiar(cuerpo);
    estado.productos.clear();

    if (!estado.stock.length) {
        mensaje.textContent = (
            "No existe inventario para "
            + "la ubicación activa."
        );
        mensaje.hidden = false;
        actualizarResumenStock();
        return;
    }

    for (const fila of estado.stock) {
        estado.productos.set(
            String(fila.producto_id),
            fila.producto,
        );

        const registro = crearElemento("tr");

        registro.append(
            celda(fila.producto || "Producto"),
            celda(fila.bodega || "Bodega"),
            celda(cantidad(fila.cantidad)),
            celda(cantidad(fila.reservada)),
            celda(cantidad(fila.disponible)),
            celda(moneda(fila.costo_promedio)),
            celda(moneda(fila.valor)),
        );

        cuerpo.append(registro);
    }

    mensaje.hidden = true;
    actualizarResumenStock();
}

async function cargarStock() {
    const mensaje = elemento(
        "estado-stock-reportes"
    );

    mensaje.textContent = (
        "Cargando inventario..."
    );
    mensaje.hidden = false;

    const parametros = new URLSearchParams({
        bodega_id: configuracion.bodegaId,
    });

    const datos = await solicitarJson(
        `${configuracion.apiStock}?${parametros}`
    );

    estado.stock = Array.isArray(datos.stock)
        ? datos.stock
        : [];

    renderizarStock();
}

function nombreTipoMovimiento(tipo) {
    const nombres = {
        entrada: "Entrada",
        salida: "Salida",
        ajuste: "Ajuste",
        devolucion: "Devolución",
        transferencia: "Transferencia",
    };

    return (
        nombres[tipo]
        || String(tipo || "Movimiento")
            .replaceAll("_", " ")
    );
}

function fechaLegible(valor) {
    if (!valor) {
        return "—";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return valor;
    }

    return fecha.toLocaleString(
        "es-CL",
        {
            dateStyle: "short",
            timeStyle: "short",
        },
    );
}

function renderizarMovimientos() {
    const cuerpo = elemento(
        "tabla-movimientos-reportes"
    );
    const mensaje = elemento(
        "estado-movimientos-reportes"
    );

    limpiar(cuerpo);

    if (!estado.movimientos.length) {
        mensaje.textContent = (
            "No hay movimientos dentro "
            + "del periodo seleccionado."
        );
        mensaje.hidden = false;
        return;
    }

    for (const movimiento of estado.movimientos) {
        const registro = crearElemento("tr");

        const producto = (
            estado.productos.get(
                String(movimiento.producto_id)
            )
            || `Producto ${movimiento.producto_id}`
        );

        const cantidadMovimiento = numero(
            movimiento.cantidad
        );

        const cantidadNodo = crearElemento(
            "span",
            cantidadMovimiento < 0
                ? "cantidad cantidad--salida"
                : "cantidad cantidad--entrada",
            (
                cantidadMovimiento > 0
                    ? "+"
                    : ""
            ) + cantidad(cantidadMovimiento),
        );

        const celdaCantidad = crearElemento("td");
        celdaCantidad.append(cantidadNodo);

        registro.append(
            celda(fechaLegible(movimiento.fecha)),
            celda(
                nombreTipoMovimiento(
                    movimiento.tipo
                )
            ),
            celda(producto),
            celdaCantidad,
            celda(cantidad(movimiento.stock_nuevo)),
            celda(movimiento.motivo || "—"),
        );

        cuerpo.append(registro);
    }

    mensaje.hidden = true;
}

async function cargarMovimientos() {
    const mensaje = elemento(
        "estado-movimientos-reportes"
    );

    mensaje.textContent = (
        "Cargando movimientos..."
    );
    mensaje.hidden = false;

    const parametros = parametrosPeriodo();
    parametros.set("limite", "500");

    const datos = await solicitarJson(
        (
            `${configuracion.apiMovimientos}`
            + `?${parametros}`
        ),
    );

    estado.movimientos = Array.isArray(
        datos.movimientos
    )
        ? datos.movimientos
        : [];

    renderizarMovimientos();
}

function crearFilaLista(
    titulo,
    detalle,
    valor = "",
) {
    const fila = crearElemento(
        "div",
        "reporte-lista__fila",
    );

    const informacion = crearElemento("div");

    informacion.append(
        crearElemento(
            "strong",
            "",
            titulo,
        ),
        crearElemento(
            "span",
            "",
            detalle,
        ),
    );

    fila.append(informacion);

    if (valor) {
        fila.append(
            crearElemento(
                "b",
                "",
                valor,
            ),
        );
    }

    return fila;
}

function renderizarLista(
    id,
    filas,
    construir,
    vacio,
) {
    const contenedor = elemento(id);
    limpiar(contenedor);

    if (!filas.length) {
        contenedor.append(
            crearElemento(
                "p",
                "reporte-lista__vacio",
                vacio,
            ),
        );
        return;
    }

    for (const fila of filas) {
        contenedor.append(
            construir(fila)
        );
    }
}

function renderizarAnalitica() {
    const datos = estado.analitica;

    elemento(
        "analitica-ingresos"
    ).textContent = moneda(datos.ingresos);

    elemento(
        "analitica-margen"
    ).textContent = moneda(
        datos.margen_bruto
    );

    elemento(
        "analitica-unidades"
    ).textContent = cantidad(
        datos.unidades_vendidas
    );

    elemento(
        "analitica-cobertura"
    ).textContent = (
        datos.dias_cobertura_actual === null
            ? "—"
            : (
                cantidad(
                    datos.dias_cobertura_actual
                )
                + " días"
            )
    );

    renderizarLista(
        "productos-mas-vendidos",
        datos.productos_mas_vendidos || [],
        (fila) => crearFilaLista(
            fila.producto,
            (
                `${cantidad(fila.unidades)} unidades`
                + ` · ${moneda(fila.ingresos)}`
            ),
            moneda(fila.margen_bruto),
        ),
        "No hay ventas confirmadas en el periodo.",
    );

    renderizarLista(
        "productos-sin-movimiento",
        datos.productos_sin_movimiento || [],
        (fila) => crearFilaLista(
            fila.producto,
            fila.ultimo_movimiento
                ? (
                    "Ultimo movimiento: "
                    + fechaLegible(
                        fila.ultimo_movimiento
                    )
                )
                : "Sin movimientos registrados",
            `${cantidad(fila.stock)} unidades`,
        ),
        "Todos los productos registran movimiento.",
    );

    renderizarLista(
        "productos-sobrestock",
        datos.sobrestock || [],
        (fila) => crearFilaLista(
            fila.producto,
            "Stock sobre el máximo configurado",
            `${cantidad(fila.exceso)} de exceso`,
        ),
        "No se detecta sobrestock.",
    );
}

async function cargarAnalitica() {
    const bloqueado = elemento(
        "analitica-bloqueada"
    );
    const contenidoAnalitica = elemento(
        "contenido-analitica"
    );

    if (!configuracion.permisoAnalitica) {
        bloqueado.hidden = false;
        contenidoAnalitica.hidden = true;
        return;
    }

    bloqueado.hidden = true;
    contenidoAnalitica.hidden = false;

    const parametros = parametrosPeriodo();
    parametros.set("limite", "10");

    const datos = await solicitarJson(
        (
            `${configuracion.apiAnalitica}`
            + `?${parametros}`
        ),
    );

    estado.analitica = datos;
    renderizarAnalitica();
}

async function cargarReportes() {
    const boton = elemento(
        "actualizar-reportes"
    );

    boton.disabled = true;

    try {
        await cargarStock();

        await Promise.all([
            cargarMovimientos(),
            cargarAnalitica(),
        ]);
    }
    catch (error) {
        notificar(
            error.message,
            "error",
        );
    }
    finally {
        boton.disabled = false;
    }
}

function exportarReporte(
    reporte,
    formato,
) {
    if (!configuracion.permisoExportar) {
        notificar(
            "El plan actual no permite exportaciones.",
            "error",
        );
        return;
    }

    const parametros = parametrosPeriodo();

    const url = (
        `${configuracion.apiExportar}/`
        + `${reporte}.${formato}`
        + `?${parametros}`
    );

    window.location.assign(url);
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
        "actualizar-reportes"
    ).addEventListener(
        "click",
        cargarReportes,
    );

    for (
        const boton
        of document.querySelectorAll(
            ".exportar-reporte"
        )
    ) {
        boton.addEventListener(
            "click",
            () => {
                exportarReporte(
                    boton.dataset.reporte,
                    boton.dataset.formato,
                );
            },
        );
    }

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
        configurarPeriodoInicial();
        registrarEventos();
        await cargarReportes();
    },
);
