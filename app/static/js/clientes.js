"use strict";

const configuracion = Object.freeze({
    api: document.body.dataset.apiClientes,
    puedeCrear:
        document.body.dataset.permisoCrear === "true",
    puedeEditar:
        document.body.dataset.permisoEditarEditar === "true",
    puedeEliminar:
        document.body.dataset.permisoEliminar === "true",
});

const estado = {
    clientes: [],
};

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

function valorCampo(id) {
    return elemento(id)?.value.trim() || "";
}

function obtenerTokenCsrf() {
    return (
        document.querySelector(
            'input[name="csrf_token"]'
        )?.value || ""
    );
}

function notificar(mensaje) {
    const notificacion = elemento("notificacion");

    if (!notificacion) {
        return;
    }

    notificacion.textContent = mensaje;
    notificacion.hidden = false;

    window.clearTimeout(
        notificar.temporizador
    );

    notificar.temporizador =
        window.setTimeout(() => {
            notificacion.hidden = true;
        }, 4500);
}

async function solicitarJson(
    url,
    opciones = {}
) {
    const respuesta = await fetch(url, {
        credentials: "same-origin",
        ...opciones,
    });

    let datos = null;

    if (respuesta.status !== 204) {
        const tipo = (
            respuesta.headers.get(
                "content-type"
            ) || ""
        ).toLowerCase();

        if (tipo.includes("application/json")) {
            datos = await respuesta.json();
        }
    }

    if (!respuesta.ok) {
        throw new Error(
            datos?.mensaje ||
            "No fue posible completar la operación."
        );
    }

    return datos;
}

function mostrarErrorFormulario(mensaje) {
    const error = elemento("error-cliente");

    if (!error) {
        return;
    }

    error.textContent = mensaje;
    error.hidden = !mensaje;
}

function abrirModal() {
    const modal = elemento("modal-cliente");

    if (!modal) {
        return;
    }

    modal.hidden = false;
    document.body.classList.add("modal-abierto");
}

function cerrarFormulario() {
    const modal = elemento("modal-cliente");

    if (!modal) {
        return;
    }

    modal.hidden = true;
    document.body.classList.remove(
        "modal-abierto"
    );

    mostrarErrorFormulario("");
}

function limpiarFormulario() {
    elemento("formulario-cliente")?.reset();

    elemento("cliente-id").value = "";
    elemento("titulo-modal-cliente").textContent =
        "Nuevo cliente";
    elemento("guardar-cliente").textContent =
        "Guardar cliente";

    mostrarErrorFormulario("");
}

function abrirFormularioCreacion() {
    if (!configuracion.puedeCrear) {
        notificar(
            "No tienes permiso para crear clientes."
        );
        return;
    }

    limpiarFormulario();
    abrirModal();
    elemento("cliente-nombre")?.focus();
}

function asignarValor(id, valor) {
    const campo = elemento(id);

    if (campo) {
        campo.value = valor ?? "";
    }
}

function abrirFormularioEdicion(cliente) {
    if (!configuracion.puedeEditar) {
        notificar(
            "No tienes permiso para editar clientes."
        );
        return;
    }

    limpiarFormulario();

    asignarValor("cliente-id", cliente.id);
    asignarValor(
        "cliente-nombre",
        cliente.nombre
    );
    asignarValor(
        "cliente-identificacion",
        cliente.identificacion_fiscal
    );
    asignarValor(
        "cliente-email",
        cliente.email
    );
    asignarValor(
        "cliente-telefono",
        cliente.telefono
    );
    asignarValor(
        "cliente-direccion",
        cliente.direccion
    );

    elemento("titulo-modal-cliente").textContent =
        "Editar cliente";
    elemento("guardar-cliente").textContent =
        "Guardar cambios";

    abrirModal();
    elemento("cliente-nombre")?.focus();
}

function construirDatosCliente() {
    const nombre = valorCampo(
        "cliente-nombre"
    );

    if (!nombre) {
        throw new Error(
            "El nombre es obligatorio."
        );
    }

    return {
        nombre,
        identificacion_fiscal:
            valorCampo(
                "cliente-identificacion"
            ) || null,
        email:
            valorCampo("cliente-email") || null,
        telefono:
            valorCampo("cliente-telefono") || null,
        direccion:
            valorCampo("cliente-direccion") || null,
    };
}

