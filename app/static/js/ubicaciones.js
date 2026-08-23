"use strict";

const configuracion = Object.freeze({
    apiSucursales:
        document.body.dataset.apiSucursales,
    apiBodegas:
        document.body.dataset.apiBodegas,
    apiUsuarios:
        document.body.dataset.apiUsuarios,
    limiteSucursales:
        document.body.dataset.limiteSucursales,
    limiteBodegas:
        document.body.dataset.limiteBodegas,
    puedeCrearSucursal:
        document.body.dataset.puedeCrearSucursal
        === "true",
    puedeEditarSucursal:
        document.body.dataset.puedeEditarSucursal
        === "true",
    puedeDesactivarSucursal:
        document.body.dataset
            .puedeDesactivarSucursal
        === "true",
    puedeCrearBodega:
        document.body.dataset.puedeCrearBodega
        === "true",
    puedeEditarBodega:
        document.body.dataset.puedeEditarBodega
        === "true",
    puedeDesactivarBodega:
        document.body.dataset
            .puedeDesactivarBodega
        === "true",
    puedeAsignarUsuarios:
        document.body.dataset
            .puedeAsignarUsuarios
        === "true",
});

const estado = {
    sucursales: [],
    bodegas: [],
    usuarios: [],
    incluir_inactivas: false,
};

function elemento(id) {
    return document.getElementById(id);
}

function escapar(valor) {
    return String(valor ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function csrfToken() {
    return document.querySelector(
        'meta[name="csrf-token"]'
    )?.content || "";
}

async function solicitar(
    ruta,
    opciones = {},
) {
    const cabeceras = {
        Accept: "application/json",
        ...(opciones.headers || {}),
    };

    if (opciones.body !== undefined) {
        cabeceras["Content-Type"] =
            "application/json";
    }

    const token = csrfToken();

    if (token) {
        cabeceras["X-CSRFToken"] = token;
    }

    const respuesta = await fetch(
        ruta,
        {
            credentials: "same-origin",
            ...opciones,
            headers: cabeceras,
        },
    );

    if (respuesta.redirected) {
        window.location.assign(
            respuesta.url
        );
        throw new Error(
            "La sesi\u00f3n ya no est\u00e1 activa."
        );
    }

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
            || "No fue posible completar la operaci\u00f3n."
        );
    }

    return datos;
}

function notificar(
    mensaje,
    tipo = "exito",
) {
    const nodo = elemento("notificacion");

    nodo.textContent = mensaje;
    nodo.dataset.tipo = tipo;
    nodo.hidden = false;

    window.clearTimeout(
        notificar.temporizador
    );

    notificar.temporizador = (
        window.setTimeout(
            () => {
                nodo.hidden = true;
            },
            4200,
        )
    );
}

function numeroLimite(valor) {
    if (
        valor === ""
        || valor === undefined
        || valor === null
    ) {
        return null;
    }

    const numero = Number(valor);

    return Number.isFinite(numero)
        ? numero
        : null;
}

function sucursalPorId(id) {
    return estado.sucursales.find(
        (sucursal) => (
            sucursal.id === Number(id)
        ),
    );
}

function bodegaPorId(id) {
    return estado.bodegas.find(
        (bodega) => (
            bodega.id === Number(id)
        ),
    );
}

function bodegasDeSucursal(
    sucursalId,
) {
    return estado.bodegas.filter(
        (bodega) => (
            bodega.sucursal_id
            === Number(sucursalId)
        ),
    );
}

function usuarioAsignado(
    usuario,
    sucursalId,
) {
    return (
        usuario.sucursales || []
    ).some(
        (asignacion) => (
            asignacion.id
            === Number(sucursalId)
        ),
    );
}

function actualizarResumen() {
    elemento(
        "resumen-sucursales"
    ).textContent = estado.sucursales.filter(
        (sucursal) => sucursal.activa
    ).length;

    elemento(
        "resumen-bodegas"
    ).textContent = estado.bodegas.filter(
        (bodega) => bodega.activa
    ).length;
}

