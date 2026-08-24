"use strict";

const cuerpo = document.body;

const apiSuscripciones = (
    cuerpo.dataset.apiSuscripciones
);

const checkoutWebpaySufijo = (
    cuerpo.dataset.checkoutWebpaySufijo
    || "/checkout/webpay"
);

const checkoutMercadoPagoSufijo = (
    cuerpo.dataset.checkoutMercadopagoSufijo
    || "/checkout/mercadopago"
);

const mandatoSufijo = (
    cuerpo.dataset.mandatoSufijo
    || "/mandato/iniciar"
);

const puedeSolicitar = (
    cuerpo.dataset.puedeSolicitar === "true"
);

const estado = {
    suscripcion: null,
    planes_disponibles: [],
    catalogo_capacidades: [],
    solicitudes: [],
};

async function activarMandato() {
    const boton = elemento("boton-activar-mandato");
    const pendiente = solicitudPendiente();
    const proveedor = pendiente?.proveedor_preferido || elemento("selector-proveedor")?.value;
    if (boton) boton.disabled = true;
    try {
        const datos = await solicitarJson(
            `${apiSuscripciones}${mandatoSufijo}`,
            {
                method: "POST",
                body: JSON.stringify({proveedor}),
            },
        );
        const destino = new URL(datos.url_redireccion);
        if (destino.protocol !== "https:") {
            throw new Error("El proveedor devolvió una dirección insegura.");
        }
        if (datos.token && datos.campo_token) {
            const formulario = document.createElement("form");
            formulario.method = "post";
            formulario.action = destino.href;
            const campo = document.createElement("input");
            campo.type = "hidden";
            campo.name = datos.campo_token;
            campo.value = datos.token;
            formulario.appendChild(campo);
            document.body.appendChild(formulario);
            formulario.submit();
        } else {
            window.location.assign(destino.href);
        }
    } catch (error) {
        notificar(error.message, "error");
        if (boton) boton.disabled = false;
    }
}

const etiquetasLimites = Object.freeze({
    productos: "Productos",
    usuarios: "Usuarios",
    movimientos_mes: "Movimientos mensuales",
    sucursales: "Sucursales",
    bodegas: "Bodegas",
    almacenamiento_mb: "Almacenamiento",
});

const etiquetasGrupos = Object.freeze({
    operacion: "Operaci\u00f3n",
    gestion: "Gesti\u00f3n",
    inteligencia: "Inteligencia",
    escala: "Escala empresarial",
});

function elemento(identificador) {
    return document.getElementById(
        identificador,
    );
}

function tokenCsrf() {
    return document.querySelector(
        'input[name="csrf_token"]',
    )?.value || "";
}

async function solicitarJson(
    ruta,
    opciones = {},
) {
    const encabezados = new Headers(
        opciones.headers || {},
    );

    encabezados.set(
        "Accept",
        "application/json",
    );

    if (opciones.body) {
        encabezados.set(
            "Content-Type",
            "application/json",
        );
    }

    const csrf = tokenCsrf();

    if (csrf) {
        encabezados.set(
            "X-CSRFToken",
            csrf,
        );
    }

    const respuesta = await fetch(
        ruta,
        {
            ...opciones,
            headers: encabezados,
        },
    );

    const datos = await respuesta.json()
        .catch(() => ({}));

    if (!respuesta.ok) {
        throw new Error(
            datos.mensaje
            || "No fue posible completar la operaci\u00f3n.",
        );
    }

    return datos;
}

function notificar(
    mensaje,
    tipo = "exito",
) {
    const notificacion = elemento(
        "notificacion",
    );

    if (!notificacion) {
        return;
    }

    notificacion.textContent = mensaje;
    notificacion.dataset.tipo = tipo;
    notificacion.hidden = false;

    window.clearTimeout(
        notificar.temporizador,
    );

    notificar.temporizador = window.setTimeout(
        () => {
            notificacion.hidden = true;
        },
        4500,
    );
}