async function guardarCliente(evento) {
    evento.preventDefault();

    const clienteId = valorCampo("cliente-id");
    const editando = Boolean(clienteId);

    const tienePermiso = editando
        ? configuracion.puedeEditar
        : configuracion.puedeCrear;

    if (!tienePermiso) {
        mostrarErrorFormulario(
            editando
                ? "No tienes permiso para editar clientes."
                : "No tienes permiso para crear clientes."
        );
        return;
    }

    const boton = elemento("guardar-cliente");

    try {
        mostrarErrorFormulario("");

        const datos = construirDatosCliente();

        const url = editando
            ? `${configuracion.api}/${clienteId}`
            : configuracion.api;

        boton.disabled = true;
        boton.textContent = editando
            ? "Guardando cambios?"
            : "Guardando?";

        await solicitarJson(url, {
            method: editando ? "PATCH" : "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": obtenerTokenCsrf(),
            },
            body: JSON.stringify(datos),
        });

        cerrarFormulario();
        await cargarClientes();

        notificar(
            editando
                ? "Cliente actualizado correctamente."
                : "Cliente creado correctamente."
        );
    } catch (error) {
        mostrarErrorFormulario(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = editando
            ? "Guardar cambios"
            : "Guardar cliente";
    }
}

function crearBoton(
    texto,
    clase,
    accion
) {
    const boton = crearElemento(
        "button",
        texto,
        clase
    );

    boton.type = "button";
    boton.addEventListener("click", accion);

    return boton;
}

function crearContacto(cliente) {
    const contenedor = crearElemento(
        "div",
        "",
        "cliente-contacto"
    );

    if (cliente.email) {
        const correo = crearElemento(
            "a",
            cliente.email
        );

        correo.href = `mailto:${cliente.email}`;
        contenedor.appendChild(correo);
    }

    if (cliente.telefono) {
        const telefono = crearElemento(
            "a",
            cliente.telefono
        );

        telefono.href = (
            `tel:${cliente.telefono}`
        );

        contenedor.appendChild(telefono);
    }

    if (!cliente.email && !cliente.telefono) {
        contenedor.appendChild(
            crearElemento("span", "?")
        );
    }

    return contenedor;
}

