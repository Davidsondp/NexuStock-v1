"use strict";

const configuracion = Object.freeze({
    apiUsuarios:
        document.body.dataset.apiUsuarios,
    apiSucursales:
        document.body.dataset.apiSucursales,
    usuarioActualId: Number(
        document.body.dataset.usuarioActualId
    ),
    limiteUsuarios: (
        document.body.dataset.limiteUsuarios
            ? Number(
                document.body.dataset.limiteUsuarios
            )
            : null
    ),
    permisoCrear:
        document.body.dataset.permisoCrear
        === "true",
    permisoEditar:
        document.body.dataset.permisoEditar
        === "true",
    permisoDesactivar:
        document.body.dataset.permisoDesactivar
        === "true",
    permisoRoles:
        document.body.dataset.permisoRoles
        === "true",
});

const rutasAccion = Object.freeze({
    cambiarPassword: "/cambiar-password",
    desactivar: "/desactivar",
    reactivar: "/reactivar",
    revocarSesiones: "/revocar-sesiones",
});

const estado = {
    usuarios: [],
    sucursales: [],
};

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

async function solicitarJson(
    url,
    opciones = {},
) {
    const encabezados = {
        ...(opciones.headers || {}),
    };

    if (
        opciones.method
        && opciones.method !== "GET"
    ) {
        encabezados["Content-Type"] = (
            "application/json"
        );
        encabezados["X-CSRFToken"] = (
            obtenerTokenCsrf()
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
                "No fue posible completar "
                + "la operación."
            ),
        );
    }

    return datos;
}

function normalizarSucursales(datos) {
    if (Array.isArray(datos)) {
        return datos;
    }

    if (Array.isArray(datos.sucursales)) {
        return datos.sucursales;
    }

    return [];
}

function nombreRol(rol) {
    const nombres = {
        jefe: "Jefe/a",
        supervisor: "Supervisor/a",
        empleado: "Empleado/a",
    };

    return nombres[rol] || rol;
}

function nombreSucursal(id) {
    return (
        estado.sucursales.find(
            (sucursal) => (
                Number(sucursal.id)
                === Number(id)
            )
        )?.nombre
        || `Sucursal ${id}`
    );
}

function actualizarResumen() {
    const activos = estado.usuarios.filter(
        (usuario) => usuario.activo
    );

    const jefaturas = activos.filter(
        (usuario) => (
            usuario.rol === "jefe"
        )
    );

    elemento(
        "resumen-usuarios-activos"
    ).textContent = String(activos.length);

    elemento(
        "resumen-jefaturas"
    ).textContent = String(
        jefaturas.length
    );

    elemento(
        "resumen-limite-usuarios"
    ).textContent = (
        configuracion.limiteUsuarios === null
            ? "Sin límite"
            : String(configuracion.limiteUsuarios)
    );
}

function crearEtiqueta(
    texto,
    modificador = "",
) {
    return crearElemento(
        "span",
        (
            "usuario-etiqueta"
            + (
                modificador
                    ? ` usuario-etiqueta--${modificador}`
                    : ""
            )
        ),
        texto,
    );
}

function crearBoton(
    texto,
    clase,
    accion,
) {
    const boton = crearElemento(
        "button",
        clase,
        texto,
    );

    boton.type = "button";
    boton.addEventListener(
        "click",
        accion,
    );

    return boton;
}