function actualizarEstadoCheckout(
    mensaje,
    tipo = "procesando",
) {
    const indicador = elemento(
        "estado-checkout",
    );

    if (!indicador) {
        return;
    }

    indicador.textContent = mensaje || "";
    indicador.dataset.tipo = tipo;
    indicador.hidden = !mensaje;
}

function redireccionarAWebpay(datos) {
    const formulario = elemento(
        "formulario-redireccion-webpay",
    );
    const token = elemento(
        "token-ws-webpay",
    );
    const url = String(
        datos?.url_redireccion || "",
    ).trim();
    const tokenWs = String(
        datos?.token || datos?.token_ws || "",
    ).trim();

    if (!formulario || !token || !url || !tokenWs) {
        throw new Error(
            "Webpay no entregó los datos necesarios para continuar.",
        );
    }

    let destino;

    try {
        destino = new URL(url);
    }
    catch (_error) {
        throw new Error(
            "Webpay entregó una dirección de pago inválida.",
        );
    }

    if (destino.protocol !== "https:") {
        throw new Error(
            "La dirección de pago de Webpay no es segura.",
        );
    }

    formulario.action = destino.href;
    token.value = tokenWs;
    actualizarEstadoCheckout(
        "Redirigiendo de forma segura a Webpay...",
    );
    formulario.submit();
}

async function iniciarCheckoutWebpay(
    solicitud,
    boton,
) {
    if (!solicitud?.id) {
        notificar(
            "La solicitud de cambio no es válida.",
            "error",
        );
        return;
    }

    const textoOriginal = boton?.textContent;

    if (boton) {
        boton.disabled = true;
        boton.textContent = "Conectando con Webpay...";
    }

    actualizarEstadoCheckout(
        "Preparando el pago seguro con Webpay...",
    );

    try {
        const pago = await solicitarJson(
            (
                `${apiSuscripciones}/solicitudes/`
                + `${solicitud.id}`
                + checkoutWebpaySufijo
            ),
            {
                method: "POST",
                body: JSON.stringify({}),
            },
        );

        redireccionarAWebpay(pago);
    }
    catch (error) {
        actualizarEstadoCheckout(
            error.message,
            "error",
        );
        notificar(
            error.message,
            "error",
        );

        if (boton) {
            boton.disabled = false;
            boton.textContent = textoOriginal;
        }
    }
}

async function iniciarCheckoutMercadoPago(
    solicitud,
    boton,
) {
    if (!solicitud?.id) {
        notificar(
            "La solicitud de cambio no es válida.",
            "error",
        );
        return;
    }

    const textoOriginal = boton?.textContent;

    if (boton) {
        boton.disabled = true;
        boton.textContent = "Conectando con Mercado Pago...";
    }

    actualizarEstadoCheckout(
        "Preparando el pago seguro con Mercado Pago...",
    );

    try {
        const pago = await solicitarJson(
            (
                `${apiSuscripciones}/solicitudes/`
                + `${solicitud.id}`
                + checkoutMercadoPagoSufijo
            ),
            {
                method: "POST",
                body: JSON.stringify({}),
            },
        );
        const destino = new URL(
            String(pago.url_redireccion || ""),
        );

        if (destino.protocol !== "https:") {
            throw new Error(
                "Mercado Pago entregó una dirección de pago insegura.",
            );
        }

        actualizarEstadoCheckout(
            "Redirigiendo de forma segura a Mercado Pago...",
        );
        window.location.assign(destino.href);
    }
    catch (error) {
        const mensaje = (
            error instanceof TypeError
                ? "Mercado Pago entregó una dirección de pago inválida."
                : error.message
        );
        actualizarEstadoCheckout(mensaje, "error");
        notificar(mensaje, "error");

        if (boton) {
            boton.disabled = false;
            boton.textContent = textoOriginal;
        }
    }
}

function textoCapitalizado(valor) {
    const texto = String(valor || "")
        .replaceAll("_", " ");

    if (!texto) {
        return "Sin informaci\u00f3n";
    }

    return (
        texto.charAt(0).toUpperCase()
        + texto.slice(1)
    );
}

