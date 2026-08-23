"use strict";

const configuracion = Object.freeze({
    apiVentas: document.body.dataset.apiVentas,
    apiProductos: document.body.dataset.apiProductos,
    apiClientes: document.body.dataset.apiClientes,
    apiStock: document.body.dataset.apiStock,
    bodegaId: Number(document.body.dataset.bodegaId),
    puedeCrear:
        document.body.dataset.permisoCrear === "true",
    puedeReservar:
        document.body.dataset.permisoReservar === "true",
    puedeConfirmar:
        document.body.dataset.permisoConfirmar === "true",
    puedeCancelar:
        document.body.dataset.permisoCancelar === "true",
});

const estado = {
    ventas: [],
    productos: [],
    clientes: [],
    stockPorProducto: new Map(),
};

function elemento(id) {
    return document.getElementById(id);
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

function limpiar(nodo) {
    while (nodo?.firstChild) {
        nodo.removeChild(nodo.firstChild);
    }
}

function obtenerTokenCsrf() {
    return document.querySelector(
        'input[name="csrf_token"]'
    )?.value || "";
}

function formatearDinero(valor, moneda = "CLP") {
    return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: moneda || "CLP",
        maximumFractionDigits: 0,
    }).format(Number(valor || 0));
}

function formatearFecha(valor) {
    if (!valor) {
        return "—";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return String(valor);
    }

    return new Intl.DateTimeFormat("es-CL", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(fecha);
}

function nombreEstado(valor) {
    const nombres = {
        borrador: "Borrador",
        reservada: "Reservada",
        confirmada: "Confirmada",
        cancelada: "Cancelada",
    };

    return nombres[valor] || valor || "Sin estado";
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

async function solicitarJson(url, opciones = {}) {
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        ...opciones,
        headers: {
            Accept: "application/json",
            ...(opciones.headers || {}),
        },
    });

    let datos = {};

    if (respuesta.status !== 204) {
        try {
            datos = await respuesta.json();
        } catch {
            datos = {};
        }
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

function mostrarErrorFormulario(mensaje) {
    const error = elemento("error-venta");

    if (!error) {
        return;
    }

    error.textContent = mensaje || "";
    error.hidden = !mensaje;
}

function crearOpcion(valor, texto) {
    const opcion = document.createElement("option");
    opcion.value = String(valor);
    opcion.textContent = texto;
    return opcion;
}

function stockProducto(productoId) {
    return estado.stockPorProducto.get(
        Number(productoId)
    ) || {
        cantidad: 0,
        reservada: 0,
        disponible: 0,
    };
}

function crearSelectorProductos() {
    const selector = document.createElement("select");
    selector.className = "campo linea-producto";
    selector.required = true;

    selector.appendChild(
        crearOpcion("", "Selecciona un producto")
    );

    estado.productos.forEach((producto) => {
        const stock = stockProducto(producto.id);

        selector.appendChild(
            crearOpcion(
                producto.id,
                `${producto.codigo} · ${producto.nombre} · ` +
                `Disponible: ${Number(stock.disponible)}`
            )
        );
    });

    return selector;
}

function crearGrupoLinea(etiquetaTexto, control) {
    const grupo = crearElemento("div");
    const etiqueta = crearElemento(
        "label",
        etiquetaTexto
    );

    grupo.appendChild(etiqueta);
    grupo.appendChild(control);

    return grupo;
}

function crearSelectorPresentaciones() {
    const selector = document.createElement("select");

    selector.className =
        "campo linea-presentacion";
    selector.disabled = true;

    const opcion = crearOpcion(
        "",
        "Unidad base"
    );

    opcion.dataset.factor = "1";
    opcion.dataset.abreviatura = "un";

    selector.appendChild(opcion);

    return selector;
}


function actualizarEquivalenciaLinea(linea) {
    const selector = linea.querySelector(
        ".linea-presentacion"
    );
    const cantidad = Number(
        linea.querySelector(
            ".linea-cantidad"
        )?.value || 0
    );
    const opcion = selector?.selectedOptions[0];
    const factor = Number(
        opcion?.dataset.factor || 1
    );
    const cantidadBase = cantidad * factor;
    const abreviatura = (
        opcion?.dataset.abreviatura
        || "unidad base"
    );
    const equivalencia = linea.querySelector(
        ".linea-equivalencia"
    );

    if (!equivalencia) {
        return;
    }

    if (
        !Number.isFinite(cantidad)
        || cantidad <= 0
    ) {
        equivalencia.textContent =
            "Ingresa una cantidad para calcular la equivalencia.";
        return;
    }

    equivalencia.textContent = (
        `${cantidad} ? ${factor} = `
        + `${cantidadBase.toFixed(3)} `
        + `${abreviatura} de inventario`
    );
}


function actualizarPrecioPresentacion(linea) {
    const productoId = Number(
        linea.querySelector(
            ".linea-producto"
        )?.value || 0
    );
    const producto = estado.productos.find(
        (actual) =>
            Number(actual.id) === productoId
    );
    const selector = linea.querySelector(
        ".linea-presentacion"
    );
    const opcion = selector?.selectedOptions[0];
    const factor = Number(
        opcion?.dataset.factor || 1
    );
    const precio = linea.querySelector(
        ".linea-precio"
    );

    if (!producto || !precio) {
        return;
    }

    precio.value = (
        Number(producto.precio_venta || 0)
        * factor
    ).toFixed(2);
}


async function cargarPresentacionesLinea(
    linea,
    productoId,
    presentacionSeleccionada = ""
) {
    const selector = linea.querySelector(
        ".linea-presentacion"
    );

    if (!selector) {
        return;
    }

    limpiar(selector);
    selector.disabled = true;

    const base = crearOpcion(
        "",
        "Unidad base"
    );

    base.dataset.factor = "1";
    base.dataset.abreviatura = "unidad base";
    selector.appendChild(base);

    if (!productoId) {
        selector.value = "";
        actualizarEquivalenciaLinea(linea);
        return;
    }

    try {
        const datos = await solicitarJson(
            `${configuracion.apiProductos}/`
            + `${productoId}/presentaciones`
        );

        const unidadBase = datos.unidad_base || {};

        base.textContent = (
            `${unidadBase.nombre || "Unidad base"} `
            + "(unidad base)"
        );
        base.dataset.factor = "1";
        base.dataset.abreviatura = (
            unidadBase.abreviatura
            || unidadBase.nombre
            || "unidad base"
        );

        (datos.presentaciones || [])
            .filter(
                (presentacion) =>
                    presentacion.activa
            )
            .forEach((presentacion) => {
                const opcion = crearOpcion(
                    presentacion.id,
                    (
                        `${presentacion.nombre} `
                        + `(? ${presentacion.factor_base})`
                    )
                );

                opcion.dataset.factor =
                    presentacion.factor_base;
                opcion.dataset.abreviatura = (
                    presentacion.abreviatura
                    || presentacion.nombre
                );

                selector.appendChild(opcion);
            });

        selector.disabled = false;

        const existe = [
            ...selector.options,
        ].some(
            (opcion) =>
                opcion.value
                === String(
                    presentacionSeleccionada
                    || ""
                )
        );

        selector.value = existe
            ? String(
                presentacionSeleccionada
                || ""
            )
            : "";

        actualizarPrecioPresentacion(linea);
        actualizarEquivalenciaLinea(linea);
    } catch (error) {
        selector.disabled = false;
        selector.value = "";
        actualizarPrecioPresentacion(linea);
        actualizarEquivalenciaLinea(linea);
        notificar(error.message);
    }
}


function agregarLineaVenta(datos = {}) {
    const contenedor = elemento("lineas-venta");

    if (!contenedor) {
        return;
    }

    const linea = crearElemento(
        "div",
        "",
        "linea-venta"
    );

    const selector = crearSelectorProductos();
    selector.value = String(
        datos.producto_id || ""
    );

    const presentacion =
        crearSelectorPresentaciones();

    const cantidad = document.createElement("input");
    cantidad.className = "campo linea-cantidad";
    cantidad.type = "number";
    cantidad.min = "0.001";
    cantidad.step = "0.001";
    cantidad.value = String(
        datos.cantidad_presentacion
        || datos.cantidad
        || "1"
    );
    cantidad.required = true;

    const precio = document.createElement("input");
    precio.className = "campo linea-precio";
    precio.type = "number";
    precio.min = "0";
    precio.step = "0.01";
    precio.value = String(
        datos.precio_presentacion
        || datos.precio_unitario
        || "0"
    );
    precio.required = true;

    const equivalencia = crearElemento(
        "p",
        "",
        "linea-equivalencia"
    );

    const descuento = document.createElement("input");
    descuento.type = "hidden";
    descuento.className = "linea-descuento";
    descuento.value = String(
        datos.descuento || "0"
    );

    const impuesto = document.createElement("input");
    impuesto.type = "hidden";
    impuesto.className = "linea-impuesto";
    impuesto.value = String(
        datos.impuesto || "0"
    );

    const seriales = document.createElement("textarea");
    seriales.className = "campo linea-seriales";
    seriales.rows = 2;
    seriales.placeholder = "Seriales, uno por línea (sólo productos serializados)";
    seriales.value = (datos.seriales || []).join("\n");

    selector.addEventListener(
        "change",
        async () => {
            await cargarPresentacionesLinea(
                linea,
                Number(selector.value || 0)
            );
        }
    );

    presentacion.addEventListener(
        "change",
        () => {
            actualizarPrecioPresentacion(linea);
            actualizarEquivalenciaLinea(linea);
        }
    );

    cantidad.addEventListener(
        "input",
        () => actualizarEquivalenciaLinea(linea)
    );

    const quitar = crearElemento(
        "button",
        "Quitar",
        "boton boton--peligro boton--pequeno"
    );

    quitar.type = "button";

    quitar.addEventListener("click", () => {
        linea.remove();

        if (!contenedor.children.length) {
            agregarLineaVenta();
        }
    });

    linea.appendChild(
        crearGrupoLinea("Producto", selector)
    );
    linea.appendChild(
        crearGrupoLinea(
            "Presentación",
            presentacion
        )
    );
    linea.appendChild(
        crearGrupoLinea("Cantidad", cantidad)
    );
    linea.appendChild(
        crearGrupoLinea(
            "Precio por presentación",
            precio
        )
    );
    linea.appendChild(quitar);
    linea.appendChild(equivalencia);
    linea.appendChild(descuento);
    linea.appendChild(impuesto);
    linea.appendChild(
        crearGrupoLinea("Números de serie", seriales)
    );

    contenedor.appendChild(linea);

    actualizarEquivalenciaLinea(linea);

    if (selector.value) {
        cargarPresentacionesLinea(
            linea,
            Number(selector.value),
            datos.presentacion_id
        );
    }
}


function restablecerFormulario() {
    elemento("formulario-venta")?.reset();
    elemento("venta-moneda").value = "CLP";

    const lineas = elemento("lineas-venta");
    limpiar(lineas);
    agregarLineaVenta();

    mostrarErrorFormulario("");
}

function abrirFormulario() {
    if (!configuracion.puedeCrear) {
        notificar(
            "No tienes permiso para crear ventas."
        );
        return;
    }

    restablecerFormulario();

    elemento("modal-venta").hidden = false;
    elemento("venta-numero")?.focus();
}

function cerrarFormulario() {
    elemento("modal-venta").hidden = true;
    mostrarErrorFormulario("");
}

function construirDatosVenta() {
    const numero = elemento("venta-numero")
        .value
        .trim();

    if (!numero) {
        throw new Error(
            "El número de venta es obligatorio."
        );
    }

    const lineas = Array.from(
        elemento("lineas-venta").children
    );

    const items = lineas.map((linea) => {
        const productoId = Number(
            linea.querySelector(
                ".linea-producto"
            ).value
        );

        const cantidad = Number(
            linea.querySelector(
                ".linea-cantidad"
            ).value
        );

        const precioUnitario = Number(
            linea.querySelector(
                ".linea-precio"
            ).value
        );

        const selectorPresentacion =
            linea.querySelector(
                ".linea-presentacion"
            );
        const opcionPresentacion =
            selectorPresentacion
                ?.selectedOptions[0];
        const presentacionId = Number(
            selectorPresentacion?.value || 0
        );
        const factor = Number(
            opcionPresentacion
                ?.dataset.factor || 1
        );

        const conversion = {
            factor_conversion: factor,
        };

        const cantidadBase = (
            cantidad
            * conversion.factor_conversion
        );

        const descuento = Number(
            linea.querySelector(
                ".linea-descuento"
            ).value || 0
        );

        const impuesto = Number(
            linea.querySelector(
                ".linea-impuesto"
            ).value || 0
        );

        const seriales = linea.querySelector(".linea-seriales").value
            .split(/\r?\n|,/)
            .map((serial) => serial.trim())
            .filter(Boolean);

        if (!productoId) {
            throw new Error(
                "Selecciona un producto en cada línea."
            );
        }

        if (!Number.isFinite(cantidad) || cantidad <= 0) {
            throw new Error(
                "Las cantidades deben ser mayores que cero."
            );
        }

        const stock = stockProducto(productoId);

        if (
            cantidadBase
            > Number(stock.disponible)
        ) {
            throw new Error(
                `La cantidad solicitada supera el stock ` +
                `disponible (${stock.disponible}).`
            );
        }

        if (
            !Number.isFinite(precioUnitario) ||
            precioUnitario < 0
        ) {
            throw new Error(
                "Los precios no pueden ser negativos."
            );
        }

        return {
            producto_id: productoId,
            presentacion_id:
                presentacionId || null,
            cantidad,
            precio_unitario: precioUnitario,
            descuento,
            impuesto,
            seriales,
        };
    });

    if (!items.length) {
        throw new Error(
            "Agrega al menos un producto."
        );
    }

    const productosUnicos = new Set(
        items.map((item) => item.producto_id)
    );

    if (productosUnicos.size !== items.length) {
        throw new Error(
            "No puedes repetir un producto en la venta."
        );
    }

    const clienteTexto =
        elemento("venta-cliente").value;

    return {
        numero,
        bodega_id: configuracion.bodegaId,
        cliente_id: clienteTexto
            ? Number(clienteTexto)
            : null,
        moneda:
            elemento("venta-moneda").value || "CLP",
        observaciones:
            elemento("venta-observaciones")
                .value
                .trim() || null,
        items,
    };
}

async function guardarVenta(evento) {
    evento.preventDefault();

    if (!configuracion.puedeCrear) {
        mostrarErrorFormulario(
            "No tienes permiso para crear ventas."
        );
        return;
    }

    const boton = elemento("guardar-venta");

    try {
        mostrarErrorFormulario("");

        const datos = construirDatosVenta();

        boton.disabled = true;
        boton.textContent = "Creando…";

        await solicitarJson(configuracion.apiVentas, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": obtenerTokenCsrf(),
            },
            body: JSON.stringify(datos),
        });

        cerrarFormulario();
        await cargarVentas();

        notificar("Venta creada correctamente.");
    } catch (error) {
        mostrarErrorFormulario(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = "Crear borrador";
    }
}

function crearBoton(texto, clase, accion) {
    const boton = crearElemento(
        "button",
        texto,
        clase
    );

    boton.type = "button";
    boton.addEventListener("click", accion);

    return boton;
}

async function ejecutarAccion(
    venta,
    accion,
    confirmacion,
    exito,
    cuerpo = null
) {
    if (confirmacion && !window.confirm(confirmacion)) {
        return;
    }

    try {
        const opciones = {
            method: "POST",
            headers: {
                "X-CSRFToken": obtenerTokenCsrf(),
            },
        };

        if (cuerpo) {
            opciones.headers["Content-Type"] =
                "application/json";
            opciones.body = JSON.stringify(cuerpo);
        }

        await solicitarJson(
            `${configuracion.apiVentas}/${venta.id}/${accion}`,
            opciones
        );

        await Promise.all([
            cargarStock(),
            cargarVentas(),
        ]);

        notificar(exito);
    } catch (error) {
        notificar(error.message);
    }
}

function reservarVenta(venta) {
    return ejecutarAccion(
        venta,
        "reservar",
        `¿Deseas reservar el inventario para ` +
        `"${venta.numero}"?`,
        "Inventario reservado correctamente."
    );
}

function confirmarVenta(venta) {
    return ejecutarAccion(
        venta,
        "confirmar",
        `¿Deseas confirmar la venta "${venta.numero}"? ` +
        "Esta acción descontará el inventario.",
        "Venta confirmada correctamente."
    );
}

function cancelarVenta(venta) {
    const motivo = window.prompt(
        `Indica el motivo de cancelación de ` +
        `"${venta.numero}":`
    );

    if (motivo === null) {
        return;
    }

    if (!motivo.trim()) {
        notificar(
            "El motivo de cancelación es obligatorio."
        );
        return;
    }

    return ejecutarAccion(
        venta,
        "cancelar",
        "¿Confirmas la cancelación de esta venta?",
        "Venta cancelada correctamente.",
        {
            motivo: motivo.trim(),
        }
    );
}

function agregarAcciones(acciones, venta) {
    if (
        venta.estado === "borrador" &&
        configuracion.puedeReservar
    ) {
        acciones.appendChild(
            crearBoton(
                "Reservar",
                "boton boton--primario boton--pequeno",
                () => reservarVenta(venta)
            )
        );
    }

    if (
        venta.estado === "reservada" &&
        configuracion.puedeConfirmar
    ) {
        acciones.appendChild(
            crearBoton(
                "Confirmar",
                "boton boton--primario boton--pequeno",
                () => confirmarVenta(venta)
            )
        );
    }

    if (
        ["borrador", "reservada"].includes(
            venta.estado
        ) &&
        configuracion.puedeCancelar
    ) {
        acciones.appendChild(
            crearBoton(
                "Cancelar",
                "boton boton--peligro boton--pequeno",
                () => cancelarVenta(venta)
            )
        );
    }

    if (!acciones.children.length) {
        acciones.appendChild(
            crearElemento(
                "span",
                "Sin acciones",
                "tabla__detalle"
            )
        );
    }
}

function ventasFiltradas() {
    const busqueda = elemento("buscar-ventas")
        .value
        .trim()
        .toLocaleLowerCase("es");

    if (!busqueda) {
        return estado.ventas;
    }

    return estado.ventas.filter((venta) => {
        return [
            venta.numero,
            venta.cliente_nombre,
        ].some((valor) =>
            String(valor || "")
                .toLocaleLowerCase("es")
                .includes(busqueda)
        );
    });
}

function renderizarVentas() {
    const cuerpo = elemento("tabla-ventas");

    if (!cuerpo) {
        return;
    }

    const ventas = ventasFiltradas();
    limpiar(cuerpo);

    elemento("cantidad-ventas").textContent =
        `${ventas.length} venta${
            ventas.length === 1 ? "" : "s"
        }`;

    if (!ventas.length) {
        const fila = crearElemento("tr");

        const celda = crearElemento(
            "td",
            "No se encontraron ventas.",
            "tabla__vacio"
        );

        celda.colSpan = 7;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    ventas.forEach((venta) => {
        const fila = crearElemento("tr");

        const numero = crearElemento("td");

        numero.appendChild(
            crearElemento(
                "span",
                venta.numero,
                "tabla__principal"
            )
        );

        numero.appendChild(
            crearElemento(
                "span",
                venta.moneda || "CLP",
                "tabla__detalle"
            )
        );

        fila.appendChild(numero);

        fila.appendChild(
            crearElemento(
                "td",
                venta.cliente_nombre ||
                "Consumidor final"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(
                    venta.fecha_creacion
                )
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                `${venta.items.length} producto${
                    venta.items.length === 1 ? "" : "s"
                }`
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(
                    venta.total,
                    venta.moneda
                )
            )
        );

        const estadoCelda = crearElemento("td");

        estadoCelda.appendChild(
            crearElemento(
                "span",
                nombreEstado(venta.estado),
                `estado-venta estado-venta--${venta.estado}`
            )
        );

        fila.appendChild(estadoCelda);

        const acciones = crearElemento(
            "td",
            "",
            "acciones-fila"
        );

        agregarAcciones(acciones, venta);
        fila.appendChild(acciones);

        cuerpo.appendChild(fila);
    });
}

function mostrarCarga() {
    const cuerpo = elemento("tabla-ventas");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando ventas…",
        "tabla__vacio"
    );

    celda.colSpan = 7;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

async function cargarVentas() {
    mostrarCarga();

    try {
        const estadoSeleccionado =
            elemento("filtrar-estado").value;

        const parametros = new URLSearchParams();

        if (estadoSeleccionado) {
            parametros.set(
                "estado",
                estadoSeleccionado
            );
        }

        const consulta = parametros.toString();

        const url = consulta
            ? `${configuracion.apiVentas}?${consulta}`
            : configuracion.apiVentas;

        const datos = await solicitarJson(url);

        estado.ventas = datos.ventas || [];
        renderizarVentas();
    } catch (error) {
        estado.ventas = [];
        renderizarVentas();
        notificar(error.message);
    }
}

async function cargarStock() {
    const parametros = new URLSearchParams({
        bodega_id: String(configuracion.bodegaId),
    });

    const datos = await solicitarJson(
        `${configuracion.apiStock}?${parametros}`
    );

    estado.stockPorProducto = new Map(
        (datos.stock || []).map((registro) => [
            Number(registro.producto_id),
            {
                cantidad: Number(registro.cantidad || 0),
                reservada: Number(registro.reservada || 0),
                disponible: Number(registro.disponible || 0),
            },
        ])
    );
}

async function cargarProductosYStock() {
    try {
        const [productos] = await Promise.all([
            solicitarJson(configuracion.apiProductos),
            cargarStock(),
        ]);

        estado.productos = productos.productos || [];
    } catch (error) {
        notificar(error.message);
    }
}

function abrirMenu() {
    document.body.classList.add("menu-abierto");

    elemento("abrir-menu")?.setAttribute(
        "aria-expanded",
        "true"
    );
}

function cerrarMenu() {
    document.body.classList.remove("menu-abierto");

    elemento("abrir-menu")?.setAttribute(
        "aria-expanded",
        "false"
    );
}


function renderizarOpcionesClientes() {
    const selector = elemento("venta-cliente");

    if (!selector) {
        return;
    }

    const valorSeleccionado = selector.value;

    limpiar(selector);

    const consumidorFinal = crearElemento(
        "option",
        "Consumidor final"
    );

    consumidorFinal.value = "";
    selector.appendChild(consumidorFinal);

    estado.clientes.forEach((cliente) => {
        const detalle = cliente.identificacion_fiscal
            ? ` ? ${cliente.identificacion_fiscal}`
            : "";

        const opcion = crearElemento(
            "option",
            `${cliente.nombre}${detalle}`
        );

        opcion.value = String(cliente.id);
        selector.appendChild(opcion);
    });

    const existeSeleccionado = [
        ...selector.options,
    ].some(
        (opcion) =>
            opcion.value === valorSeleccionado
    );

    selector.value = existeSeleccionado
        ? valorSeleccionado
        : "";
}

async function cargarClientes() {
    if (!configuracion.apiClientes) {
        estado.clientes = [];
        renderizarOpcionesClientes();
        return;
    }

    try {
        const datos = await solicitarJson(
            configuracion.apiClientes
        );

        estado.clientes = (
            datos.clientes || []
        ).filter(
            (cliente) => cliente.activo
        );

        renderizarOpcionesClientes();
    } catch (error) {
        estado.clientes = [];
        renderizarOpcionesClientes();
        notificar(error.message);
    }
}

function registrarEventos() {
    elemento("crear-venta")?.addEventListener(
        "click",
        abrirFormulario
    );

    elemento("cerrar-modal-venta")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento(
        "cancelar-formulario-venta"
    )?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("formulario-venta")?.addEventListener(
        "submit",
        guardarVenta
    );

    elemento("agregar-linea-venta")?.addEventListener(
        "click",
        () => agregarLineaVenta()
    );

    elemento("actualizar-ventas")?.addEventListener(
        "click",
        async () => {
            await Promise.all([
                cargarClientes(),
                cargarProductosYStock(),
            ]);
            await cargarVentas();
        }
    );

    elemento("filtrar-estado")?.addEventListener(
        "change",
        cargarVentas
    );

    elemento("ejecutar-busqueda")?.addEventListener(
        "click",
        renderizarVentas
    );

    elemento("buscar-ventas")?.addEventListener(
        "input",
        renderizarVentas
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
        if (
            evento.key === "Escape" &&
            !elemento("modal-venta")?.hidden
        ) {
            cerrarFormulario();
        }
    });
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();

        await Promise.all([
            cargarClientes(),
            cargarProductosYStock(),
        ]);

        await cargarVentas();
    }
);