function crearTarjeta(usuario) {
    const tarjeta = crearElemento(
        "article",
        "usuario-tarjeta",
    );

    if (!usuario.activo) {
        tarjeta.classList.add(
            "usuario-tarjeta--inactivo"
        );
    }

    const identidad = crearElemento(
        "div",
        "usuario-tarjeta__identidad",
    );

    identidad.append(
        crearElemento(
            "div",
            "usuario-tarjeta__avatar",
            (
                String(usuario.nombre || "U")
                    .slice(0, 1)
                    .toUpperCase()
            ),
        ),
    );

    const informacion = crearElemento("div");

    const nombre = [
        usuario.nombre,
        usuario.apellido,
    ].filter(Boolean).join(" ");

    informacion.append(
        crearElemento(
            "h4",
            "",
            nombre || "Usuario",
        ),
        crearElemento(
            "p",
            "",
            usuario.email,
        ),
        crearElemento(
            "p",
            "",
            [usuario.identificacion_fiscal || "RUT no informado", usuario.telefono || "Teléfono no informado"].join(" · "),
        ),
    );

    const etiquetas = crearElemento(
        "div",
        "usuario-tarjeta__etiquetas",
    );

    etiquetas.append(
        crearEtiqueta(
            nombreRol(usuario.rol),
            usuario.rol,
        ),
        crearEtiqueta(
            usuario.activo
                ? "Activo"
                : "Inactivo",
            usuario.activo
                ? "activo"
                : "inactivo",
        ),
    );

    if (
        Number(usuario.id)
        === configuracion.usuarioActualId
    ) {
        etiquetas.append(
            crearEtiqueta(
                "Tu cuenta",
                "actual",
            ),
        );
    }

    informacion.append(etiquetas);
    identidad.append(informacion);

    const sucursales = crearElemento(
        "div",
        "usuario-tarjeta__sucursales",
    );

    sucursales.append(
        crearElemento(
            "span",
            "",
            "Sucursales asignadas",
        ),
    );

    const asignaciones = (
        usuario.sucursales || []
    );

    sucursales.append(
        crearElemento(
            "strong",
            "",
            asignaciones.length
                ? asignaciones.map(
                    (asignacion) => (
                        nombreSucursal(
                            asignacion.id
                        )
                        + (
                            asignacion.es_principal
                                ? " (principal)"
                                : ""
                        )
                    )
                ).join(", ")
                : "Sin sucursales",
        ),
    );

    const permisosCantidad = Object.keys(
        usuario.permisos_especiales || {}
    ).length;

    const permisos = crearElemento(
        "div",
        "usuario-tarjeta__permisos",
        (
            permisosCantidad
                ? (
                    `${permisosCantidad} permiso`
                    + (
                        permisosCantidad === 1
                            ? " especial"
                            : "s especiales"
                    )
                )
                : "Sin permisos especiales"
        ),
    );

    const acciones = crearElemento(
        "div",
        "usuario-tarjeta__acciones",
    );

    if (configuracion.permisoEditar) {
        acciones.append(
            crearBoton(
                "Editar",
                (
                    "boton boton--secundario "
                    + "boton--pequeno"
                ),
                () => abrirEditor(usuario),
            ),
            crearBoton(
                "Cambiar contraseña",
                (
                    "boton boton--secundario "
                    + "boton--pequeno"
                ),
                () => cambiarPassword(usuario),
            ),
            crearBoton(
                "Revocar sesiones",
                (
                    "boton boton--secundario "
                    + "boton--pequeno"
                ),
                () => ejecutarAccion(
                    usuario,
                    "revocarSesiones",
                ),
            ),
        );
    }

    if (
        usuario.activo
        && configuracion.permisoDesactivar
        && Number(usuario.id)
            !== configuracion.usuarioActualId
    ) {
        acciones.append(
            crearBoton(
                "Desactivar",
                (
                    "boton boton--peligro "
                    + "boton--pequeno"
                ),
                () => ejecutarAccion(
                    usuario,
                    "desactivar",
                ),
            ),
        );
    }

    if (
        !usuario.activo
        && configuracion.permisoEditar
    ) {
        acciones.append(
            crearBoton(
                "Reactivar",
                (
                    "boton boton--primario "
                    + "boton--pequeno"
                ),
                () => ejecutarAccion(
                    usuario,
                    "reactivar",
                ),
            ),
        );
    }

    tarjeta.append(
        identidad,
        sucursales,
        permisos,
        acciones,
    );

    return tarjeta;
}

function renderizarUsuarios() {
    const lista = elemento(
        "lista-usuarios"
    );
    const mensaje = elemento(
        "estado-lista-usuarios"
    );

    limpiar(lista);

    if (!estado.usuarios.length) {
        mensaje.textContent = (
            "No hay usuarios para "
            + "el filtro seleccionado."
        );
        mensaje.hidden = false;
        actualizarResumen();
        return;
    }

    for (const usuario of estado.usuarios) {
        lista.append(
            crearTarjeta(usuario)
        );
    }

    mensaje.hidden = true;
    actualizarResumen();
}

