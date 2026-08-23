"use strict";

const estadoPresentaciones = {
    productoId: null,
    unidadBase: null,
    presentaciones: [],
};


function mostrarErrorPresentacion(mensaje) {
    const error = elemento(
        "error-presentacion-producto"
    );

    if (!error) {
        return;
    }

    error.textContent = mensaje || "";
    error.hidden = !mensaje;
}


function mostrarEstadoPresentaciones(mensaje) {
    const salida = elemento(
        "estado-presentaciones-producto"
    );

    if (!salida) {
        return;
    }

    salida.textContent = mensaje || "";
    salida.hidden = !mensaje;
}


function cerrarEditorPresentacion() {
    const editor = elemento(
        "formulario-presentacion-producto"
    );

    if (editor) {
        editor.hidden = true;
    }

    [
        "presentacion-id",
        "presentacion-codigo",
        "presentacion-nombre",
        "presentacion-abreviatura",
        "presentacion-factor",
    ].forEach(
        (id) => asignarValorCampo(id, "")
    );

    mostrarErrorPresentacion("");
}


function restablecerGestionPresentaciones() {
    estadoPresentaciones.productoId = null;
    estadoPresentaciones.unidadBase = null;
    estadoPresentaciones.presentaciones = [];

    const seccion = elemento(
        "seccion-presentaciones-producto"
    );

    if (seccion) {
        seccion.hidden = true;
    }

    limpiar(
        elemento("lista-presentaciones-producto")
    );
    cerrarEditorPresentacion();

    mostrarEstadoPresentaciones(
        "Guarda primero el producto para " +
        "administrar sus presentaciones."
    );
}


function actualizarEquivalenciaPresentacion() {
    const salida = elemento(
        "presentacion-equivalencia"
    );

    if (!salida) {
        return;
    }

    const nombre =
        valorCampo("presentacion-nombre") ||
        "presentación";
    const factor = valorCampo(
        "presentacion-factor"
    );
    const unidad =
        estadoPresentaciones.unidadBase?.nombre ||
        valorCampo("producto-unidad-medida") ||
        "unidad base";

    salida.textContent = factor
        ? `1 ${nombre} = ${factor} ${unidad}`
        : (
            "Indica cuántas unidades base " +
            "contiene esta presentación."
        );
}


function abrirEditorPresentacion(
    presentacion = null
) {
    if (!configuracion.puedeEditar) {
        notificar(
            "No tienes permiso para editar " +
            "presentaciones."
        );
        return;
    }

    const editor = elemento(
        "formulario-presentacion-producto"
    );

    if (!editor) {
        return;
    }

    asignarValorCampo(
        "presentacion-id",
        presentacion?.id || ""
    );
    asignarValorCampo(
        "presentacion-codigo",
        presentacion?.codigo || ""
    );
    asignarValorCampo(
        "presentacion-nombre",
        presentacion?.nombre || ""
    );
    asignarValorCampo(
        "presentacion-abreviatura",
        presentacion?.abreviatura || ""
    );
    asignarValorCampo(
        "presentacion-factor",
        presentacion?.factor_base || ""
    );

    elemento(
        "titulo-editor-presentacion"
    ).textContent = presentacion
        ? "Editar presentación"
        : "Nueva presentación";

    elemento(
        "guardar-presentacion-producto"
    ).textContent = presentacion
        ? "Guardar cambios"
        : "Guardar presentación";

    mostrarErrorPresentacion("");
    editor.hidden = false;
    actualizarEquivalenciaPresentacion();

    elemento("presentacion-codigo")?.focus();
}


function crearTarjetaPresentacion(
    presentacion,
    esBase = false
) {
    const tarjeta = crearElemento(
        "article",
        "",
        "presentacion-tarjeta"
    );
    const contenido = crearElemento(
        "div",
        "",
        "presentacion-tarjeta__contenido"
    );

    contenido.appendChild(
        crearElemento(
            "h4",
            presentacion.nombre
        )
    );

    const detalle = crearElemento("p");

    detalle.textContent = esBase
        ? (
            `${presentacion.abreviatura} ? ` +
            "Unidad utilizada para controlar stock"
        )
        : (
            `1 ${presentacion.abreviatura} = ` +
            `${presentacion.factor_base} ` +
            `${estadoPresentaciones.unidadBase.nombre}`
        );

    contenido.appendChild(detalle);
    tarjeta.appendChild(contenido);

    const lateral = crearElemento(
        "div",
        "",
        "presentacion-tarjeta__lateral"
    );

    lateral.appendChild(
        crearElemento(
            "span",
            esBase
                ? "Unidad base"
                : (
                    presentacion.codigo === "CAJA"
                        ? "Administrada por el producto"
                        : presentacion.codigo
                ),
            esBase
                ? (
                    "presentacion-etiqueta " +
                    "presentacion-etiqueta--base"
                )
                : "presentacion-etiqueta"
        )
    );

    if (
        !esBase &&
        presentacion.codigo !== "CAJA" &&
        configuracion.puedeEditar
    ) {
        const acciones = crearElemento(
            "div",
            "",
            "presentacion-tarjeta__acciones"
        );

        acciones.appendChild(
            crearBoton(
                "Editar",
                (
                    "boton boton--secundario " +
                    "boton--pequeno"
                ),
                () => abrirEditorPresentacion(
                    presentacion
                )
            )
        );

        acciones.appendChild(
            crearBoton(
                "Desactivar",
                (
                    "boton boton--peligro " +
                    "boton--pequeno"
                ),
                () => desactivarPresentacion(
                    presentacion
                )
            )
        );

        lateral.appendChild(acciones);
    }

    tarjeta.appendChild(lateral);

    return tarjeta;
}