function fechaLocal(valor) {
    if (!valor) {
        return "Sin vencimiento";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return "Sin vencimiento";
    }

    return new Intl.DateTimeFormat(
        "es-CL",
        {
            day: "2-digit",
            month: "short",
            year: "numeric",
        },
    ).format(fecha);
}

function precioPlan(
    plan,
    ciclo,
) {
    const valor = Number(
        ciclo === "anual"
            ? plan.precio_anual
            : plan.precio_mensual,
    );

    if (!Number.isFinite(valor)) {
        return "Consultar";
    }

    return new Intl.NumberFormat(
        "es-CL",
        {
            style: "currency",
            currency: plan.moneda || "CLP",
            maximumFractionDigits: 0,
        },
    ).format(valor);
}

function limiteVisible(
    codigo,
    valor,
) {
    if (valor === null || valor === undefined) {
        return "Sin l\u00edmite";
    }

    if (codigo === "almacenamiento_mb") {
        if (Number(valor) >= 1024) {
            const gigabytes = (
                Number(valor) / 1024
            );

            return (
                `${gigabytes.toLocaleString("es-CL")} GB`
            );
        }

        return `${valor} MB`;
    }

    return Number(valor).toLocaleString(
        "es-CL",
    );
}

function limpiar(elementoDestino) {
    elementoDestino.replaceChildren();
}

function crear(
    etiqueta,
    clase,
    texto,
) {
    const nodo = document.createElement(
        etiqueta,
    );

    if (clase) {
        nodo.className = clase;
    }

    if (texto !== undefined) {
        nodo.textContent = texto;
    }

    return nodo;
}

function solicitudPendiente() {
    return estado.solicitudes.find(
        (solicitud) => (
            [
                "pendiente",
                "pago_en_proceso",
                "cancelacion_en_revision",
            ].includes(solicitud.estado)
        ),
    );
}

function renderizarResumen() {
    const suscripcion = estado.suscripcion;

    elemento(
        "resumen-plan-actual",
    ).textContent = (
        suscripcion.plan_nombre
        || suscripcion.plan
    );

    elemento(
        "resumen-estado-suscripcion",
    ).textContent = textoCapitalizado(
        suscripcion.estado,
    );

    elemento(
        "resumen-vigencia",
    ).textContent = fechaLocal(
        suscripcion.fecha_fin,
    );

    elemento(
        "resumen-ciclo",
    ).textContent = textoCapitalizado(
        suscripcion.ciclo,
    );
}

function renderizarLimites() {
    const contenedor = elemento(
        "lista-limites-plan",
    );

    limpiar(contenedor);

    for (
        const [codigo, etiqueta]
        of Object.entries(etiquetasLimites)
    ) {
        const tarjeta = crear(
            "article",
            "planes-limite",
        );

        tarjeta.append(
            crear(
                "span",
                "planes-limite__nombre",
                etiqueta,
            ),
            crear(
                "strong",
                "planes-limite__valor",
                limiteVisible(
                    codigo,
                    estado.suscripcion
                        .limites[codigo],
                ),
            ),
        );

        contenedor.append(tarjeta);
    }
}

function capacidadesIncluidas(plan) {
    return plan.capacidades.filter(
        (capacidad) => capacidad.incluida,
    ).length;
}

function botonSolicitar(plan) {
    const boton = crear(
        "button",
        "boton boton--primario",
    );

    boton.type = "button";

    if (plan.requiere_cotizacion) {
        boton.textContent = "Solicitar contrato";
        boton.className = "boton boton--secundario";
        boton.addEventListener("click", () => {
            window.location.href = (
                "mailto:equipos@nexustock.cl"
                + "?subject=Contrato%20plan%20Empresarial%20NexuStock"
            );
        });
        return boton;
    }

    const esActual = (
        plan.codigo
        === estado.suscripcion.plan
    );

    const pendiente = solicitudPendiente();

    if (esActual) {
        boton.textContent = "Plan actual";
        boton.disabled = true;
        return boton;
    }

    if (!puedeSolicitar) {
        boton.textContent = "Sin autorizaci\u00f3n";
        boton.disabled = true;
        return boton;
    }

    if (pendiente && pendiente.estado !== "pendiente") {
        boton.textContent = "Pago en conciliación";
        boton.disabled = true;
        return boton;
    }
    boton.textContent = pendiente
        ? `Actualizar a ${plan.nombre}`
        : `Elegir ${plan.nombre}`;
    boton.dataset.planCodigo = plan.codigo;

    boton.addEventListener(
        "click",
        () => solicitarCambio(plan),
    );

    return boton;
}

