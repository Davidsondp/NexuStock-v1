"use strict";

const configuracion = Object.freeze({
    api: document.body.dataset.apiProductos,
    apiProveedores:
    document.body.dataset.apiProveedores,
    puedeCrear: document.body.dataset.permisoCrear === "true",
    puedeEditar: document.body.dataset.permisoEditar === "true",
    puedeEliminar: document.body.dataset.permisoEliminar === "true",
});

const estado = {
    productos: [],
    proveedores: [],
};

window.NexuStockProductos = Object.freeze({
    buscar(codigo) {
        const buscador = document.getElementById("buscar-productos");
        if (!buscador) return;
        buscador.value = String(codigo || "").trim();
        document.getElementById("ejecutar-busqueda")?.click();
    },
});

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

function renderizarOpcionesProveedores() {
    const selector = elemento("producto-proveedor");

    if (!selector) {
        return;
    }

    const valorSeleccionado = selector.value;

    limpiar(selector);

    const opcionVacia = document.createElement("option");

    opcionVacia.value = "";
    opcionVacia.textContent = "Sin proveedor asignado";

    selector.appendChild(opcionVacia);

    estado.proveedores.forEach((proveedor) => {
        const opcion = document.createElement("option");

        opcion.value = String(proveedor.id);
        opcion.textContent = proveedor.identificacion_fiscal
            ? `${proveedor.nombre} · ${proveedor.identificacion_fiscal}`
            : proveedor.nombre;

        selector.appendChild(opcion);
    });

    selector.value = valorSeleccionado;
}

function renderizarColecciones() {
    const contenedor = elemento("categorias-productos");
    if (!contenedor) return;

    const conteos = new Map();
    estado.productos.forEach((producto) => {
        const categoria = producto.categoria?.trim() || "Sin categoría";
        conteos.set(categoria, (conteos.get(categoria) || 0) + 1);
    });

    limpiar(contenedor);
    [...conteos.entries()]
        .sort((a, b) => a[0].localeCompare(b[0], "es"))
        .slice(0, 8)
        .forEach(([categoria, cantidad]) => {
            const boton = crearElemento("button", "", "nx-coleccion");
            boton.type = "button";
            boton.append(
                crearElemento("span", categoria.slice(0, 1).toUpperCase(), "nx-coleccion__icono"),
                crearElemento("strong", categoria),
                crearElemento("small", `${cantidad} producto${cantidad === 1 ? "" : "s"}`),
            );
            boton.addEventListener("click", () => {
                elemento("buscar-productos").value = categoria === "Sin categoría" ? "" : categoria;
                const filas = estado.productos.filter((producto) =>
                    (producto.categoria?.trim() || "Sin categoría") === categoria
                );
                renderizarProductos(filas);
            });
            contenedor.appendChild(boton);
        });
}

async function cargarOpcionesProveedores() {
    if (!configuracion.apiProveedores) {
        return;
    }

    try {
        const datos = await solicitarJson(
            configuracion.apiProveedores
        );

        estado.proveedores = datos.proveedores || [];

        renderizarOpcionesProveedores();
    } catch (error) {
        estado.proveedores = [];
        renderizarOpcionesProveedores();

        notificar(
            `No fue posible cargar los proveedores: ${error.message}`
        );
    }
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
    return valor === "" ? predeterminado : valor;
}

function camposPersonalizadosDesdeTexto(texto) {
    const resultado = {};
    String(texto || "").split("\n").forEach((linea) => {
        const posicion = linea.indexOf(":");
        if (posicion < 1) return;
        const nombre = linea.slice(0, posicion).trim();
        const valor = linea.slice(posicion + 1).trim();
        if (nombre) resultado[nombre] = valor;
    });
    return resultado;
}

function camposPersonalizadosATexto(campos) {
    return Object.entries(campos || {})
        .map(([nombre, valor]) => `${nombre}: ${valor}`)
        .join("\n");
}

function mostrarErrorFormulario(mensaje) {
    const error = elemento("error-producto");

    if (!error) {
        return;
    }

    error.textContent = mensaje || "";
    error.hidden = !mensaje;
}

