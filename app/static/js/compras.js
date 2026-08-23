"use strict";

const configuracion = Object.freeze({
    apiCompras: document.body.dataset.apiCompras,
    apiProveedores: document.body.dataset.apiProveedores,
    apiProductos: document.body.dataset.apiProductos,
    bodegaId: Number(document.body.dataset.bodegaId),
    puedeCrear:
        document.body.dataset.permisoCrear === "true",
    puedeEditar:
        document.body.dataset.permisoEditar === "true",
    puedeEnviar:
        document.body.dataset.permisoEnviar === "true",
    puedeRecibir:
        document.body.dataset.permisoRecibir === "true",
    puedeCancelar:
        document.body.dataset.permisoCancelar === "true",
});

const estado = {
    ordenes: [],
    proveedores: [],
    productos: [],
    presentaciones: new Map(),
    ordenRecepcion: null,
    ordenEdicion: null,
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

    const fechaTexto = String(valor).slice(0, 10);
    const partes = fechaTexto.split("-");

    if (partes.length !== 3) {
        return fechaTexto;
    }

    return `${partes[2]}-${partes[1]}-${partes[0]}`;
}

function nombreEstado(valor) {
    const nombres = {
        borrador: "Borrador",
        creada: "Creada",
        enviada: "Enviada",
        parcialmente_recibida: "Parcialmente recibida",
        recibida: "Recibida",
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
        headers: {
            Accept: "application/json",
            ...(opciones.headers || {}),
        },
        ...opciones,
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
    const error = elemento("error-compra");

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

function renderizarProveedores() {
    const selector = elemento("compra-proveedor");

    if (!selector) {
        return;
    }

    limpiar(selector);

    selector.appendChild(
        crearOpcion("", "Selecciona un proveedor")
    );

    estado.proveedores.forEach((proveedor) => {
        const detalle = proveedor.identificacion_fiscal
            ? ` · ${proveedor.identificacion_fiscal}`
            : "";

        selector.appendChild(
            crearOpcion(
                proveedor.id,
                `${proveedor.nombre}${detalle}`
            )
        );
    });
}

function crearSelectorProductos() {
    const selector = document.createElement("select");
    selector.className = "campo linea-producto";
    selector.required = true;

    selector.appendChild(
        crearOpcion("", "Selecciona un producto")
    );

    estado.productos.forEach((producto) => {
        selector.appendChild(
            crearOpcion(
                producto.id,
                `${producto.codigo} · ${producto.nombre}`
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


async function obtenerPresentaciones(productoId) {
    const clave = Number(productoId);

    if (!clave) {
        return null;
    }

    if (estado.presentaciones.has(clave)) {
        return estado.presentaciones.get(clave);
    }

    const datos = await solicitarJson(
        `${configuracion.apiProductos}/${clave}/presentaciones`
    );

    estado.presentaciones.set(clave, datos);

    return datos;
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
    const abreviatura =
        opcion?.dataset.abreviatura || "unidad";
    const equivalencia = linea.querySelector(
        ".linea-equivalencia"
    );

    linea.dataset.factorConversion = String(factor);

    if (!equivalencia) {
        return;
    }

    const cantidadBase = cantidad * factor;

    equivalencia.textContent =
        `${cantidad || 0} ${abreviatura} = ` +
        `${cantidadBase.toFixed(3)} unidades base`;
}

async function cargarPresentacionesLinea(
    linea,
    productoId,
    presentacionSeleccionada = null
) {
    const selector = linea.querySelector(
        ".linea-presentacion"
    );

    if (!selector) {
        return;
    }

    limpiar(selector);
    selector.disabled = true;

    if (!productoId) {
        selector.appendChild(
            crearOpcion("", "Selecciona un producto")
        );
        actualizarEquivalenciaLinea(linea);
        return;
    }

    try {
        const datos = await obtenerPresentaciones(
            productoId
        );
        const base = datos.unidad_base;

        const opcionBase = crearOpcion(
            "",
            `${base.nombre} (${base.abreviatura})`
        );
        opcionBase.dataset.factor =
            String(base.factor_base || "1");
        opcionBase.dataset.abreviatura =
            base.abreviatura || "unidad";
        selector.appendChild(opcionBase);

        (datos.presentaciones || []).forEach(
            (presentacion) => {
                const opcion = crearOpcion(
                    presentacion.id,
                    (
                        `${presentacion.nombre} ` +
                        `(${presentacion.abreviatura})`
                    )
                );
                opcion.dataset.factor = String(
                    presentacion.factor_base
                );
                opcion.dataset.abreviatura =
                    presentacion.abreviatura;
                selector.appendChild(opcion);
            }
        );

        selector.value = presentacionSeleccionada
            ? String(presentacionSeleccionada)
            : "";
        selector.disabled = false;
        actualizarEquivalenciaLinea(linea);
    } catch (error) {
        selector.appendChild(
            crearOpcion(
                "",
                "No fue posible cargar presentaciones"
            )
        );
        notificar(error.message);
    }
}

function agregarLineaCompra(datos = {}) {
    const contenedor = elemento("lineas-compra");

    if (!contenedor) {
        return;
    }

    const linea = crearElemento(
        "div",
        "",
        "linea-compra"
    );

    const selector = crearSelectorProductos();
    selector.value = String(
        datos.producto_id || ""
    );

    const presentacion =
        document.createElement("select");
    presentacion.className =
        "campo linea-presentacion";
    presentacion.appendChild(
        crearOpcion("", "Unidad base")
    );

    const cantidad = document.createElement("input");
    cantidad.className = "campo linea-cantidad";
    cantidad.type = "number";
    cantidad.min = "0.001";
    cantidad.step = "0.001";
    cantidad.value = String(
        datos.cantidad_presentacion ??
        datos.cantidad ??
        "1"
    );
    cantidad.required = true;

    const precio = document.createElement("input");
    precio.className = "campo linea-precio";
    precio.type = "number";
    precio.min = "0";
    precio.step = "0.0001";
    precio.value = String(
        datos.precio_presentacion ??
        datos.precio_unitario ??
        "0"
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

    selector.addEventListener(
        "change",
        async () => {
            const producto = estado.productos.find(
                (actual) =>
                    String(actual.id) ===
                    selector.value
            );

            await cargarPresentacionesLinea(
                linea,
                selector.value
            );

            if (producto) {
                precio.value = String(
                    producto.costo_referencia || "0"
                );
            }

            actualizarEquivalenciaLinea(linea);
        }
    );

    presentacion.addEventListener(
        "change",
        () => {
            const producto = estado.productos.find(
                (actual) =>
                    String(actual.id) ===
                    selector.value
            );
            const factorAnterior = Number(
                linea.dataset.factorConversion || 1
            );
            const factor = Number(
                presentacion.selectedOptions[0]
                    ?.dataset.factor || 1
            );
            const costoActual = Number(
                precio.value || 0
            );

            if (
                Number.isFinite(costoActual) &&
                factorAnterior > 0
            ) {
                precio.value = String(
                    (
                        costoActual
                        / factorAnterior
                        * factor
                    ).toFixed(4)
                );
            } else if (producto) {
                precio.value = String(
                    Number(
                        producto.costo_referencia || 0
                    ) * factor
                );
            }

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
            agregarLineaCompra();
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
            "Costo por presentación",
            precio
        )
    );
    linea.appendChild(quitar);
    linea.appendChild(equivalencia);
    linea.appendChild(descuento);
    linea.appendChild(impuesto);

    contenedor.appendChild(linea);

    if (datos.producto_id) {
        void cargarPresentacionesLinea(
            linea,
            datos.producto_id,
            datos.presentacion_id
        );
    } else {
        actualizarEquivalenciaLinea(linea);
    }
}

function restablecerFormulario() {
    elemento("formulario-compra")?.reset();
    elemento("compra-moneda").value = "CLP";

    const lineas = elemento("lineas-compra");
    limpiar(lineas);
    agregarLineaCompra();

    mostrarErrorFormulario("");
}

function abrirFormulario() {
    if (!configuracion.puedeCrear) {
        notificar("No tienes permiso para crear compras.");
        return;
    }
    estado.ordenEdicion = null;

    restablecerFormulario();
    elemento("titulo-modal-compra").textContent =
        "Nueva orden de compra";

    elemento("guardar-compra").textContent =
        "Crear borrador";
    elemento("modal-compra").hidden = false;
    elemento("compra-numero")?.focus();
}

function abrirFormularioEdicion(orden) {
    if (!configuracion.puedeEditar) {
        notificar(
            "No tienes permiso para editar compras."
        );
        return;
    }

    if (orden.estado !== "borrador") {
        notificar(
            "Solo se pueden editar órdenes en borrador."
        );
        return;
    }

    restablecerFormulario();
    estado.ordenEdicion = orden;

    elemento("titulo-modal-compra").textContent =
        `Editar orden ${orden.numero}`;

    elemento("guardar-compra").textContent =
        "Guardar cambios";

    elemento("compra-numero").value =
        orden.numero || "";

    elemento("compra-proveedor").value =
        String(orden.proveedor_id || "");

    elemento("compra-fecha-entrega").value =
        orden.fecha_entrega_esperada || "";

    elemento("compra-moneda").value =
        orden.moneda || "CLP";

    elemento("compra-observaciones").value =
        orden.observaciones || "";

    const lineas = elemento("lineas-compra");
    limpiar(lineas);

    orden.items.forEach((item) => {
        agregarLineaCompra({
            producto_id: item.producto_id,
            presentacion_id:
                item.presentacion_id,
            cantidad_presentacion:
                item.cantidad_presentacion,
            precio_presentacion:
                item.precio_presentacion,
            descuento: item.descuento,
            impuesto: item.impuesto,
        });
    });

    elemento("modal-compra").hidden = false;
    elemento("compra-numero")?.focus();
}

function cerrarFormulario() {
    elemento("modal-compra").hidden = true;
    mostrarErrorFormulario("");

    estado.ordenEdicion = null;
}

function construirDatosCompra() {
    const numero = elemento("compra-numero").value.trim();
    const proveedorId = Number(
        elemento("compra-proveedor").value
    );

    if (!numero) {
        throw new Error(
            "El número de orden es obligatorio."
        );
    }

    if (!proveedorId) {
        throw new Error(
            "Debes seleccionar un proveedor."
        );
    }

    const lineas = Array.from(
        elemento("lineas-compra").children
    );

    const items = lineas.map((linea) => {
        const productoId = Number(
            linea.querySelector(".linea-producto").value
        );
        const presentacionId = Number(
            linea.querySelector(
                ".linea-presentacion"
            )?.value || 0
        );
        const cantidad = Number(
            linea.querySelector(".linea-cantidad").value
        );
        const precioUnitario = Number(
            linea.querySelector(".linea-precio").value
        );

        const descuento = Number(
            linea.querySelector(
                ".linea-descuento"
            )?.value || 0
        );

        const impuesto = Number(
            linea.querySelector(
                ".linea-impuesto"
            )?.value || 0
        );

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

        if (
            !Number.isFinite(precioUnitario) ||
            precioUnitario < 0
        ) {
            throw new Error(
                "Los costos no pueden ser negativos."
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
            "No puedes repetir un producto en la orden."
        );
    }

    return {
        numero,
        proveedor_id: proveedorId,
        bodega_destino_id: configuracion.bodegaId,
        fecha_entrega_esperada:
            elemento("compra-fecha-entrega").value || null,
        moneda:
            elemento("compra-moneda").value || "CLP",
        observaciones:
            elemento("compra-observaciones").value.trim() ||
            null,
        items,
    };
}

async function guardarCompra(evento) {
    evento.preventDefault();

    if (!configuracion.puedeCrear) {
        mostrarErrorFormulario(
            "No tienes permiso para crear compras."
        );
        return;
    }

    const boton = elemento("guardar-compra");

    const ordenEdicion = estado.ordenEdicion;
    const editando = Boolean(ordenEdicion);

    try {
        mostrarErrorFormulario("");

        const datos = construirDatosCompra();

        boton.disabled = true;
                boton.textContent = editando
            ? "Guardando cambios…"
            : "Creando…";

        const url = editando
            ? `${configuracion.apiCompras}/${ordenEdicion.id}`
            : configuracion.apiCompras;

        await solicitarJson(url, {
            method: editando ? "PATCH" : "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": obtenerTokenCsrf(),
            },
            body: JSON.stringify(datos),
        });

        cerrarFormulario();
        await cargarCompras();
        notificar(
            editando
                ? "Orden actualizada correctamente."
                : "Orden de compra creada correctamente."
        );
    } catch (error) {
        mostrarErrorFormulario(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = editando
            ? "Guardar cambios"
            : "Crear borrador";
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
    orden,
    accion,
    mensajeConfirmacion,
    mensajeExito,
    cuerpo = null
) {
    if (
        mensajeConfirmacion &&
        !window.confirm(mensajeConfirmacion)
    ) {
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
            `${configuracion.apiCompras}/${orden.id}/${accion}`,
            opciones
        );

        await cargarCompras();
        notificar(mensajeExito);
    } catch (error) {
        notificar(error.message);
    }
}

function confirmarOrden(orden) {
    return ejecutarAccion(
        orden,
        "confirmar",
        `¿Deseas confirmar la orden "${orden.numero}"?`,
        "Orden confirmada correctamente."
    );
}

function enviarOrden(orden) {
    return ejecutarAccion(
        orden,
        "enviar",
        `¿Deseas marcar como enviada la orden "${orden.numero}"?`,
        "Orden enviada correctamente."
    );
}

function cancelarOrden(orden) {
    const motivo = window.prompt(
        `Indica el motivo de cancelación de "${orden.numero}":`
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
        orden,
        "cancelar",
        "¿Confirmas la cancelación de esta orden?",
        "Orden cancelada correctamente.",
        {
            motivo: motivo.trim(),
        }
    );
}

function agregarAcciones(acciones, orden) {
        if (
        orden.estado === "borrador" &&
        configuracion.puedeEditar
    ) {
        acciones.appendChild(
            crearBoton(
                "Editar",
                "boton boton--secundario boton--pequeno",
                () => abrirFormularioEdicion(orden)
            )
        );
    }
    if (
        orden.estado === "borrador" &&
        configuracion.puedeCrear
    ) {
        acciones.appendChild(
            crearBoton(
                "Confirmar",
                "boton boton--primario boton--pequeno",
                () => confirmarOrden(orden)
            )
        );
    }

    if (
        orden.estado === "creada" &&
        configuracion.puedeEnviar
    ) {
        acciones.appendChild(
            crearBoton(
                "Enviar",
                "boton boton--primario boton--pequeno",
                () => enviarOrden(orden)
            )
        );
    }

    if (
        ["enviada", "parcialmente_recibida"].includes(
            orden.estado
        ) &&
        configuracion.puedeRecibir
    ) {
        acciones.appendChild(
            crearBoton(
                "Recibir",
                "boton boton--primario boton--pequeno",
                () => abrirRecepcion(orden)
            )
        );
    }

    if (
        ["borrador", "creada", "enviada"].includes(
            orden.estado
        ) &&
        configuracion.puedeCancelar
    ) {
        acciones.appendChild(
            crearBoton(
                "Cancelar",
                "boton boton--peligro boton--pequeno",
                () => cancelarOrden(orden)
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

function ordenesFiltradas() {
    const busqueda = elemento("buscar-compras")
        .value
        .trim()
        .toLocaleLowerCase("es");

    if (!busqueda) {
        return estado.ordenes;
    }

    return estado.ordenes.filter((orden) => {
        return [
            orden.numero,
            orden.proveedor_nombre,
        ].some((valor) =>
            String(valor || "")
                .toLocaleLowerCase("es")
                .includes(busqueda)
        );
    });
}

function renderizarCompras() {
    const cuerpo = elemento("tabla-compras");

    if (!cuerpo) {
        return;
    }

    const ordenes = ordenesFiltradas();
    limpiar(cuerpo);

    elemento("cantidad-compras").textContent =
        `${ordenes.length} orden${
            ordenes.length === 1 ? "" : "es"
        }`;

    if (!ordenes.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No se encontraron órdenes de compra.",
            "tabla__vacio"
        );

        celda.colSpan = 7;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    ordenes.forEach((orden) => {
        const fila = crearElemento("tr");

        const numero = crearElemento("td");
        numero.appendChild(
            crearElemento(
                "span",
                orden.numero,
                "tabla__principal"
            )
        );
        numero.appendChild(
            crearElemento(
                "span",
                `${orden.items.length} producto${
                    orden.items.length === 1 ? "" : "s"
                }`,
                "tabla__detalle"
            )
        );
        fila.appendChild(numero);

        fila.appendChild(
            crearElemento(
                "td",
                orden.proveedor_nombre || "—"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(orden.fecha_orden)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(
                    orden.fecha_entrega_esperada
                )
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(
                    orden.total,
                    orden.moneda
                )
            )
        );

        const estadoCelda = crearElemento("td");
        estadoCelda.appendChild(
            crearElemento(
                "span",
                nombreEstado(orden.estado),
                `estado-compra estado-compra--${orden.estado}`
            )
        );
        fila.appendChild(estadoCelda);

        const acciones = crearElemento(
            "td",
            "",
            "acciones-fila"
        );
        agregarAcciones(acciones, orden);
        fila.appendChild(acciones);

        cuerpo.appendChild(fila);
    });
}

function mostrarCarga() {
    const cuerpo = elemento("tabla-compras");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando órdenes de compra…",
        "tabla__vacio"
    );

    celda.colSpan = 7;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

async function cargarCompras() {
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
            ? `${configuracion.apiCompras}?${consulta}`
            : configuracion.apiCompras;

        const datos = await solicitarJson(url);

        estado.ordenes = datos.ordenes || [];
        renderizarCompras();
    } catch (error) {
        estado.ordenes = [];
        renderizarCompras();
        notificar(error.message);
    }
}

async function cargarOpciones() {
    try {
        const [proveedores, productos] =
            await Promise.all([
                solicitarJson(configuracion.apiProveedores),
                solicitarJson(configuracion.apiProductos),
            ]);

        estado.proveedores =
            proveedores.proveedores || [];
        estado.productos =
            productos.productos || [];

        renderizarProveedores();
    } catch (error) {
        notificar(error.message);
    }
}

function mostrarErrorRecepcion(mensaje) {
    const error = elemento("error-recepcion");

    if (!error) {
        return;
    }

    error.textContent = mensaje || "";
    error.hidden = !mensaje;
}

function crearCampoRecepcion(
    etiquetaTexto,
    clase,
    tipo,
    valor,
    atributos = {}
) {
    const grupo = crearElemento("div");
    const etiqueta = crearElemento(
        "label",
        etiquetaTexto
    );
    const campo = document.createElement(
        tipo === "textarea" ? "textarea" : "input"
    );

    campo.className = `campo ${clase}`;

    if (tipo !== "textarea") {
        campo.type = tipo;
    }

    campo.value = valor ?? "";

    Object.entries(atributos).forEach(
        ([nombre, contenido]) => {
            campo.setAttribute(nombre, contenido);
        }
    );

    grupo.appendChild(etiqueta);
    grupo.appendChild(campo);

    return grupo;
}


function renderizarLineasRecepcion(orden) {
    const contenedor = elemento("lineas-recepcion");
    limpiar(contenedor);

    orden.items.forEach((item) => {
        const pendienteBase =
            Number(item.cantidad) -
            Number(item.cantidad_recibida);

        if (pendienteBase <= 0) {
            return;
        }

        const producto = estado.productos.find(
            (actual) =>
                Number(actual.id) ===
                Number(item.producto_id)
        );
        const factor = Number(
            item.factor_conversion || 1
        );
        const usaPresentacion = Boolean(
            item.presentacion_id
        );
        const pendienteMostrado = usaPresentacion
            ? pendienteBase / factor
            : pendienteBase;
        const unidad = usaPresentacion
            ? (
                item.presentacion_abreviatura ||
                item.presentacion_nombre ||
                "presentación"
            )
            : (
                producto?.unidad_medida ||
                "unidad base"
            );

        const linea = crearElemento(
            "div",
            "",
            "recepcion-linea"
        );

        linea.dataset.ordenItemId = String(item.id);
        linea.dataset.usaPresentacion =
            String(usaPresentacion);
        linea.dataset.factorConversion =
            String(factor);

        const resumen = crearElemento(
            "div",
            "",
            "recepcion-linea__producto"
        );

        resumen.appendChild(
            crearElemento(
                "strong",
                item.producto_nombre ||
                `Producto ${item.producto_id}`
            )
        );

        resumen.appendChild(
            crearElemento(
                "span",
                (
                    `${item.producto_codigo || "Sin código"} ? ` +
                    `Pendiente: ${pendienteMostrado.toFixed(3)} ` +
                    `${unidad} ? ${pendienteBase.toFixed(3)} base`
                )
            )
        );

        linea.appendChild(resumen);

        linea.appendChild(
            crearCampoRecepcion(
                usaPresentacion
                    ? "Cantidad de presentaciones"
                    : "Cantidad recibida",
                "recepcion-cantidad",
                "number",
                pendienteMostrado,
                {
                    min: "0",
                    max: String(pendienteMostrado),
                    step: "0.001",
                }
            )
        );

        linea.appendChild(
            crearCampoRecepcion(
                usaPresentacion
                    ? "Costo por presentación"
                    : "Costo unitario",
                "recepcion-costo",
                "number",
                usaPresentacion
                    ? item.precio_presentacion
                    : item.precio_unitario,
                {
                    min: "0",
                    step: "0.0001",
                }
            )
        );

        if (
            producto?.controla_lotes ||
            producto?.controla_vencimiento
        ) {
            linea.appendChild(
                crearCampoRecepcion(
                    "Número de lote",
                    "recepcion-lote",
                    "text",
                    "",
                    {
                        maxlength: "100",
                    }
                )
            );
        }

        if (producto?.controla_vencimiento) {
            linea.appendChild(
                crearCampoRecepcion(
                    "Fecha de vencimiento",
                    "recepcion-vencimiento",
                    "date",
                    ""
                )
            );
        }

        if (producto?.requiere_serial) {
            linea.appendChild(
                crearCampoRecepcion(
                    "Seriales, uno por línea",
                    "recepcion-seriales",
                    "textarea",
                    "",
                    {
                        rows: "3",
                    }
                )
            );
        }

        contenedor.appendChild(linea);
    });
}

function abrirRecepcion(orden) {
    if (!configuracion.puedeRecibir) {
        notificar(
            "No tienes permiso para recibir compras."
        );
        return;
    }

    estado.ordenRecepcion = orden;

    elemento("formulario-recepcion")?.reset();

    elemento("detalle-orden-recepcion").textContent =
        `${orden.numero} · ${orden.proveedor_nombre || "Proveedor"}`;

    renderizarLineasRecepcion(orden);
    mostrarErrorRecepcion("");

    elemento("modal-recepcion").hidden = false;
    elemento("recepcion-numero")?.focus();
}

function cerrarRecepcion() {
    elemento("modal-recepcion").hidden = true;
    estado.ordenRecepcion = null;
    mostrarErrorRecepcion("");
}


function construirDatosRecepcion() {
    const numero = elemento("recepcion-numero")
        .value
        .trim();

    if (!numero) {
        throw new Error(
            "El número de recepción es obligatorio."
        );
    }

    const lineas = Array.from(
        elemento("lineas-recepcion").children
    );
    const items = [];

    lineas.forEach((linea) => {
        const cantidad = Number(
            linea.querySelector(
                ".recepcion-cantidad"
            ).value
        );

        if (cantidad === 0) {
            return;
        }

        const costo = Number(
            linea.querySelector(
                ".recepcion-costo"
            ).value
        );

        if (
            !Number.isFinite(cantidad) ||
            cantidad < 0
        ) {
            throw new Error(
                "Las cantidades recibidas no son válidas."
            );
        }

        if (
            !Number.isFinite(costo) ||
            costo < 0
        ) {
            throw new Error(
                "Los costos recibidos no son válidos."
            );
        }

        const lote = linea.querySelector(
            ".recepcion-lote"
        );
        const vencimiento = linea.querySelector(
            ".recepcion-vencimiento"
        );
        const serialesCampo = linea.querySelector(
            ".recepcion-seriales"
        );
        const seriales = serialesCampo
            ? serialesCampo.value
                .split(/\r?\n|,/)
                .map((serial) => serial.trim())
                .filter(Boolean)
            : [];

        const item = {
            orden_item_id: Number(
                linea.dataset.ordenItemId
            ),
            numero_lote:
                lote?.value.trim() || null,
            fecha_vencimiento:
                vencimiento?.value || null,
            seriales,
        };

        if (
            linea.dataset.usaPresentacion === "true"
        ) {
            item.cantidad_presentacion = cantidad;
            item.costo_presentacion = costo;
        } else {
            item.cantidad = cantidad;
            item.costo_unitario = costo;
        }

        items.push(item);
    });

    if (!items.length) {
        throw new Error(
            "Debes recibir al menos un producto."
        );
    }

    return {
        numero,
        documento_referencia:
            elemento("recepcion-documento")
                .value
                .trim() || null,
        observaciones:
            elemento("recepcion-observaciones")
                .value
                .trim() || null,
        items,
    };
}

async function guardarRecepcion(evento) {
    evento.preventDefault();

    const orden = estado.ordenRecepcion;

    if (!orden) {
        mostrarErrorRecepcion(
            "No hay una orden seleccionada."
        );
        return;
    }

    const boton = elemento("guardar-recepcion");

    try {
        mostrarErrorRecepcion("");

        const datos = construirDatosRecepcion();

        boton.disabled = true;
        boton.textContent = "Recibiendo…";

        await solicitarJson(
            `${configuracion.apiCompras}/${orden.id}/recepciones`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
                body: JSON.stringify(datos),
            }
        );

        cerrarRecepcion();
        await cargarCompras();

        notificar(
            "Recepción registrada correctamente."
        );
    } catch (error) {
        mostrarErrorRecepcion(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = "Confirmar recepción";
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

function registrarEventos() {
    elemento("crear-compra")?.addEventListener(
        "click",
        abrirFormulario
    );

    elemento("cerrar-modal-compra")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("cancelar-compra")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("formulario-compra")?.addEventListener(
        "submit",
        guardarCompra
    );

        elemento("cerrar-modal-recepcion")?.addEventListener(
        "click",
        cerrarRecepcion
    );

    elemento("cancelar-recepcion")?.addEventListener(
        "click",
        cerrarRecepcion
    );

    elemento("formulario-recepcion")?.addEventListener(
        "submit",
        guardarRecepcion
    );

    elemento("agregar-linea-compra")?.addEventListener(
        "click",
        () => agregarLineaCompra()
    );

    elemento("actualizar-compras")?.addEventListener(
        "click",
        cargarCompras
    );

    elemento("filtrar-estado")?.addEventListener(
        "change",
        cargarCompras
    );

    elemento("ejecutar-busqueda")?.addEventListener(
        "click",
        renderizarCompras
    );

    elemento("buscar-compras")?.addEventListener(
        "input",
        renderizarCompras
    );

    elemento("buscar-compras")?.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                renderizarCompras();
            }
        }
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
        if (evento.key !== "Escape") {
            return;
        }

        if (!elemento("modal-recepcion")?.hidden) {
            cerrarRecepcion();
            return;
        }

        if (!elemento("modal-compra")?.hidden) {
            cerrarFormulario();
        }
    });
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();

        await cargarOpciones();
        await cargarCompras();
    }
);