function renderizarPlanes() {
    const contenedor = elemento(
        "lista-planes",
    );
    const ciclo = elemento(
        "selector-ciclo",
    ).value;

    limpiar(contenedor);

    for (
        const plan
        of estado.planes_disponibles
    ) {
        const tarjeta = crear(
            "article",
            "plan-tarjeta",
        );

        if (
            plan.codigo
            === estado.suscripcion.plan
        ) {
            tarjeta.classList.add(
                "plan-tarjeta--actual",
            );
        }

        if (
            plan.codigo.includes(
                "profesional"
            )
        ) {
            tarjeta.classList.add(
                "plan-tarjeta--destacada",
            );

            tarjeta.append(
                crear(
                    "span",
                    "plan-tarjeta__recomendada",
                    "Más elegido",
                ),
            );
        }

        const cabecera = crear(
            "div",
            "plan-tarjeta__cabecera",
        );

        const identidad = crear("div");

        identidad.append(
            crear(
                "span",
                "plan-tarjeta__codigo",
                plan.codigo,
            ),
            crear(
                "h4",
                "",
                plan.nombre,
            ),
        );

        cabecera.append(
            identidad,
            crear(
                "span",
                "plan-tarjeta__precio",
                precioPlan(plan, ciclo),
            ),
        );

        const descripcion = crear(
            "p",
            "plan-tarjeta__descripcion",
            plan.descripcion
            || "Capacidad empresarial NexuStock.",
        );

        const resumen = crear(
            "div",
            "plan-tarjeta__resumen",
        );

        const incluidas = capacidadesIncluidas(
            plan,
        );

        resumen.append(
            crear(
                "div",
                "plan-tarjeta__cobertura",
                (
                    incluidas
                    + " de "
                    + plan.capacidades.length
                    + " capacidades"
                ),
            ),
        );

        const progreso = crear(
            "div",
            "plan-tarjeta__progreso",
        );

        const progresoActivo = crear(
            "span",
            "",
        );

        progresoActivo.style.width = (
            (
                incluidas
                / plan.capacidades.length
            )
            * 100
            + "%"
        );

        progreso.append(
            progresoActivo,
        );

        resumen.append(
            progreso,
        );

        const lista = crear(
            "ul",
            "plan-tarjeta__funciones",
        );

        for (
            const capacidad
            of plan.capacidades
                .filter(
                    (item) => item.incluida,
                )
                .slice(0, 6)
        ) {
            const item = crear(
                "li",
                "",
                capacidad.nombre,
            );

            lista.append(item);
        }

        tarjeta.append(
            cabecera,
            descripcion,
            resumen,
            lista,
            botonSolicitar(plan),
        );

        contenedor.append(tarjeta);
    }
}

function planesParaComparar() {
    const actual = {
        codigo: estado.suscripcion.plan,
        nombre: (
            estado.suscripcion.plan_nombre
            || estado.suscripcion.plan
        ),
        capacidades:
            estado.suscripcion.capacidades,
    };

    const codigos = new Set([actual.codigo]);

    return [
        actual,
        ...estado.planes_disponibles.filter(
            (plan) => {
                if (codigos.has(plan.codigo)) {
                    return false;
                }

                codigos.add(plan.codigo);
                return true;
            },
        ),
    ];
}