function restablecerFormulario() {
    const formulario = elemento("formulario-producto");

    formulario?.reset();

    elemento("producto-id").value = "";
    elemento("producto-unidad-medida").value = "unidad";
    elemento("producto-unidades-caja").value = "1";
    elemento("producto-costo").value = "0";
    elemento("producto-precio").value = "0";
    elemento("producto-impuesto").value = "0.19";
    elemento("producto-stock-minimo").value = "0";
    elemento("producto-punto-reorden").value = "0";
    elemento("producto-stock-maximo").value = "";
    elemento("producto-proveedor").value = "";
    elemento("producto-incluye-iva").checked = true;

    mostrarErrorFormulario("");
}

function asignarValorCampo(id, valor) {
    const campo = elemento(id);

    if (campo) {
        campo.value = valor ?? "";
    }
}

function abrirFormularioCreacion() {
    if (!configuracion.puedeCrear) {
        notificar("No tienes permiso para crear productos.");
        return;
    }

    restablecerFormulario();

    elemento("titulo-modal-producto").textContent =
        "Nuevo producto";

    elemento("guardar-producto").textContent =
        "Guardar producto";

    elemento("modal-producto").hidden = false;
    elemento("producto-codigo")?.focus();
}

function cerrarFormulario() {
    elemento("modal-producto").hidden = true;
    mostrarErrorFormulario("");
}

function construirDatosProducto() {
    const codigo = valorCampo("producto-codigo");
    const nombre = valorCampo("producto-nombre");

    if (!codigo || !nombre) {
        throw new Error("Código y nombre son obligatorios.");
    }

    const stockMinimo = Number(
        valorNumerico("producto-stock-minimo")
    );

    const stockMaximoTexto = valorCampo(
        "producto-stock-maximo"
    );

    const stockMaximo = stockMaximoTexto === ""
        ? null
        : Number(stockMaximoTexto);

    if (
        stockMaximo !== null &&
        stockMaximo < stockMinimo
    ) {
        throw new Error(
            "El stock máximo no puede ser menor al stock mínimo."
        );
    }

    const proveedorTexto = valorCampo(
        "producto-proveedor"
    );

    return {
        codigo,
        codigo_barras:
            valorCampo("producto-codigo-barras") || null,
        nombre,
        descripcion:
            valorCampo("producto-descripcion") || null,
        categoria:
            valorCampo("producto-categoria") || null,
        subcategoria:
            valorCampo("producto-subcategoria") || null,
        marca:
            valorCampo("producto-marca") || null,
        campos_personalizados: camposPersonalizadosDesdeTexto(
            elemento("producto-campos-personalizados")?.value
        ),
        unidad_medida:
            valorCampo("producto-unidad-medida") || "unidad",
        unidades_por_caja: valorNumerico(
            "producto-unidades-caja",
            "1"
        ),
        costo_referencia: valorNumerico(
            "producto-costo"
        ),
        precio_venta: valorNumerico(
            "producto-precio"
        ),
        tasa_impuesto: valorNumerico(
            "producto-impuesto",
            "0.19"
        ),
        stock_minimo: String(stockMinimo),
        punto_reorden: valorNumerico(
            "producto-punto-reorden"
        ),
        stock_maximo: stockMaximo,
        proveedor_principal_id: proveedorTexto
            ? Number(proveedorTexto)
            : null,
        incluye_iva:
            elemento("producto-incluye-iva").checked,
        requiere_serial:
            elemento("producto-requiere-serial").checked,
        controla_lotes:
            elemento(
                "producto-controla-lotes"
            )?.checked || false,
        controla_vencimiento:
            elemento(
                "producto-controla-vencimiento"
            )?.checked || false,
    };
}