function etiquetaEstado(activa) {
    return activa
        ? (
            '<span class="ubicacion-etiqueta '
            + 'ubicacion-etiqueta--activa">'
            + "Activa</span>"
        )
        : (
            '<span class="ubicacion-etiqueta '
            + 'ubicacion-etiqueta--inactiva">'
            + "Inactiva</span>"
        );
}

function accionesBodega(bodega) {
    const acciones = [];

    if (
        configuracion.puedeEditarBodega
        && bodega.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--secundario boton--pequeno"
                type="button"
                data-accion="editar-bodega"
                data-bodega-id="${bodega.id}"
            >Editar</button>`
        );
    }

    if (
        configuracion.puedeDesactivarBodega
        && bodega.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--peligro boton--pequeno"
                type="button"
                data-accion="desactivar-bodega"
                data-bodega-id="${bodega.id}"
            >Desactivar</button>`
        );
    }

    if (
        configuracion.puedeEditarBodega
        && !bodega.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--secundario boton--pequeno"
                type="button"
                data-accion="reactivar-bodega"
                data-bodega-id="${bodega.id}"
            >Reactivar</button>`
        );
    }

    return acciones.join("");
}

function tarjetaBodega(bodega) {
    return `
        <article class="${
            bodega.activa
                ? "bodega-tarjeta"
                : (
                    "bodega-tarjeta "
                    + "bodega-tarjeta--inactiva"
                )
        }">
            <div>
                <div class="bodega-tarjeta__titulo">
                    <h4>${escapar(bodega.nombre)}</h4>
                    ${etiquetaEstado(bodega.activa)}
                </div>
                <p>
                    ${escapar(bodega.codigo)}
                    ${
                        bodega.descripcion
                            ? (
                                " \u00b7 "
                                + escapar(
                                    bodega.descripcion
                                )
                            )
                            : ""
                    }
                </p>
            </div>
            <div class="bodega-tarjeta__acciones">
                ${accionesBodega(bodega)}
            </div>
        </article>
    `;
}

function accionesSucursal(sucursal) {
    const acciones = [];

    if (
        configuracion.puedeCrearBodega
        && sucursal.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--primario boton--pequeno"
                type="button"
                data-accion="nueva-bodega"
                data-sucursal-id="${sucursal.id}"
            >Nueva bodega</button>`
        );
    }

    if (
        configuracion.puedeAsignarUsuarios
        && sucursal.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--secundario boton--pequeno"
                type="button"
                data-accion="usuarios-sucursal"
                data-sucursal-id="${sucursal.id}"
            >Usuarios</button>`
        );
    }

    if (
        configuracion.puedeEditarSucursal
        && sucursal.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--secundario boton--pequeno"
                type="button"
                data-accion="editar-sucursal"
                data-sucursal-id="${sucursal.id}"
            >Editar</button>`
        );
    }

    if (
        configuracion.puedeDesactivarSucursal
        && sucursal.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--peligro boton--pequeno"
                type="button"
                data-accion="desactivar-sucursal"
                data-sucursal-id="${sucursal.id}"
            >Desactivar</button>`
        );
    }

    if (
        configuracion.puedeEditarSucursal
        && !sucursal.activa
    ) {
        acciones.push(
            `<button
                class="boton boton--secundario boton--pequeno"
                type="button"
                data-accion="reactivar-sucursal"
                data-sucursal-id="${sucursal.id}"
            >Reactivar</button>`
        );
    }

    return acciones.join("");
}

function tarjetaSucursal(sucursal) {
    const bodegas = bodegasDeSucursal(
        sucursal.id
    );

    const ubicacion = [
        sucursal.direccion,
        sucursal.ciudad,
    ].filter(Boolean).join(", ");

    return `
        <article class="${
            sucursal.activa
                ? "sucursal-tarjeta"
                : (
                    "sucursal-tarjeta "
                    + "sucursal-tarjeta--inactiva"
                )
        }">
            <header class="sucursal-tarjeta__encabezado">
                <div>
                    <div class="sucursal-tarjeta__titulo">
                        <h3>
                            ${escapar(sucursal.nombre)}
                        </h3>
                        ${etiquetaEstado(sucursal.activa)}
                    </div>
                    <p>
                        ${escapar(sucursal.codigo)}
                        ${
                            ubicacion
                                ? (
                                    " \u00b7 "
                                    + escapar(ubicacion)
                                )
                                : ""
                        }
                        ${
                            sucursal.telefono
                                ? (
                                    " \u00b7 "
                                    + escapar(
                                        sucursal.telefono
                                    )
                                )
                                : ""
                        }
                    </p>
                </div>

                <div class="sucursal-tarjeta__acciones">
                    ${accionesSucursal(sucursal)}
                </div>
            </header>

            <div class="sucursal-tarjeta__bodegas">
                ${
                    bodegas.length
                        ? bodegas.map(
                            tarjetaBodega
                        ).join("")
                        : (
                            '<div class="ubicaciones-vacio">'
                            + "Esta sucursal no tiene bodegas."
                            + "</div>"
                        )
                }
            </div>
        </article>
    `;
}

function renderizar() {
    actualizarResumen();

    const lista = elemento(
        "lista-sucursales"
    );
    const estadoNodo = elemento(
        "estado-ubicaciones"
    );

    if (!estado.sucursales.length) {
        estadoNodo.textContent = (
            estado.incluir_inactivas
                ? "No existen sucursales registradas."
                : "No existen sucursales activas."
        );
        lista.innerHTML = "";
        return;
    }

    estadoNodo.textContent = (
        `${estado.sucursales.length} `
        + (
            estado.sucursales.length === 1
                ? "sucursal encontrada"
                : "sucursales encontradas"
        )
    );

    lista.innerHTML = estado.sucursales
        .map(tarjetaSucursal)
        .join("");
}

async function cargarUbicaciones() {
    const parametro = (
        estado.incluir_inactivas
            ? "true"
            : "false"
    );

    elemento(
        "estado-ubicaciones"
    ).textContent = "Cargando ubicaciones...";

    const [
        respuestaSucursales,
        respuestaBodegas,
    ] = await Promise.all(
        [
            solicitar(
                `${configuracion.apiSucursales}`
                + "?incluir_inactivas="
                + parametro
            ),
            solicitar(
                `${configuracion.apiBodegas}`
                + "?incluir_inactivas="
                + parametro
            ),
        ]
    );

    estado.sucursales = (
        respuestaSucursales.sucursales
        || []
    );
    estado.bodegas = (
        respuestaBodegas.bodegas
        || []
    );

    renderizar();
}

async function cargarUsuarios() {
    if (estado.usuarios.length) {
        return;
    }

    const respuesta = await solicitar(
        `${configuracion.apiUsuarios}`
        + "?incluir_inactivos=false"
    );

    estado.usuarios = (
        respuesta.usuarios || []
    );
}

function abrirModal(id) {
    elemento(id).hidden = false;
    document.body.classList.add(
        "modal-abierto"
    );
}

function cerrarModal(id) {
    elemento(id).hidden = true;

    if (
        !document.querySelector(
            ".modal:not([hidden])"
        )
    ) {
        document.body.classList.remove(
            "modal-abierto"
        );
    }
}

function abrirSucursal(sucursal = null) {
    const editando = Boolean(sucursal);

    elemento(
        "titulo-modal-sucursal"
    ).textContent = editando
        ? "Editar sucursal"
        : "Nueva sucursal";

    elemento("sucursal-id").value = (
        sucursal?.id || ""
    );
    elemento("sucursal-codigo").value = (
        sucursal?.codigo || ""
    );
    elemento("sucursal-nombre").value = (
        sucursal?.nombre || ""
    );
    elemento("sucursal-direccion").value = (
        sucursal?.direccion || ""
    );
    elemento("sucursal-ciudad").value = (
        sucursal?.ciudad || ""
    );
    elemento("sucursal-telefono").value = (
        sucursal?.telefono || ""
    );

    const crearBodega = elemento(
        "sucursal-crear-bodega"
    );

    crearBodega.checked = !editando;
    crearBodega.disabled = editando;

    abrirModal("modal-sucursal");
    elemento("sucursal-codigo").focus();
}

function abrirBodega(
    sucursalId,
    bodega = null,
) {
    const editando = Boolean(bodega);

    elemento(
        "titulo-modal-bodega"
    ).textContent = editando
        ? "Editar bodega"
        : "Nueva bodega";

    elemento("bodega-id").value = (
        bodega?.id || ""
    );
    elemento(
        "bodega-sucursal-id"
    ).value = (
        sucursalId
        || bodega?.sucursal_id
        || ""
    );
    elemento("bodega-codigo").value = (
        bodega?.codigo || ""
    );
    elemento("bodega-nombre").value = (
        bodega?.nombre || ""
    );
    elemento(
        "bodega-descripcion"
    ).value = (
        bodega?.descripcion || ""
    );

    abrirModal("modal-bodega");
    elemento("bodega-codigo").focus();
}

async function guardarSucursal(evento) {
    evento.preventDefault();

    const id = elemento(
        "sucursal-id"
    ).value;

    const datos = {
        codigo:
            elemento("sucursal-codigo")
                .value.trim(),
        nombre:
            elemento("sucursal-nombre")
                .value.trim(),
        direccion:
            elemento("sucursal-direccion")
                .value.trim() || null,
        ciudad:
            elemento("sucursal-ciudad")
                .value.trim() || null,
        telefono:
            elemento("sucursal-telefono")
                .value.trim() || null,
    };

    if (!id) {
        datos.crear_bodega_principal = (
            elemento(
                "sucursal-crear-bodega"
            ).checked
        );
    }

    const boton = elemento(
        "guardar-sucursal"
    );
    boton.disabled = true;

    try {
        await solicitar(
            id
                ? (
                    `${configuracion.apiSucursales}`
                    + `/${id}`
                )
                : configuracion.apiSucursales,
            {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(datos),
            },
        );

        cerrarModal("modal-sucursal");
        await cargarUbicaciones();

        notificar(
            id
                ? "Sucursal actualizada correctamente."
                : "Sucursal creada correctamente."
        );
    }
    catch (error) {
        notificar(error.message, "error");
    }
    finally {
        boton.disabled = false;
    }
}

async function guardarBodega(evento) {
    evento.preventDefault();

    const id = elemento("bodega-id").value;
    const sucursalId = elemento(
        "bodega-sucursal-id"
    ).value;

    const datos = {
        codigo:
            elemento("bodega-codigo")
                .value.trim(),
        nombre:
            elemento("bodega-nombre")
                .value.trim(),
        descripcion:
            elemento("bodega-descripcion")
                .value.trim() || null,
    };

    if (!id) {
        datos.sucursal_id = Number(
            sucursalId
        );
    }

    const boton = elemento(
        "guardar-bodega"
    );
    boton.disabled = true;

    try {
        await solicitar(
            id
                ? (
                    `${configuracion.apiBodegas}`
                    + `/${id}`
                )
                : configuracion.apiBodegas,
            {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(datos),
            },
        );

        cerrarModal("modal-bodega");
        await cargarUbicaciones();

        notificar(
            id
                ? "Bodega actualizada correctamente."
                : "Bodega creada correctamente."
        );
    }
    catch (error) {
        notificar(error.message, "error");
    }
    finally {
        boton.disabled = false;
    }
}

async function cambiarEstado(
    tipo,
    id,
    reactivar,
) {
    const api = tipo === "sucursal"
        ? configuracion.apiSucursales
        : configuracion.apiBodegas;

    const entidad = tipo === "sucursal"
        ? "sucursal"
        : "bodega";

    if (
        !reactivar
        && !window.confirm(
            `\u00bfDesactivar esta ${entidad}?`
        )
    ) {
        return;
    }

    try {
        await solicitar(
            `${api}/${id}${
                reactivar
                    ? "/reactivar"
                    : ""
            }`,
            {
                method: reactivar
                    ? "POST"
                    : "DELETE",
            },
        );

        await cargarUbicaciones();

        notificar(
            reactivar
                ? (
                    `${entidad[0].toUpperCase()}`
                    + entidad.slice(1)
                    + " reactivada correctamente."
                )
                : (
                    `${entidad[0].toUpperCase()}`
                    + entidad.slice(1)
                    + " desactivada correctamente."
                )
        );
    }
    catch (error) {
        notificar(error.message, "error");
    }
}

function filaUsuario(
    usuario,
    sucursalId,
) {
    const asignado = usuarioAsignado(
        usuario,
        sucursalId
    );

    return `
        <label class="usuario-sucursal">
            <input
                type="checkbox"
                data-usuario-sucursal
                data-usuario-id="${usuario.id}"
                ${
                    asignado
                        ? "checked"
                        : ""
                }
            >
            <span>
                <strong>
                    ${escapar(usuario.nombre)}
                    ${escapar(usuario.apellido || "")}
                </strong>
                <small>
                    ${escapar(usuario.email)}
                    \u00b7
                    ${escapar(
                        usuario.rol.replaceAll(
                            "_",
                            " "
                        )
                    )}
                </small>
            </span>
        </label>
    `;
}

async function abrirUsuarios(sucursal) {
    await cargarUsuarios();

    elemento(
        "usuarios-sucursal-id"
    ).value = sucursal.id;

    elemento(
        "contexto-usuarios-sucursal"
    ).textContent = (
        `Gestiona los accesos a ${sucursal.nombre}.`
    );

    elemento(
        "lista-usuarios-sucursal"
    ).innerHTML = estado.usuarios.length
        ? estado.usuarios.map(
            (usuario) => filaUsuario(
                usuario,
                sucursal.id,
            )
        ).join("")
        : (
            '<div class="ubicaciones-vacio">'
            + "No existen usuarios activos."
            + "</div>"
        );

    abrirModal(
        "modal-usuarios-sucursal"
    );
}

async function cambiarAsignacion(
    control,
) {
    const sucursalId = Number(
        elemento(
            "usuarios-sucursal-id"
        ).value
    );
    const usuarioId = Number(
        control.dataset.usuarioId
    );
    const asignar = control.checked;

    control.disabled = true;

    try {
        await solicitar(
            `${configuracion.apiSucursales}`
            + `/${sucursalId}/usuarios/`
            + `${usuarioId}`,
            {
                method: asignar
                    ? "POST"
                    : "DELETE",
                body: asignar
                    ? JSON.stringify({
                        es_principal: false,
                    })
                    : undefined,
            },
        );

        const usuario = estado.usuarios.find(
            (item) => item.id === usuarioId
        );

        if (usuario) {
            usuario.sucursales = (
                usuario.sucursales || []
            ).filter(
                (item) => (
                    item.id !== sucursalId
                ),
            );

            if (asignar) {
                usuario.sucursales.push({
                    id: sucursalId,
                    es_principal: false,
                });
            }
        }

        notificar(
            asignar
                ? "Usuario asignado correctamente."
                : "Usuario desasignado correctamente."
        );
    }
    catch (error) {
        control.checked = !asignar;
        notificar(error.message, "error");
    }
    finally {
        control.disabled = false;
    }
}

function validarLimite(
    tipo,
) {
    const limite = numeroLimite(
        tipo === "sucursal"
            ? configuracion.limiteSucursales
            : configuracion.limiteBodegas
    );

    if (limite === null) {
        return true;
    }

    const cantidad = tipo === "sucursal"
        ? estado.sucursales.length
        : estado.bodegas.length;

    if (cantidad < limite) {
        return true;
    }

    notificar(
        `Se alcanz\u00f3 el l\u00edmite de ${tipo}s del plan.`,
        "error",
    );

    return false;
}

async function manejarAccion(evento) {
    const boton = evento.target.closest(
        "[data-accion]"
    );

    if (!boton) {
        return;
    }

    const accion = boton.dataset.accion;
    const sucursalId = Number(
        boton.dataset.sucursalId
    );
    const bodegaId = Number(
        boton.dataset.bodegaId
    );

    if (accion === "editar-sucursal") {
        abrirSucursal(
            sucursalPorId(sucursalId)
        );
    }
    else if (accion === "nueva-bodega") {
        if (validarLimite("bodega")) {
            abrirBodega(sucursalId);
        }
    }
    else if (accion === "editar-bodega") {
        abrirBodega(
            null,
            bodegaPorId(bodegaId),
        );
    }
    else if (
        accion === "desactivar-sucursal"
    ) {
        await cambiarEstado(
            "sucursal",
            sucursalId,
            false,
        );
    }
    else if (
        accion === "reactivar-sucursal"
    ) {
        await cambiarEstado(
            "sucursal",
            sucursalId,
            true,
        );
    }
    else if (
        accion === "desactivar-bodega"
    ) {
        await cambiarEstado(
            "bodega",
            bodegaId,
            false,
        );
    }
    else if (
        accion === "reactivar-bodega"
    ) {
        await cambiarEstado(
            "bodega",
            bodegaId,
            true,
        );
    }
    else if (
        accion === "usuarios-sucursal"
    ) {
        await abrirUsuarios(
            sucursalPorId(sucursalId)
        );
    }
}

function abrirMenu() {
    document.body.classList.add(
        "menu-abierto"
    );
    elemento(
        "abrir-menu"
    ).setAttribute(
        "aria-expanded",
        "true",
    );
}

function cerrarMenu() {
    document.body.classList.remove(
        "menu-abierto"
    );
    elemento(
        "abrir-menu"
    ).setAttribute(
        "aria-expanded",
        "false",
    );
}

function registrarEventos() {
    elemento(
        "actualizar-ubicaciones"
    ).addEventListener(
        "click",
        async () => {
            try {
                await cargarUbicaciones();
                notificar(
                    "Ubicaciones actualizadas."
                );
            }
            catch (error) {
                notificar(
                    error.message,
                    "error",
                );
            }
        },
    );

    elemento(
        "nueva-sucursal"
    )?.addEventListener(
        "click",
        () => {
            if (
                validarLimite("sucursal")
            ) {
                abrirSucursal();
            }
        },
    );

    elemento(
        "formulario-sucursal"
    ).addEventListener(
        "submit",
        guardarSucursal,
    );

    elemento(
        "formulario-bodega"
    ).addEventListener(
        "submit",
        guardarBodega,
    );

    elemento(
        "cancelar-sucursal"
    ).addEventListener(
        "click",
        () => cerrarModal(
            "modal-sucursal"
        ),
    );

    elemento(
        "cancelar-bodega"
    ).addEventListener(
        "click",
        () => cerrarModal(
            "modal-bodega"
        ),
    );

    document.querySelectorAll(
        "[data-cerrar-sucursal]"
    ).forEach(
        (boton) => boton.addEventListener(
            "click",
            () => cerrarModal(
                "modal-sucursal"
            ),
        )
    );

    document.querySelectorAll(
        "[data-cerrar-bodega]"
    ).forEach(
        (boton) => boton.addEventListener(
            "click",
            () => cerrarModal(
                "modal-bodega"
            ),
        )
    );

    document.querySelectorAll(
        "[data-cerrar-usuarios]"
    ).forEach(
        (boton) => boton.addEventListener(
            "click",
            () => cerrarModal(
                "modal-usuarios-sucursal"
            ),
        )
    );

    elemento(
        "filtro-estado-ubicaciones"
    ).addEventListener(
        "change",
        async (evento) => {
            estado.incluir_inactivas = (
                evento.target.value
                === "todas"
            );

            try {
                await cargarUbicaciones();
            }
            catch (error) {
                notificar(
                    error.message,
                    "error",
                );
            }
        },
    );

    elemento(
        "lista-sucursales"
    ).addEventListener(
        "click",
        manejarAccion,
    );

    elemento(
        "lista-usuarios-sucursal"
    ).addEventListener(
        "change",
        async (evento) => {
            if (
                evento.target.matches(
                    "[data-usuario-sucursal]"
                )
            ) {
                await cambiarAsignacion(
                    evento.target
                );
            }
        },
    );

    elemento(
        "abrir-menu"
    ).addEventListener(
        "click",
        abrirMenu,
    );

    elemento(
        "cerrar-menu"
    ).addEventListener(
        "click",
        cerrarMenu,
    );

    document.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Escape") {
                document.querySelectorAll(
                    ".modal:not([hidden])"
                ).forEach(
                    (modal) => cerrarModal(
                        modal.id
                    )
                );
                cerrarMenu();
            }
        },
    );
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();

        try {
            await cargarUbicaciones();
        }
        catch (error) {
            elemento(
                "estado-ubicaciones"
            ).textContent = error.message;
            notificar(
                error.message,
                "error",
            );
        }
    },
);