function crearCeldaEstado(capacidad) {
    const celda = crear(
        "div",
        "planes-comparador__estado",
    );

    if (capacidad?.incluida) {
        celda.classList.add(
            "planes-comparador__estado--incluida",
        );
        celda.textContent = "\u2713";
        celda.title = "Incluida";
        return celda;
    }

    if (
        capacidad?.estado
        === "proximamente"
    ) {
        celda.classList.add(
            "planes-comparador__estado--proxima",
        );
        celda.textContent = "Pr\u00f3ximamente";
        return celda;
    }

    celda.textContent = "\u2014";
    celda.title = "No incluida";

    return celda;
}

function renderizarComparador() {
    const contenedor = elemento(
        "comparador-capacidades",
    );
    const planes = planesParaComparar();

    limpiar(contenedor);

    for (
        const [grupo, etiqueta]
        of Object.entries(etiquetasGrupos)
    ) {
        const capacidades = (
            estado.catalogo_capacidades.filter(
                (capacidad) => (
                    capacidad.grupo === grupo
                ),
            )
        );

        if (!capacidades.length) {
            continue;
        }

        const seccion = crear(
            "section",
            "planes-comparador__grupo",
        );

        seccion.append(
            crear(
                "h4",
                "",
                etiqueta,
            ),
        );

        const tabla = crear(
            "div",
            "planes-comparador__tabla",
        );

        const encabezado = crear(
            "div",
            (
                "planes-comparador__fila "
                + "planes-comparador__encabezado"
            ),
        );

        encabezado.style.setProperty(
            "--cantidad-planes",
            String(planes.length),
        );

        encabezado.append(
            crear(
                "strong",
                "",
                "Capacidad",
            ),
        );

        for (const plan of planes) {
            encabezado.append(
                crear(
                    "strong",
                    "",
                    plan.nombre,
                ),
            );
        }

        tabla.append(encabezado);

        for (
            const capacidad
            of capacidades
        ) {
            const fila = crear(
                "div",
                "planes-comparador__fila",
            );

            fila.style.setProperty(
                "--cantidad-planes",
                String(planes.length),
            );

            const descripcion = crear(
                "div",
                "planes-comparador__capacidad",
            );

            descripcion.append(
                crear(
                    "strong",
                    "",
                    capacidad.nombre,
                ),
                crear(
                    "small",
                    "",
                    capacidad.descripcion,
                ),
            );

            fila.append(descripcion);

            for (const plan of planes) {
                const detalle = (
                    plan.capacidades.find(
                        (item) => (
                            item.codigo
                            === capacidad.codigo
                        ),
                    )
                );

                fila.append(
                    crearCeldaEstado(detalle),
                );
            }

            tabla.append(fila);
        }

        seccion.append(tabla);
        contenedor.append(seccion);
    }
}

function nombrePlanPorId(identificador) {
    return (
        estado.planes_disponibles.find(
            (plan) => (
                plan.id === identificador
            ),
        )?.nombre
        || `Plan ${identificador}`
    );
}

function renderizarSolicitudes() {
    const contenedor = elemento(
        "historial-solicitudes",
    );

    limpiar(contenedor);

    if (!estado.solicitudes.length) {
        contenedor.append(
            crear(
                "div",
                "planes-solicitudes__vacio",
                (
                    "No existen solicitudes "
                    + "de cambio registradas."
                ),
            ),
        );
        return;
    }

    for (
        const solicitud
        of estado.solicitudes
    ) {
        const fila = crear(
            "article",
            "solicitud-plan",
        );

        const detalle = crear("div");

        detalle.append(
            crear(
                "strong",
                "",
                nombrePlanPorId(
                    solicitud.plan_solicitado_id,
                ),
            ),
            crear(
                "span",
                "",
                (
                    textoCapitalizado(
                        solicitud.ciclo,
                    )
                    + " \u00b7 "
                    + solicitud.moneda
                    + " "
                    + Number(
                        solicitud.monto_esperado,
                    ).toLocaleString("es-CL")
                ),
            ),
        );

        const etiquetasEstado = {
            pendiente: "Pendiente",
            pago_en_proceso: "Esperando confirmación del proveedor",
            cancelacion_en_revision: "Cancelación en revisión",
            aprobada: "Activado automáticamente",
            cancelada: "Cancelado",
            vencida: "Solicitud vencida",
        };

        const estadoSolicitud = crear(
            "span",
            (
                "solicitud-plan__estado "
                + "solicitud-plan__estado--"
                + solicitud.estado
            ),
            etiquetasEstado[solicitud.estado]
                || textoCapitalizado(solicitud.estado),
        );

        fila.append(
            detalle,
            estadoSolicitud,
        );


        contenedor.append(fila);
    }
}