async function guardarProducto(evento) {
    evento.preventDefault();

    const productoId = valorCampo("producto-id");
    const editando = Boolean(productoId);
    const tienePermiso = editando
        ? configuracion.puedeEditar
        : configuracion.puedeCrear;

    if (!tienePermiso) {
        mostrarErrorFormulario(
            editando
                ? "No tienes permiso para editar productos."
                : "No tienes permiso para crear productos."
        );
        return;
    }

    const boton = elemento("guardar-producto");

    try {
        mostrarErrorFormulario("");

        const datos = construirDatosProducto();
        const url = editando
            ? `${configuracion.api}/${productoId}`
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
        await cargarProductos();

        notificar(
            editando
                ? "Producto actualizado correctamente."
                : "Producto creado correctamente."
        );
    } catch (error) {
        mostrarErrorFormulario(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = editando
            ? "Guardar cambios"
            : "Guardar producto";
    }
}

function mostrarCarga() {
    const cuerpo = elemento("tabla-productos");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        "Cargando productos…",
        "estado-carga"
    );

    celda.colSpan = 7;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);

    elemento("cantidad-productos").textContent = "Cargando catálogo…";
}

function mostrarError(mensaje) {
    const cuerpo = elemento("tabla-productos");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje || "No fue posible cargar los productos.",
        "tabla__vacio"
    );

    celda.colSpan = 7;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);

    elemento("cantidad-productos").textContent =
        "No fue posible cargar el catálogo";
}

function crearBoton(texto, clase, accion) {
    const boton = crearElemento("button", texto, clase);
    boton.type = "button";
    boton.addEventListener("click", accion);
    return boton;
}

function renderizarProductos(productos) {
    const cuerpo = elemento("tabla-productos");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    elemento("cantidad-productos").textContent =
        `${productos.length} producto${productos.length === 1 ? "" : "s"}`;

    if (!productos.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No se encontraron productos activos.",
            "tabla__vacio"
        );

        celda.colSpan = 7;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    productos.forEach((producto) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento("td", producto.codigo || "—")
        );

        const celdaProducto = crearElemento("td");
        celdaProducto.appendChild(
            crearElemento(
                "strong",
                producto.nombre || "Sin nombre"
            )
        );

        if (producto.codigo_barras) {
            celdaProducto.appendChild(
                crearElemento(
                    "div",
                    producto.codigo_barras,
                    "productos-tabla__detalle"
                )
            );
        }

        fila.appendChild(celdaProducto);
        fila.appendChild(
            crearElemento("td", producto.categoria || "—")
        );
        fila.appendChild(
            crearElemento("td", producto.marca || "—")
        );
        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(producto.precio_venta)
            )
        );

        const celdaEstado = crearElemento("td");
        celdaEstado.appendChild(
            crearElemento(
                "span",
                producto.activo ? "Activo" : "Inactivo",
                producto.activo
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

        acciones.appendChild(
            crearBoton(
                "Etiqueta",
                "boton boton--secundario boton--pequeno",
                () => imprimirEtiqueta(producto)
            )
        );

        if (
    producto.activo &&
    configuracion.puedeEditar
) {
    acciones.appendChild(
        crearBoton(
            "Editar",
            "boton boton--secundario boton--pequeno",
            () => abrirFormularioEdicion(producto)
        )
    );
    acciones.appendChild(
        crearBoton(
            "Imágenes",
            "boton boton--secundario boton--pequeno",
            () => window.location.assign(`/panel/productos/${producto.id}/imagenes`)
        )
    );
}

if (
    producto.activo &&
    configuracion.puedeEliminar
) {
    acciones.appendChild(
        crearBoton(
            "Desactivar",
            "boton boton--secundario boton--pequeno",
            () => solicitarDesactivacion(producto)
        )
    );

    acciones.appendChild(
        crearBoton(
            "Eliminar",
            "boton boton--peligro boton--pequeno",
            () => solicitarEliminacion(producto)
        )
    );
}

if (
    !producto.activo &&
    configuracion.puedeEliminar
) {
    acciones.appendChild(
        crearBoton(
            "Reactivar",
            "boton boton--primario boton--pequeno",
            () => solicitarReactivacion(producto)
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
                    "productos-tabla__detalle"
                )
            );
        }

        fila.appendChild(acciones);
        cuerpo.appendChild(fila);
    });
}

