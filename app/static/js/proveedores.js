"use strict";

const configuracion = Object.freeze({
    api: document.body.dataset.apiProveedores,
    puedeCrear:
        document.body.dataset.permisoCrear === "true",
    puedeEditar:
        document.body.dataset.permisoEditar === "true",
    puedeEliminar:
        document.body.dataset.permisoEliminar === "true",
});

const estado = {
    proveedores: [],
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

function crearBoton(texto, clase, accion) {
    const boton = crearElemento("button", texto, clase);

    boton.type = "button";
    boton.addEventListener("click", accion);

    return boton;
}

function formatearDinero(valor) {
    return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
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

function obtenerTokenCsrf() {
    return document.querySelector(
        'input[name="csrf_token"]'
    )?.value || "";
}

function valorCampo(id) {
    return elemento(id)?.value.trim() || "";
}

function valorNumerico(id, predeterminado = "0") {
    const valor = valorCampo(id);

    return valor === ""
        ? predeterminado
        : valor;
}

function asignarValorCampo(id, valor) {
    const campo = elemento(id);

    if (campo) {
        campo.value = valor ?? "";
    }
}

function mostrarErrorFormulario(mensaje) {
    const error = elemento("error-proveedor");

    if (!error) {
        return;
    }

    error.textContent = mensaje || "";
    error.hidden = !mensaje;
}

function restablecerFormulario() {
    elemento("formulario-proveedor")?.reset();

    asignarValorCampo("proveedor-id", "");
    asignarValorCampo("proveedor-pais", "CL");
    asignarValorCampo("proveedor-dias-entrega", "7");
    asignarValorCampo("proveedor-compra-minima", "0");

    mostrarErrorFormulario("");
}

function abrirFormularioCreacion() {
    if (!configuracion.puedeCrear) {
        notificar(
            "No tienes permiso para crear proveedores."
        );
        return;
    }

    restablecerFormulario();

    elemento("titulo-modal-proveedor").textContent =
        "Nuevo proveedor";

    elemento("guardar-proveedor").textContent =
        "Guardar proveedor";

    elemento("modal-proveedor").hidden = false;
    elemento("proveedor-nombre")?.focus();
}

function abrirFormularioEdicion(proveedor) {
    if (!configuracion.puedeEditar) {
        notificar(
            "No tienes permiso para editar proveedores."
        );
        return;
    }

    restablecerFormulario();

    asignarValorCampo("proveedor-id", proveedor.id);
    asignarValorCampo(
        "proveedor-nombre",
        proveedor.nombre
    );
    asignarValorCampo(
        "proveedor-identificacion",
        proveedor.identificacion_fiscal
    );
    asignarValorCampo(
        "proveedor-email",
        proveedor.email
    );
    asignarValorCampo(
        "proveedor-telefono",
        proveedor.telefono
    );
    asignarValorCampo(
        "proveedor-direccion",
        proveedor.direccion
    );
    asignarValorCampo(
        "proveedor-ciudad",
        proveedor.ciudad
    );
    asignarValorCampo(
        "proveedor-pais",
        proveedor.pais || "CL"
    );
    asignarValorCampo(
        "proveedor-sitio-web",
        proveedor.sitio_web
    );
    asignarValorCampo(
        "proveedor-condiciones-pago",
        proveedor.condiciones_pago
    );
    asignarValorCampo(
        "proveedor-dias-entrega",
        proveedor.dias_entrega ?? 7
    );
    asignarValorCampo(
        "proveedor-compra-minima",
        proveedor.compra_minima ?? 0
    );
    asignarValorCampo(
        "proveedor-observaciones",
        proveedor.observaciones
    );

    elemento("titulo-modal-proveedor").textContent =
        "Editar proveedor";

    elemento("guardar-proveedor").textContent =
        "Guardar cambios";

    elemento("modal-proveedor").hidden = false;
    elemento("proveedor-nombre")?.focus();
}

function cerrarFormulario() {
    elemento("modal-proveedor").hidden = true;
    mostrarErrorFormulario("");
}

function construirDatosProveedor() {
    const nombre = valorCampo("proveedor-nombre");
    const pais = valorCampo("proveedor-pais")
        .toUpperCase();

    if (!nombre) {
        throw new Error(
            "El nombre del proveedor es obligatorio."
        );
    }

    if (
        pais.length !== 2 ||
        !/^[A-Z]{2}$/.test(pais)
    ) {
        throw new Error(
            "El país debe usar un código de dos letras."
        );
    }

    const diasEntrega = Number(
        valorNumerico("proveedor-dias-entrega", "7")
    );

    const compraMinima = Number(
        valorNumerico("proveedor-compra-minima")
    );

    if (
        !Number.isInteger(diasEntrega) ||
        diasEntrega < 0
    ) {
        throw new Error(
            "Los días de entrega deben ser un entero no negativo."
        );
    }

    if (
        !Number.isFinite(compraMinima) ||
        compraMinima < 0
    ) {
        throw new Error(
            "La compra mínima no puede ser negativa."
        );
    }

    return {
        nombre,
        identificacion_fiscal:
            valorCampo("proveedor-identificacion") || null,
        email:
            valorCampo("proveedor-email") || null,
        telefono:
            valorCampo("proveedor-telefono") || null,
        direccion:
            valorCampo("proveedor-direccion") || null,
        ciudad:
            valorCampo("proveedor-ciudad") || null,
        pais,
        sitio_web:
            valorCampo("proveedor-sitio-web") || null,
        condiciones_pago:
            valorCampo("proveedor-condiciones-pago") || null,
        dias_entrega: diasEntrega,
        compra_minima: compraMinima,
        observaciones:
            valorCampo("proveedor-observaciones") || null,
    };
}

async function guardarProveedor(evento) {
    evento.preventDefault();

    const proveedorId = valorCampo("proveedor-id");
    const editando = Boolean(proveedorId);

    const tienePermiso = editando
        ? configuracion.puedeEditar
        : configuracion.puedeCrear;

    if (!tienePermiso) {
        mostrarErrorFormulario(
            editando
                ? "No tienes permiso para editar proveedores."
                : "No tienes permiso para crear proveedores."
        );
        return;
    }

    const boton = elemento("guardar-proveedor");

    try {
        mostrarErrorFormulario("");

        const datos = construirDatosProveedor();

        const url = editando
            ? `${configuracion.api}/${proveedorId}`
            : configuracion.api;

        boton.disabled = true;
        boton.textContent = editando
            ? "Guardando cambios…"
            : "Guardando…";

        await solicitarJson(url, {
            method: editando ? "PATCH" : "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": obtenerTokenCsrf(),
            },
            body: JSON.stringify(datos),
        });

        cerrarFormulario();
        await cargarProveedores();

        notificar(
            editando
                ? "Proveedor actualizado correctamente."
                : "Proveedor creado correctamente."
        );
    } catch (error) {
        mostrarErrorFormulario(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = editando
            ? "Guardar cambios"
            : "Guardar proveedor";
    }
}

function mostrarCarga() {
    const cuerpo = elemento("tabla-proveedores");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando proveedores…",
        "estado-carga"
    );

    celda.colSpan = 8;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function mostrarError(mensaje) {
    const cuerpo = elemento("tabla-proveedores");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje,
        "tabla__vacio"
    );

    celda.colSpan = 8;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function crearContacto(proveedor) {
    const contenedor = crearElemento(
        "div",
        "",
        "proveedor-contacto"
    );

    if (proveedor.email) {
        const correo = crearElemento(
            "a",
            proveedor.email
        );

        correo.href = `mailto:${proveedor.email}`;
        contenedor.appendChild(correo);
    }

    if (proveedor.telefono) {
        contenedor.appendChild(
            crearElemento("span", proveedor.telefono)
        );
    }

    if (
        !proveedor.email &&
        !proveedor.telefono
    ) {
        contenedor.appendChild(
            crearElemento(
                "span",
                "Sin contacto registrado",
                "proveedores-tabla__detalle"
            )
        );
    }

    return contenedor;
}

function renderizarProveedores(proveedores) {
    const cuerpo = elemento("tabla-proveedores");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    elemento("cantidad-proveedores").textContent =
        `${proveedores.length} proveedor${
            proveedores.length === 1 ? "" : "es"
        }`;

    if (!proveedores.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No se encontraron proveedores.",
            "tabla__vacio"
        );

        celda.colSpan = 8;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);

        return;
    }

    proveedores.forEach((proveedor) => {
        const fila = crearElemento("tr");

        const identidad = crearElemento("td");
        const identidadContenido = crearElemento(
            "div",
            "",
            "proveedor-identidad"
        );

        identidadContenido.appendChild(
            crearElemento(
                "strong",
                proveedor.nombre || "Sin nombre"
            )
        );

        if (proveedor.condiciones_pago) {
            identidadContenido.appendChild(
                crearElemento(
                    "span",
                    proveedor.condiciones_pago,
                    "proveedores-tabla__detalle"
                )
            );
        }

        identidad.appendChild(identidadContenido);
        fila.appendChild(identidad);

        fila.appendChild(
            crearElemento(
                "td",
                proveedor.identificacion_fiscal || "—"
            )
        );

        const contacto = crearElemento("td");
        contacto.appendChild(
            crearContacto(proveedor)
        );
        fila.appendChild(contacto);

        fila.appendChild(
            crearElemento(
                "td",
                proveedor.ciudad || "—"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                `${proveedor.dias_entrega ?? 0} días`
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(
                    proveedor.compra_minima
                )
            )
        );

        const celdaEstado = crearElemento("td");

        celdaEstado.appendChild(
            crearElemento(
                "span",
                proveedor.activo
                    ? "Activo"
                    : "Inactivo",
                proveedor.activo
                    ? "insignia insignia--exito"
                    : "insignia insignia--advertencia"
            )
        );

        fila.appendChild(celdaEstado);

        const acciones = crearElemento(
            "td",
            "",
            "acciones-fila"
        );

        if (
            proveedor.activo &&
            configuracion.puedeEditar
        ) {
            acciones.appendChild(
                crearBoton(
                    "Editar",
                    "boton boton--secundario boton--pequeno",
                    () => abrirFormularioEdicion(proveedor)
                )
            );
        }

        if (
            proveedor.activo &&
            configuracion.puedeEliminar
        ) {
            acciones.appendChild(
                crearBoton(
                    "Desactivar",
                    "boton boton--secundario boton--pequeno",
                    () => solicitarDesactivacion(proveedor)
                )
            );

            acciones.appendChild(
                crearBoton(
                    "Eliminar",
                    "boton boton--peligro boton--pequeno",
                    () => solicitarEliminacion(proveedor)
                )
            );
        }

        if (
            !proveedor.activo &&
            configuracion.puedeEliminar
        ) {
            acciones.appendChild(
                crearBoton(
                    "Reactivar",
                    "boton boton--primario boton--pequeno",
                    () => solicitarReactivacion(proveedor)
                )
            );
        }

        if (
            !configuracion.puedeEditar &&
            !configuracion.puedeEliminar
        ) {
            acciones.appendChild(
                crearElemento(
                    "span",
                    "Solo lectura",
                    "proveedores-tabla__detalle"
                )
            );
        }

        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

async function cargarProveedores() {
    mostrarCarga();

    try {
        const busqueda =
            valorCampo("buscar-proveedores");

        const incluirInactivos = Boolean(
            elemento("mostrar-inactivos")?.checked
        );

        const parametros = new URLSearchParams();

        if (busqueda) {
            parametros.set("buscar", busqueda);
        }

        if (incluirInactivos) {
            parametros.set(
                "incluir_inactivos",
                "true"
            );
        }

        const consulta = parametros.toString();

        const url = consulta
            ? `${configuracion.api}?${consulta}`
            : configuracion.api;

        const datos = await solicitarJson(url);

        estado.proveedores = datos.proveedores || [];

        const titulo = elemento(
            "titulo-listado-proveedores"
        );

        if (titulo) {
            titulo.textContent = incluirInactivos
                ? "Proveedores activos e inactivos"
                : "Proveedores activos";
        }

        renderizarProveedores(estado.proveedores);
    } catch (error) {
        mostrarError(error.message);
        notificar(error.message);
    }
}

async function solicitarReactivacion(proveedor) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para reactivar proveedores."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas reactivar al proveedor "${proveedor.nombre}"?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${proveedor.id}/reactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProveedores();

        notificar(
            "Proveedor reactivado correctamente."
        );
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarDesactivacion(proveedor) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para desactivar proveedores."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas desactivar al proveedor "${proveedor.nombre}"?\n\n` +
        "El proveedor conservará sus productos, compras e historial."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${proveedor.id}/desactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProveedores();

        notificar(
            "Proveedor desactivado correctamente."
        );
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarEliminacion(proveedor) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para eliminar proveedores."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas eliminar al proveedor "${proveedor.nombre}"?\n\n` +
        "Solo se permitirá si no tiene productos ni compras asociadas."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${proveedor.id}`,
            {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProveedores();

        notificar(
            "Proveedor eliminado correctamente."
        );
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

function registrarEventos() {
    elemento("crear-proveedor")?.addEventListener(
        "click",
        abrirFormularioCreacion
    );

    elemento("cerrar-modal-proveedor")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento(
        "cerrar-modal-proveedor-boton"
    )?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("cancelar-proveedor")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("formulario-proveedor")?.addEventListener(
        "submit",
        guardarProveedor
    );

    window.addEventListener("keydown", (evento) => {
        const modal = elemento("modal-proveedor");

        if (
            evento.key === "Escape" &&
            modal &&
            !modal.hidden
        ) {
            cerrarFormulario();
        }
    });

    elemento("actualizar-proveedores")?.addEventListener(
        "click",
        cargarProveedores
    );

    elemento("mostrar-inactivos")?.addEventListener(
        "change",
        cargarProveedores
    );

    elemento("ejecutar-busqueda")?.addEventListener(
        "click",
        cargarProveedores
    );

    elemento("buscar-proveedores")?.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                cargarProveedores();
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
}

document.addEventListener("DOMContentLoaded", () => {
    registrarEventos();
    cargarProveedores();
});