"use strict";

const configuracion = Object.freeze({
    apiBodegasBase:
        document.body.dataset.apiBodegasBase,
});

function elemento(id) {
    return document.getElementById(id);
}

function csrfToken() {
    return document.querySelector(
        'meta[name="csrf-token"]'
    )?.content || "";
}

function opcionSeleccionada(select) {
    return (
        select.selectedOptions[0]
        ?.textContent
        ?.trim()
        || "Sin seleccionar"
    );
}

function mostrarBodegas(select, bodegas, mensajeVacio) {
    select.replaceChildren();
    if (!bodegas.length) {
        const opcion = document.createElement("option");
        opcion.value = "";
        opcion.textContent = mensajeVacio;
        select.append(opcion);
        return;
    }
    for (const item of bodegas) {
        const opcion = document.createElement("option");
        opcion.value = String(item.id);
        opcion.textContent = item.nombre;
        select.append(opcion);
    }
}

function actualizarResumen() {
    const sucursal = elemento("sucursal_id");
    const bodega = elemento("bodega_id");

    elemento(
        "resumen-sucursal"
    ).textContent = sucursal.value
        ? opcionSeleccionada(sucursal)
        : "Sin seleccionar";

    elemento(
        "resumen-bodega"
    ).textContent = bodega.value
        ? opcionSeleccionada(bodega)
        : "Sin seleccionar";

    elemento(
        "estado-contexto"
    ).textContent = (
        sucursal.value && bodega.value
            ? (
                "La operaci\u00f3n se aplicar\u00e1 "
                + "a esta ubicaci\u00f3n."
            )
            : (
                "Selecciona una sucursal "
                + "y una bodega disponibles."
            )
    );

    elemento("submit").disabled = !(
        sucursal.value
        && bodega.value
    );
}

async function cargarBodegas() {
    const sucursal = elemento("sucursal_id");
    const bodega = elemento("bodega_id");
    const sucursalId = sucursal.value;

    bodega.disabled = true;
    elemento("submit").disabled = true;
    elemento(
        "estado-contexto"
    ).textContent = "Cargando bodegas...";

    if (!sucursalId) {
        mostrarBodegas(bodega, [], "Sin bodegas disponibles");
        actualizarResumen();
        return;
    }

    try {
        const respuesta = await fetch(
            `${configuracion.apiBodegasBase}`
            + `/${sucursalId}`,
            {
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                    "X-CSRFToken": csrfToken(),
                },
            },
        );

        if (respuesta.redirected) {
            window.location.assign(
                respuesta.url
            );
            return;
        }

        if (!respuesta.ok) {
            throw new Error(
                "No fue posible cargar las bodegas."
            );
        }

        const datos = await respuesta.json();
        const bodegas = datos.bodegas || [];

        mostrarBodegas(bodega, bodegas, "Sin bodegas disponibles");
    }
    catch (error) {
        mostrarBodegas(bodega, [], "No fue posible cargar");
        elemento(
            "estado-contexto"
        ).textContent = error.message;
    }
    finally {
        bodega.disabled = false;
        actualizarResumen();
    }
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        const sucursal = elemento(
            "sucursal_id"
        );
        const bodega = elemento(
            "bodega_id"
        );
        const formulario = elemento(
            "selector-contexto"
        );

        sucursal.addEventListener(
            "change",
            cargarBodegas,
        );

        bodega.addEventListener(
            "change",
            actualizarResumen,
        );

        formulario.addEventListener(
            "submit",
            () => {
                elemento("submit").disabled = true;
                elemento(
                    "estado-contexto"
                ).textContent = (
                    "Preparando espacio de trabajo..."
                );
            },
        );

        actualizarResumen();
    },
);