function actualizarFlujoContratacion() {
    const pendiente = solicitudPendiente();
    const mandatoActivo = (
        estado.suscripcion?.metodo_pago_recurrente_estado === "activo"
    );
    let pasoActivo = "plan";

    if (mandatoActivo) {
        pasoActivo = "listo";
    }
    else if (pendiente) {
        pasoActivo = "pago";
    }

    const orden = ["perfil", "plan", "pago", "listo"];
    const indiceActivo = orden.indexOf(pasoActivo);
    for (const nodo of document.querySelectorAll("[data-paso]")) {
        const indice = orden.indexOf(nodo.dataset.paso);
        nodo.classList.toggle("flujo-planes__paso--activo", indice === indiceActivo);
        nodo.classList.toggle("flujo-planes__paso--completo", indice < indiceActivo);
    }

    const proveedor = pendiente?.proveedor_preferido || elemento("selector-proveedor")?.value;
    const proveedorNombre = elemento("mandato-proveedor-nombre");
    if (proveedorNombre) {
        proveedorNombre.textContent = proveedor === "webpay"
            ? "Webpay Oneclick"
            : "Mercado Pago Suscripciones";
    }

    const plan = estado.planes_disponibles.find(
        (item) => item.id === pendiente?.plan_solicitado_id,
    ) || estado.planes_disponibles.find((item) => item.codigo === "avanzado");
    const ciclo = pendiente?.ciclo || elemento("selector-ciclo")?.value || "mensual";
    if (plan) {
        const nombre = elemento("mandato-plan-nombre");
        const precio = elemento("mandato-plan-precio");
        if (nombre) nombre.textContent = plan.nombre;
        if (precio) precio.textContent = precioPlan(plan, ciclo);
        const productos = elemento("mandato-limite-productos");
        const usuarios = elemento("mandato-limite-usuarios");
        if (productos) {
            productos.textContent = plan.limites.productos === null
                ? "Productos según contrato"
                : `Hasta ${Number(plan.limites.productos).toLocaleString("es-CL")} productos`;
        }
        if (usuarios) {
            usuarios.textContent = plan.limites.usuarios === null
                ? "Usuarios según contrato"
                : `${plan.limites.usuarios} usuarios incluidos`;
        }
    }
}

async function consultarEstadoSolicitud(solicitud) {
    try {
        const resultado = await solicitarJson(
            `${apiSuscripciones}/solicitudes/${solicitud.id}/conciliar`,
            {method: "POST"},
        );
        notificar(
            resultado.codigo === "conciliacion_pago_no_disponible"
                ? resultado.mensaje
                : "Estado consultado directamente al proveedor.",
            resultado.codigo ? "procesando" : "exito",
        );
    }
    catch (error) {
        notificar(error.message, "procesando");
    }
    await cargarPlanes();
}

function renderizarTodo() {
    renderizarResumen();
    renderizarLimites();
    renderizarPlanes();
    renderizarComparador();
    renderizarSolicitudes();
    actualizarFlujoContratacion();

    const avisoMandato = elemento("activar-mandato");
    if (avisoMandato) {
        avisoMandato.hidden = !(
            estado.suscripcion?.estado === "prueba"
            && estado.suscripcion?.metodo_pago_recurrente_estado !== "activo"
        );
    }

    elemento(
        "estado-planes",
    ).hidden = true;
}