async function cargarUsuarios() {
    const incluirInactivos = (
        elemento(
            "filtro-estado-usuarios"
        ).value === "todos"
    );

    const parametros = new URLSearchParams({
        incluir_inactivos: String(
            incluirInactivos
        ),
    });

    const datos = await solicitarJson(
        (
            `${configuracion.apiUsuarios}`
            + `?${parametros}`
        ),
    );

    estado.usuarios = Array.isArray(
        datos.usuarios
    )
        ? datos.usuarios
        : [];

    renderizarUsuarios();
}

function renderizarSucursales(
    seleccionadas = [],
) {
    const contenedor = elemento(
        "usuario-sucursales"
    );

    limpiar(contenedor);

    const ids = new Set(
        seleccionadas.map(
            (valor) => Number(valor)
        )
    );

    if (!estado.sucursales.length) {
        contenedor.append(
            crearElemento(
                "p",
                "usuario-opciones__vacio",
                "No existen sucursales activas.",
            ),
        );
        return;
    }

    for (const sucursal of estado.sucursales) {
        const etiqueta = crearElemento(
            "label",
            "usuario-opcion",
        );

        const entrada = document.createElement(
            "input"
        );

        entrada.type = "checkbox";
        entrada.value = String(sucursal.id);
        entrada.checked = ids.has(
            Number(sucursal.id)
        );

        etiqueta.append(
            entrada,
            crearElemento(
                "span",
                "",
                sucursal.nombre,
            ),
        );

        contenedor.append(etiqueta);
    }
}

async function cargarSucursales() {
    const datos = await solicitarJson(
        configuracion.apiSucursales
    );

    estado.sucursales = normalizarSucursales(
        datos
    );

    renderizarSucursales();
}

function limpiarPermisos() {
    for (
        const selector
        of elemento(
            "contenedor-permisos-especiales"
        ).querySelectorAll(
            "[data-permiso]"
        )
    ) {
        selector.value = "";
    }
}

function cargarPermisos(permisos) {
    limpiarPermisos();

    for (
        const [permiso, valor]
        of Object.entries(permisos || {})
    ) {
        const selector = elemento(
            "contenedor-permisos-especiales"
        ).querySelector(
            `[data-permiso="${permiso}"]`
        );

        if (selector) {
            selector.value = String(valor);
        }
    }
}

function recolectarPermisos() {
    const permisos = {};

    if (!configuracion.permisoRoles) {
        return permisos;
    }

    for (
        const selector
        of elemento(
            "contenedor-permisos-especiales"
        ).querySelectorAll(
            "[data-permiso]"
        )
    ) {
        if (selector.value === "") {
            continue;
        }

        permisos[selector.dataset.permiso] = (
            selector.value === "true"
        );
    }

    return permisos;
}

function sucursalesSeleccionadas() {
    return Array.from(
        elemento(
            "usuario-sucursales"
        ).querySelectorAll(
            'input[type="checkbox"]:checked'
        ),
        (entrada) => Number(entrada.value),
    );
}

function abrirEditor(usuario = null) {
    const esEdicion = Boolean(usuario);

    elemento("usuario-id").value = (
        usuario?.id || ""
    );
    elemento("usuario-nombre").value = (
        usuario?.nombre || ""
    );
    elemento("usuario-apellido").value = (
        usuario?.apellido || ""
    );
    elemento("usuario-email").value = (
        usuario?.email || ""
    );
    elemento("usuario-rut").value = usuario?.identificacion_fiscal || "";
    elemento("usuario-telefono").value = usuario?.telefono || "";
    elemento("usuario-password").value = "";
    elemento("usuario-password").required = (
        !esEdicion
    );
    elemento("usuario-rol").value = (
        usuario?.rol || "empleado"
    );

    elemento(
        "titulo-formulario-usuario"
    ).textContent = esEdicion
        ? "Editar usuario"
        : "Nuevo usuario";

    renderizarSucursales(
        (usuario?.sucursales || []).map(
            (asignacion) => asignacion.id
        ),
    );

    cargarPermisos(
        usuario?.permisos_especiales || {}
    );

    elemento(
        "formulario-usuario"
    ).hidden = false;

    document.body.classList.add(
        "modal-abierto"
    );

    elemento("usuario-nombre").focus();
}

function cerrarEditor() {
    elemento(
        "formulario-usuario"
    ).hidden = true;

    document.body.classList.remove(
        "modal-abierto"
    );

    elemento(
        "formulario-datos-usuario"
    ).reset();

    limpiarPermisos();
}