async function cargarProductos() {
    mostrarCarga();

    try {
        const busqueda =
            elemento("buscar-productos").value.trim();

        const incluirInactivos = Boolean(
            elemento("mostrar-inactivos")?.checked
        );

        const parametros = new URLSearchParams();

        if (busqueda) {
            parametros.set("buscar", busqueda);
        }

        if (incluirInactivos) {
            parametros.set("incluir_inactivos", "true");
        }

        const consulta = parametros.toString();

        const url = consulta
            ? `${configuracion.api}?${consulta}`
            : configuracion.api;

        const datos = await solicitarJson(url);

        estado.productos = datos.productos || [];
        renderizarColecciones();

        const titulo = elemento("titulo-listado-productos");

        if (titulo) {
            titulo.textContent = incluirInactivos
                ? "Productos activos e inactivos"
                : "Productos activos";
        }

        renderizarProductos(estado.productos);
    } catch (error) {
        mostrarError(error.message);
        notificar(error.message);
    }
}

async function imprimirEtiqueta(producto) {
    try {
        const datos = await solicitarJson(`${configuracion.api}/${producto.id}/etiqueta`);
        const item = datos.producto;
        const ventana = window.open("", "_blank", "width=520,height=420");
        if (!ventana) throw new Error("Permite ventanas emergentes para imprimir etiquetas.");
        ventana.document.write(`<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Etiqueta ${item.codigo}</title><style>@page{size:62mm 30mm;margin:0}body{margin:0;font-family:Arial,sans-serif}.etiqueta{box-sizing:border-box;display:grid;grid-template-columns:1fr 23mm;gap:2mm;width:62mm;height:30mm;padding:3mm;border:1px solid #ddd}.nombre{margin:0;font-size:10pt;font-weight:700}.codigo{margin:2mm 0 0;font-size:7pt}.precio{margin:2mm 0 0;font-size:11pt;font-weight:800}.qr{width:22mm;height:22mm;object-fit:contain}@media print{.etiqueta{border:0}}</style></head><body><div class="etiqueta"><div><p class="nombre"></p><p class="codigo"></p><p class="precio"></p></div><img class="qr" alt="Código QR"></div></body></html>`);
        ventana.document.querySelector(".nombre").textContent = item.nombre;
        ventana.document.querySelector(".codigo").textContent = item.codigo_barras;
        ventana.document.querySelector(".precio").textContent = formatearDinero(item.precio_venta);
        ventana.document.querySelector(".qr").src = item.qr;
        ventana.document.close();
        ventana.addEventListener("load", () => ventana.print(), { once: true });
    } catch (error) {
        notificar(error.message);
    }
}

/*
 * Estas funciones se conectarán en el siguiente paso.
 * Se mantienen definidas para que los botones no produzcan errores.
 */