async function cargarPlanes() {
    const indicador = elemento(
        "estado-planes",
    );

    indicador.hidden = false;
    indicador.textContent = (
        "Cargando planes..."
    );

    try {
        const datos = await solicitarJson(
            apiSuscripciones,
        );

        estado.suscripcion = datos.suscripcion;
        estado.planes_disponibles = (
            datos.planes_disponibles || []
        );
        estado.catalogo_capacidades = (
            datos.catalogo_capacidades || []
        );
        estado.solicitudes = (
            datos.solicitudes || []
        );

        renderizarTodo();
    }
    catch (error) {
        indicador.hidden = false;
        indicador.textContent = error.message;
        notificar(
            error.message,
            "error",
        );
    }
}

async function solicitarCambio(plan) {
    const ciclo = elemento(
        "selector-ciclo",
    ).value;
    const proveedor = elemento("selector-proveedor").value;
    const pendiente = solicitudPendiente();

    const confirmado = window.confirm(
        (
            (pendiente ? "Cambiar la solicitud al plan " : "Solicitar el cambio al plan ")
            + plan.nombre
            + " con ciclo "
            + textoCapitalizado(ciclo)
            + " y pago por "
            + (proveedor === "webpay" ? "Webpay" : "Mercado Pago")
            + "?"
        ),
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            pendiente
                ? `${apiSuscripciones}/solicitudes/${pendiente.id}`
                : `${apiSuscripciones}/solicitudes`,
            {
                method: pendiente ? "PATCH" : "POST",
                body: JSON.stringify({
                    plan_codigo: plan.codigo,
                    ciclo,
                    proveedor,
                }),
            },
        );

        notificar(
            pendiente ? "Solicitud actualizada." : "Solicitud de cambio registrada.",
        );

        await cargarPlanes();
        elemento("activar-mandato")?.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
    }
    catch (error) {
        notificar(
            error.message,
            "error",
        );
    }
}

async function cancelarSolicitud(
    solicitud,
) {
    const confirmado = window.confirm(
        "Cancelar esta solicitud de cambio?",
    );

    if (!confirmado) {
        return;
    }

    try {
        const resultado = await solicitarJson(
            (
                `${apiSuscripciones}/solicitudes/`
                + `${solicitud.id}/cancelar`
            ),
            {
                method: "POST",
            },
        );

        notificar(
            resultado.estado === "cancelacion_en_revision"
                ? "La cancelación quedó en revisión. Puedes volver al dashboard."
                : "Solicitud cancelada correctamente.",
            resultado.estado === "cancelacion_en_revision"
                ? "procesando"
                : "exito",
        );

        await cargarPlanes();
    }
    catch (error) {
        notificar(
            error.message,
            "error",
        );
    }
}

function abrirMenu() {
    cuerpo.classList.add(
        "menu-abierto",
    );

    elemento(
        "abrir-menu",
    )?.setAttribute(
        "aria-expanded",
        "true",
    );
}

function cerrarMenu() {
    cuerpo.classList.remove(
        "menu-abierto",
    );

    elemento(
        "abrir-menu",
    )?.setAttribute(
        "aria-expanded",
        "false",
    );
}

function registrarEventos() {
    elemento("boton-activar-mandato")?.addEventListener("click", activarMandato);
    elemento(
        "selector-ciclo",
    )?.addEventListener(
        "change",
        () => {
            renderizarPlanes();
            actualizarFlujoContratacion();
        },
    );

    elemento(
        "selector-proveedor",
    )?.addEventListener(
        "change",
        actualizarFlujoContratacion,
    );

    elemento(
        "actualizar-planes",
    )?.addEventListener(
        "click",
        cargarPlanes,
    );

    elemento(
        "actualizar-planes-cabecera",
    )?.addEventListener(
        "click",
        cargarPlanes,
    );

    elemento(
        "abrir-menu",
    )?.addEventListener(
        "click",
        abrirMenu,
    );

    elemento(
        "cerrar-menu",
    )?.addEventListener(
        "click",
        cerrarMenu,
    );

    window.addEventListener(
        "keydown",
        (evento) => {
            if (evento.key === "Escape") {
                cerrarMenu();
            }
        },
    );
}

document.addEventListener(
    "DOMContentLoaded",
    () => {
        registrarEventos();
        cargarPlanes();
    },
);