async function guardarUsuario(evento) {
    evento.preventDefault();

    const usuarioId = elemento(
        "usuario-id"
    ).value;

    const sucursalesIds = (
        sucursalesSeleccionadas()
    );

    if (!sucursalesIds.length) {
        notificar(
            "Selecciona al menos una sucursal.",
            "error",
        );
        return;
    }

    const datos = {
        nombre: elemento(
            "usuario-nombre"
        ).value.trim(),
        apellido: elemento(
            "usuario-apellido"
        ).value.trim(),
        email: elemento(
            "usuario-email"
        ).value.trim(),
        identificacion_fiscal: elemento("usuario-rut").value.trim(),
        telefono: elemento("usuario-telefono").value.trim(),
        sucursales_ids: sucursalesIds,
    };

    if (configuracion.permisoRoles) {
        datos.rol = elemento(
            "usuario-rol"
        ).value;
        datos.permisos_especiales = (
            recolectarPermisos()
        );
    }

    if (!usuarioId) {
        datos.password = elemento(
            "usuario-password"
        ).value;
    }

    const boton = elemento(
        "guardar-usuario"
    );
    boton.disabled = true;

    try {
        await solicitarJson(
            usuarioId
                ? (
                    `${configuracion.apiUsuarios}/`
                    + usuarioId
                )
                : configuracion.apiUsuarios,
            {
                method: usuarioId
                    ? "PATCH"
                    : "POST",
                body: JSON.stringify(datos),
            },
        );

        cerrarEditor();
        await cargarUsuarios();

        notificar(
            usuarioId
                ? "Usuario actualizado correctamente."
                : "Usuario creado correctamente.",
        );
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

async function cambiarPassword(usuario) {
    const password = window.prompt(
        (
            "Ingresa la nueva contraseña "
            + `para ${usuario.nombre}.`
        ),
    );

    if (password === null) {
        return;
    }

    if (password.length < 8) {
        notificar(
            (
                "La contraseña debe tener "
                + "al menos 8 caracteres."
            ),
            "error",
        );
        return;
    }

    try {
        await solicitarJson(
            (
                `${configuracion.apiUsuarios}/`
                + `${usuario.id}`
                + rutasAccion.cambiarPassword
            ),
            {
                method: "POST",
                body: JSON.stringify({
                    password,
                }),
            },
        );

        notificar(
            "Contraseña actualizada y sesiones revocadas."
        );
    }
    catch (error) {
        notificar(
            error.message,
            "error",
        );
    }
}

async function ejecutarAccion(
    usuario,
    accion,
) {
    const mensajes = {
        desactivar:
            "desactivar esta cuenta",
        reactivar:
            "reactivar esta cuenta",
        revocarSesiones:
            "cerrar todas las sesiones de esta cuenta",
    };

    if (
        !window.confirm(
            (
                `¿Deseas ${mensajes[accion]}?`
            ),
        )
    ) {
        return;
    }

    try {
        await solicitarJson(
            (
                `${configuracion.apiUsuarios}/`
                + `${usuario.id}`
                + rutasAccion[accion]
            ),
            {
                method: "POST",
                body: JSON.stringify({}),
            },
        );

        await cargarUsuarios();

        notificar(
            "Acción completada correctamente."
        );
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
        "abrir-formulario-usuario"
    )?.addEventListener(
        "click",
        () => abrirEditor(),
    );

    elemento(
        "formulario-datos-usuario"
    ).addEventListener(
        "submit",
        guardarUsuario,
    );

    elemento(
        "cancelar-usuario"
    ).addEventListener(
        "click",
        cerrarEditor,
    );

    elemento(
        "cerrar-formulario-usuario"
    ).addEventListener(
        "click",
        cerrarEditor,
    );

    elemento(
        "fondo-formulario-usuario"
    ).addEventListener(
        "click",
        cerrarEditor,
    );

    elemento(
        "filtro-estado-usuarios"
    ).addEventListener(
        "change",
        cargarUsuarios,
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

        try {
            await cargarSucursales();
            await cargarUsuarios();
        }
        catch (error) {
            elemento(
                "estado-lista-usuarios"
            ).textContent = error.message;

            notificar(
                error.message,
                "error",
            );
        }
    },
);