function abrirFormularioEdicion(producto) {
    if (!configuracion.puedeEditar) {
        notificar("No tienes permiso para editar productos.");
        return;
    }

    restablecerFormulario();

    asignarValorCampo("producto-id", producto.id);
    asignarValorCampo("producto-codigo", producto.codigo);
    asignarValorCampo(
        "producto-codigo-barras",
        producto.codigo_barras
    );
    asignarValorCampo("producto-nombre", producto.nombre);
    asignarValorCampo(
        "producto-descripcion",
        producto.descripcion
    );
    asignarValorCampo("producto-categoria", producto.categoria);
    asignarValorCampo(
        "producto-subcategoria",
        producto.subcategoria
    );
    asignarValorCampo("producto-marca", producto.marca);
    asignarValorCampo(
        "producto-campos-personalizados",
        camposPersonalizadosATexto(producto.campos_personalizados)
    );
    asignarValorCampo(
        "producto-unidad-medida",
        producto.unidad_medida || "unidad"
    );
    asignarValorCampo(
        "producto-unidades-caja",
        producto.unidades_por_caja ?? 1
    );
    asignarValorCampo(
        "producto-costo",
        producto.costo_referencia ?? 0
    );
    asignarValorCampo(
        "producto-precio",
        producto.precio_venta ?? 0
    );
    asignarValorCampo(
        "producto-impuesto",
        producto.tasa_impuesto ?? "0.19"
    );
    asignarValorCampo(
        "producto-stock-minimo",
        producto.stock_minimo ?? 0
    );
    asignarValorCampo(
        "producto-punto-reorden",
        producto.punto_reorden ?? 0
    );
    asignarValorCampo(
        "producto-stock-maximo",
        producto.stock_maximo
    );
    asignarValorCampo(
        "producto-proveedor",
        producto.proveedor_principal_id
    );

    elemento("producto-incluye-iva").checked =
        Boolean(producto.incluye_iva);

    elemento("producto-requiere-serial").checked =
        Boolean(producto.requiere_serial);

    const controlaLotes = elemento(
        "producto-controla-lotes"
    );

    if (controlaLotes) {
        controlaLotes.checked = Boolean(
            producto.controla_lotes
        );
    }

    const controlaVencimiento = elemento(
        "producto-controla-vencimiento"
    );

    if (controlaVencimiento) {
        controlaVencimiento.checked = Boolean(
            producto.controla_vencimiento
        );
    }

    elemento("titulo-modal-producto").textContent =
        "Editar producto";

    elemento("guardar-producto").textContent =
        "Guardar cambios";

    elemento("modal-producto").hidden = false;
    elemento("producto-codigo")?.focus();
}

async function solicitarReactivacion(producto) {
    if (!configuracion.puedeEliminar) {
        notificar("No tienes permiso para reactivar productos.");
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas reactivar el producto "${producto.nombre}"?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${producto.id}/reactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProductos();

        notificar("Producto reactivado correctamente.");
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarDesactivacion(producto) {
    if (!configuracion.puedeEliminar) {
        notificar("No tienes permiso para desactivar productos.");
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas desactivar el producto "${producto.nombre}"?\n\n` +
        "El producto dejará de aparecer en las operaciones normales, " +
        "pero conservará su stock, movimientos e historial."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${producto.id}/desactivar`,
            {
                method: "POST",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProductos();

        notificar("Producto desactivado correctamente.");
    } catch (error) {
        notificar(error.message);
    }
}

async function solicitarEliminacion(producto) {
    if (!configuracion.puedeEliminar) {
        notificar("No tienes permiso para eliminar productos.");
        return;
    }

    const confirmado = window.confirm(
        `¿Deseas eliminar el producto "${producto.nombre}"?\n\n` +
        "Esta acción solamente será permitida si el producto no tiene " +
        "stock ni movimientos históricos."
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${configuracion.api}/${producto.id}`,
            {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
            }
        );

        await cargarProductos();

        notificar("Producto eliminado correctamente.");
    } catch (error) {
        notificar(error.message);
    }
}

function abrirMenu() {
    document.body.classList.add("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "true");
}

function cerrarMenu() {
    document.body.classList.remove("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "false");
}

function registrarEventos() {
    elemento("crear-producto")?.addEventListener(
        "click",
        abrirFormularioCreacion
    );

    elemento("cerrar-modal-producto")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("cancelar-producto")?.addEventListener(
        "click",
        cerrarFormulario
    );

    elemento("formulario-producto")?.addEventListener(
        "submit",
        guardarProducto
    );

    window.addEventListener("keydown", (evento) => {
        const modalProducto = elemento("modal-producto");

        if (
            evento.key === "Escape" &&
            modalProducto &&
            !modalProducto.hidden
        ) {
            cerrarFormulario();
        }
    });

    elemento("actualizar-productos")?.addEventListener(
        "click",
        cargarProductos
    );

    elemento("mostrar-inactivos")?.addEventListener(
    "change",
    cargarProductos
    );

    elemento("ejecutar-busqueda")?.addEventListener(
        "click",
        cargarProductos
    );

    elemento("buscar-productos")?.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Enter") {
                evento.preventDefault();
                cargarProductos();
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

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        registrarEventos();

        await Promise.all([
            cargarOpcionesProveedores(),
            cargarProductos(),
        ]);
    }
);