function mostrarCarga() {
    const cuerpo = elemento("tabla-clientes");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando clientes?",
        "estado-carga"
    );

    celda.colSpan = 6;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function mostrarErrorListado(mensaje) {
    const cuerpo = elemento("tabla-clientes");

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

    celda.colSpan = 6;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function renderizarClientes(clientes) {
    const cuerpo = elemento("tabla-clientes");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const cantidad = elemento(
        "cantidad-clientes"
    );

    if (cantidad) {
        cantidad.textContent =
            `${clientes.length} cliente${
                clientes.length === 1
                    ? ""
                    : "s"
            }`;
    }

    if (!clientes.length) {
        mostrarErrorListado(
            "No se encontraron clientes."
        );
        return;
    }

    clientes.forEach((cliente) => {
        const fila = crearElemento("tr");

        const identidad = crearElemento("td");
        const identidadContenido = crearElemento(
            "div",
            "",
            "cliente-identidad"
        );

        identidadContenido.appendChild(
            crearElemento(
                "strong",
                cliente.nombre || "Sin nombre"
            )
        );

        if (cliente.email) {
            identidadContenido.appendChild(
                crearElemento(
                    "span",
                    cliente.email,
                    "clientes-tabla__detalle"
                )
            );
        }

        identidad.appendChild(
            identidadContenido
        );
        fila.appendChild(identidad);

        fila.appendChild(
            crearElemento(
                "td",
                cliente.identificacion_fiscal
                    || "?"
            )
        );

        const contacto = crearElemento("td");
        contacto.appendChild(
            crearContacto(cliente)
        );
        fila.appendChild(contacto);

        fila.appendChild(
            crearElemento(
                "td",
                cliente.direccion || "?"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                cliente.activo
                    ? "Activo"
                    : "Inactivo",
                cliente.activo
                    ? "insignia insignia--exito"
                    : "insignia insignia--neutra"
            )
        );

        const acciones = crearElemento(
            "td",
            "",
            "tabla-acciones"
        );

        if (configuracion.puedeEditar) {
            acciones.appendChild(
                crearBoton(
                    "Editar",
                    (
                        "boton boton--secundario " +
                        "boton--pequeno"
                    ),
                    () =>
                        abrirFormularioEdicion(
                            cliente
                        )
                )
            );
        }

        if (
            cliente.activo &&
            configuracion.puedeEliminar
        ) {
            acciones.appendChild(
                crearBoton(
                    "Desactivar",
                    (
                        "boton boton--secundario " +
                        "boton--pequeno"
                    ),
                    () =>
                        solicitarDesactivacion(
                            cliente
                        )
                )
            );

            acciones.appendChild(
                crearBoton(
                    "Eliminar",
                    (
                        "boton boton--peligro " +
                        "boton--pequeno"
                    ),
                    () =>
                        solicitarEliminacion(
                            cliente
                        )
                )
            );
        }

        if (
            !cliente.activo &&
            configuracion.puedeEliminar
        ) {
            acciones.appendChild(
                crearBoton(
                    "Reactivar",
                    (
                        "boton boton--primario " +
                        "boton--pequeno"
                    ),
                    () =>
                        solicitarReactivacion(
                            cliente
                        )
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
                    "texto-secundario"
                )
            );
        }

        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

async function cargarClientes() {
    mostrarCarga();

    try {
        const busqueda =
            valorCampo("buscar-clientes");

        const incluirInactivos = Boolean(
            elemento(
                "mostrar-inactivos"
            )?.checked
        );

        const parametros =
            new URLSearchParams();

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

        estado.clientes = datos.clientes || [];

        const titulo = elemento(
            "titulo-listado-clientes"
        );

        if (titulo) {
            titulo.textContent = incluirInactivos
                ? "Clientes activos e inactivos"
                : "Clientes activos";
        }

        renderizarClientes(estado.clientes);
    } catch (error) {
        mostrarErrorListado(error.message);
        notificar(error.message);
    }
}

async function solicitarReactivacion(cliente) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para reactivar clientes."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas reactivar al cliente "${cliente.nombre}"?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${cliente.id}/reactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
            }
        );

        await cargarClientes();

        notificar(
            "Cliente reactivado correctamente."
        );
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarDesactivacion(cliente) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para desactivar clientes."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas desactivar al cliente "${cliente.nombre}"?\n\n`
        + "El cliente conservará sus ventas e historial."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${cliente.id}/desactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
            }
        );

        await cargarClientes();

        notificar(
            "Cliente desactivado correctamente."
        );
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarEliminacion(cliente) {
    if (!configuracion.puedeEliminar) {
        notificar(
            "No tienes permiso para eliminar clientes."
        );
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas eliminar al cliente "${cliente.nombre}"?\n\n`
        + "Solo será posible si no tiene ventas asociadas."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${cliente.id}`,
            {
                method: "DELETE",
                headers: {
                    "X-CSRFToken":
                        obtenerTokenCsrf(),
                },
            }
        );

        await cargarClientes();

        notificar(
            "Cliente eliminado correctamente."
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
    document.body.classList.remove(
        "menu-abierto"
    );

    elemento("abrir-menu")?.setAttribute(
        "aria-expanded",
        "false"
    );
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        elemento("crear-cliente")?.addEventListener(
            "click",
            abrirFormularioCreacion
        );

        elemento(
            "cerrar-modal-cliente"
        )?.addEventListener(
            "click",
            cerrarFormulario
        );

        elemento(
            "cerrar-modal-cliente-boton"
        )?.addEventListener(
            "click",
            cerrarFormulario
        );

        elemento(
            "cancelar-cliente"
        )?.addEventListener(
            "click",
            cerrarFormulario
        );

        elemento(
            "formulario-cliente"
        )?.addEventListener(
            "submit",
            guardarCliente
        );

        elemento(
            "actualizar-clientes"
        )?.addEventListener(
            "click",
            cargarClientes
        );

        elemento(
            "mostrar-inactivos"
        )?.addEventListener(
            "change",
            cargarClientes
        );

        elemento(
            "ejecutar-busqueda"
        )?.addEventListener(
            "click",
            cargarClientes
        );

        elemento(
            "buscar-clientes"
        )?.addEventListener(
            "keydown",
            (evento) => {
                if (evento.key === "Enter") {
                    evento.preventDefault();
                    cargarClientes();
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

        cargarClientes();
    }
);