function renderizarPresentaciones() {
    const lista = elemento(
        "lista-presentaciones-producto"
    );

    if (
        !lista ||
        !estadoPresentaciones.unidadBase
    ) {
        return;
    }

    limpiar(lista);

    lista.appendChild(
        crearTarjetaPresentacion(
            estadoPresentaciones.unidadBase,
            true
        )
    );

    estadoPresentaciones.presentaciones.forEach(
        (presentacion) => {
            lista.appendChild(
                crearTarjetaPresentacion(
                    presentacion
                )
            );
        }
    );

    mostrarEstadoPresentaciones(
        estadoPresentaciones.presentaciones.length
            ? ""
            : (
                "Este producto todavía no tiene " +
                "presentaciones adicionales."
            )
    );
}


async function cargarPresentaciones(productoId) {
    const seccion = elemento(
        "seccion-presentaciones-producto"
    );

    if (!seccion) {
        return;
    }

    seccion.hidden = false;
    estadoPresentaciones.productoId =
        Number(productoId);

    cerrarEditorPresentacion();
    mostrarEstadoPresentaciones(
        "Cargando presentaciones?"
    );

    try {
        const datos = await solicitarJson(
            `${configuracion.api}/${productoId}` +
            "/presentaciones"
        );

        estadoPresentaciones.unidadBase =
            datos.unidad_base;
        estadoPresentaciones.presentaciones =
            datos.presentaciones || [];

        renderizarPresentaciones();
    } catch (error) {
        estadoPresentaciones.unidadBase = null;
        estadoPresentaciones.presentaciones = [];

        mostrarEstadoPresentaciones(
            "No fue posible cargar las " +
            `presentaciones: ${error.message}`
        );
    }
}


async function guardarPresentacion() {
    const productoId =
        estadoPresentaciones.productoId;
    const presentacionId = valorCampo(
        "presentacion-id"
    );
    const codigo = valorCampo(
        "presentacion-codigo"
    );
    const nombre = valorCampo(
        "presentacion-nombre"
    );
    const abreviatura = valorCampo(
        "presentacion-abreviatura"
    );
    const factor = valorCampo(
        "presentacion-factor"
    );
    const boton = elemento(
        "guardar-presentacion-producto"
    );

    if (
        !productoId ||
        !codigo ||
        !nombre ||
        !abreviatura ||
        !factor
    ) {
        mostrarErrorPresentacion(
            "Completa código, nombre, " +
            "abreviatura y cantidad."
        );
        return;
    }

    const base =
        `${configuracion.api}/${productoId}` +
        "/presentaciones";
    const url = presentacionId
        ? `${base}/${presentacionId}`
        : base;

    try {
        mostrarErrorPresentacion("");
        boton.disabled = true;
        boton.textContent = "Guardando?";

        await solicitarJson(
            url,
            {
                method: presentacionId
                    ? "PATCH"
                    : "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
                body: JSON.stringify(
                    {
                        codigo,
                        nombre,
                        abreviatura,
                        factor_base: factor,
                    }
                ),
            }
        );

        cerrarEditorPresentacion();
        await cargarPresentaciones(
            productoId
        );

        notificar(
            presentacionId
                ? "Presentación actualizada."
                : "Presentación creada."
        );
    } catch (error) {
        mostrarErrorPresentacion(
            error.message
        );
    } finally {
        boton.disabled = false;
        boton.textContent = presentacionId
            ? "Guardar cambios"
            : "Guardar presentación";
    }
}


async function desactivarPresentacion(
    presentacion
) {
    const productoId =
        estadoPresentaciones.productoId;

    if (!productoId) {
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas desactivar "${presentacion.nombre}"?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${productoId}` +
            `/presentaciones/${presentacion.id}` +
            "/desactivar",
            {
                method: "POST",
                headers: {
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
            }
        );

        await cargarPresentaciones(
            productoId
        );
        notificar(
            "Presentación desactivada."
        );
    } catch (error) {
        notificar(error.message);
    }
}


const abrirFormularioEdicionOriginal =
    abrirFormularioEdicion;

abrirFormularioEdicion = function (producto) {
    abrirFormularioEdicionOriginal(producto);
    void cargarPresentaciones(producto.id);
};


const restablecerFormularioOriginal =
    restablecerFormulario;

restablecerFormulario = function () {
    restablecerGestionPresentaciones();
    restablecerFormularioOriginal();
};


const cerrarFormularioOriginal =
    cerrarFormulario;

cerrarFormulario = function () {
    restablecerGestionPresentaciones();
    cerrarFormularioOriginal();
};


document.addEventListener(
    "DOMContentLoaded",
    () => {
        elemento(
            "nueva-presentacion-producto"
        )?.addEventListener(
            "click",
            () => abrirEditorPresentacion()
        );

        elemento(
            "cancelar-presentacion-producto"
        )?.addEventListener(
            "click",
            cerrarEditorPresentacion
        );

        elemento(
            "guardar-presentacion-producto"
        )?.addEventListener(
            "click",
            guardarPresentacion
        );

        elemento(
            "presentacion-factor"
        )?.addEventListener(
            "input",
            actualizarEquivalenciaPresentacion
        );

        elemento(
            "presentacion-nombre"
        )?.addEventListener(
            "input",
            actualizarEquivalenciaPresentacion
        );
    }
);
