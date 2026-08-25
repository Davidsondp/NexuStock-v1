"use strict";

const API = Object.freeze({
    resumen: "/api/superadmin/resumen",
    analitica: "/api/superadmin/analitica",
    empresas: "/api/superadmin/empresas",
    planes: "/api/superadmin/planes",
    suscripciones: "/api/superadmin/suscripciones",
    contratosEmpresariales: "/api/superadmin/contratos-empresariales",
    pagos: "/api/superadmin/pagos",
    auditoria: "/api/superadmin/auditoria",
});

const titulos = Object.freeze({
    resumen: "Panel global",
    empresas: "Empresas",
    planes: "Planes",
    suscripciones: "Suscripciones",
    pagos: "Pagos",
    auditoria: "Auditoría",
});

const estado = {
    seccion: "resumen",
    cargadas: new Set(),
    planes: [],
};

function elemento(id) {
    return document.getElementById(id);
}

function asignarTexto(id, valor) {
    const destino = elemento(id);

    if (destino) {
        destino.textContent = valor ?? "—";
    }
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

function formatearNumero(valor) {
    return new Intl.NumberFormat("es-CL").format(Number(valor || 0));
}

function formatearDinero(valor, moneda = "CLP") {
    return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: moneda,
        maximumFractionDigits: moneda === "CLP" ? 0 : 2,
    }).format(Number(valor || 0));
}

function formatearFecha(valor) {
    if (!valor) {
        return "—";
    }

    const fecha = new Date(valor);

    if (Number.isNaN(fecha.getTime())) {
        return "—";
    }

    return new Intl.DateTimeFormat("es-CL", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(fecha);
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

async function cambiarEstadoEmpresa(empresa, nuevoEstado) {
    let motivo = "";

    if (nuevoEstado !== "activa") {
        motivo = window.prompt(
            `Indica el motivo para suspender "${empresa.nombre}":`
        )?.trim() || "";

        if (!motivo) {
            notificar("La suspensión requiere un motivo.");
            return;
        }
    }

    const accion = nuevoEstado === "activa"
        ? "reactivar"
        : "suspender";

    const confirmado = window.confirm(
        `¿Confirmas que deseas ${accion} la empresa "${empresa.nombre}"?`
    );

    if (!confirmado) {
        return;
    }

    try {
        await solicitarJson(
            `${API.empresas}/${empresa.id}/estado`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": obtenerTokenCsrf(),
                },
                body: JSON.stringify({
                    estado: nuevoEstado,
                    motivo,
                }),
            }
        );

        estado.cargadas.delete("empresas");
        estado.cargadas.delete("resumen");

        await cargarEmpresas(true);
        notificar(
            nuevoEstado === "activa"
                ? "Empresa reactivada correctamente."
                : "Empresa suspendida correctamente."
        );
    } catch (error) {
        notificar(error.message);
    }
}

function claseEstado(valor) {
    if (["activa", "activo", "pagado", "prueba"].includes(valor)) {
        return "insignia insignia--exito";
    }

    if (["suspendida", "pendiente"].includes(valor)) {
        return "insignia insignia--advertencia";
    }

    if (["cancelada", "cancelado", "fallido"].includes(valor)) {
        return "insignia insignia--peligro";
    }

    return "insignia";
}

function crearInsignia(valor) {
    const texto = valor || "Sin estado";
    return crearElemento("span", texto, claseEstado(texto));
}

function cerrarMenu() {
    document.body.classList.remove("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "false");
}

function abrirMenu() {
    document.body.classList.add("menu-abierto");
    elemento("abrir-menu")?.setAttribute("aria-expanded", "true");
}

function mostrarSeccion(nombre) {
    if (!titulos[nombre]) {
        return;
    }

    estado.seccion = nombre;

    document.querySelectorAll("[data-contenido-seccion]").forEach((seccion) => {
        seccion.hidden = seccion.dataset.contenidoSeccion !== nombre;
    });

    document.querySelectorAll("[data-seccion]").forEach((boton) => {
        if (boton.dataset.seccion === nombre) {
            boton.setAttribute("aria-current", "page");
        } else {
            boton.removeAttribute("aria-current");
        }
    });

    asignarTexto("titulo-pagina", titulos[nombre]);
    cerrarMenu();
    cargarSeccion(nombre);
}

async function cargarResumen(forzar = false) {
    if (estado.cargadas.has("resumen") && !forzar) {
        return;
    }

    try {
        const meses = elemento("periodo-analitica")?.value || "12";
        const [resumen, analitica, empresas, auditoria] = await Promise.all([
            solicitarJson(API.resumen),
            solicitarJson(`${API.analitica}?meses=${encodeURIComponent(meses)}`),
            solicitarJson(`${API.empresas}?estado=activa`),
            solicitarJson(`${API.auditoria}?limite=6`),
        ]);

        asignarTexto("metrica-empresas", formatearNumero(resumen.empresas));
        asignarTexto(
            "metrica-empresas-activas",
            formatearNumero(resumen.empresas_activas)
        );
        asignarTexto(
            "metrica-usuarios",
            formatearNumero(resumen.usuarios_empresariales)
        );
        asignarTexto(
            "metrica-suscripciones",
            formatearNumero(resumen.suscripciones_activas)
        );
        asignarTexto(
            "metrica-pagos",
            formatearNumero(resumen.pagos_confirmados)
        );
        asignarTexto(
            "metrica-ingresos",
            formatearDinero(resumen.ingresos_confirmados)
        );
        renderizarAnalitica(analitica);

        renderizarEmpresasResumen((empresas.empresas || []).slice(0, 6));
        renderizarActividad(auditoria.auditoria || []);

        estado.cargadas.add("resumen");
    } catch (error) {
        notificar(error.message);
    }
}

document.querySelectorAll("[data-ir-seccion], [data-ir-usuarios]").forEach((tarjeta) => {
    const abrir = () => {
        if (tarjeta.dataset.irUsuarios) window.location.assign(tarjeta.dataset.irUsuarios);
        else mostrarSeccion(tarjeta.dataset.irSeccion);
    };
    tarjeta.addEventListener("click", abrir);
    tarjeta.addEventListener("keydown", (evento) => {
        if (["Enter", " "].includes(evento.key)) { evento.preventDefault(); abrir(); }
    });
});

function formatearPorcentaje(valor) {
    if (valor === null || valor === undefined) return "Sin base";
    const signo = Number(valor) > 0 ? "+" : "";
    return `${signo}${new Intl.NumberFormat("es-CL", { maximumFractionDigits: 1 }).format(valor)}%`;
}

function renderizarAnalitica(datos) {
    asignarTexto("analitica-ingresos", formatearDinero(datos.ingresos_periodo, datos.moneda));
    asignarTexto("analitica-crecimiento", formatearPorcentaje(datos.crecimiento_ingresos_pct));
    asignarTexto("analitica-ticket", formatearDinero(datos.ticket_promedio, datos.moneda));
    asignarTexto("analitica-activacion", `${datos.tasa_activacion_pct}%`);
    asignarTexto("analitica-pagos", `${formatearNumero(datos.pagos_periodo)} pagos confirmados`);
    asignarTexto("analitica-altas", `${formatearNumero(datos.nuevas_empresas)} empresas nuevas`);
    asignarTexto("analitica-comparacion", datos.crecimiento_ingresos_pct === null
        ? "Aún no existe un período anterior con ingresos"
        : `Anterior: ${formatearDinero(datos.ingresos_periodo_anterior, datos.moneda)}`);
    asignarTexto("analitica-actualizada", `Actualizado ${formatearFecha(datos.actualizado_en)} · Solo pagos confirmados en CLP`);
    renderizarLineaIngresos(datos.serie || [], datos.moneda);
    renderizarBarrasEmpresas(datos.serie || []);
    renderizarComposicionPlanes(datos.planes_vigentes || []);
}

function svgNodo(nombre, atributos = {}) {
    const nodo = document.createElementNS("http://www.w3.org/2000/svg", nombre);
    Object.entries(atributos).forEach(([clave, valor]) => nodo.setAttribute(clave, valor));
    return nodo;
}

function renderizarLineaIngresos(serie, moneda) {
    const destino = elemento("grafica-ingresos");
    if (!destino) return;
    limpiar(destino);
    const valores = serie.map((punto) => Number(punto.ingresos || 0));
    const maximo = Math.max(...valores, 1);
    const ancho = 760, alto = 260, margenX = 42, margenY = 26;
    const svg = svgNodo("svg", { viewBox: `0 0 ${ancho} ${alto}`, preserveAspectRatio: "none", "aria-hidden": "true" });
    [0, 0.5, 1].forEach((factor) => {
        const y = margenY + (alto - margenY * 2) * factor;
        svg.appendChild(svgNodo("line", { x1: margenX, y1: y, x2: ancho - margenX, y2: y, class: "grafica__guia" }));
    });
    const puntos = valores.map((valor, indice) => {
        const x = margenX + (indice / Math.max(valores.length - 1, 1)) * (ancho - margenX * 2);
        const y = alto - margenY - (valor / maximo) * (alto - margenY * 2);
        return { x, y, valor, etiqueta: serie[indice].etiqueta };
    });
    const linea = puntos.map((p, i) => `${i ? "L" : "M"}${p.x},${p.y}`).join(" ");
    const area = `${linea} L${puntos.at(-1)?.x || margenX},${alto - margenY} L${puntos[0]?.x || margenX},${alto - margenY} Z`;
    svg.appendChild(svgNodo("path", { d: area, class: "grafica__area" }));
    svg.appendChild(svgNodo("path", { d: linea, class: "grafica__linea" }));
    puntos.forEach((punto, indice) => {
        const circulo = svgNodo("circle", { cx: punto.x, cy: punto.y, r: 5, class: "grafica__punto", tabindex: "0" });
        const titulo = svgNodo("title");
        titulo.textContent = `${punto.etiqueta}: ${formatearDinero(punto.valor, moneda)}`;
        circulo.appendChild(titulo); svg.appendChild(circulo);
        if (indice === 0 || indice === puntos.length - 1 || (serie.length <= 12 && indice % 2 === 0)) {
            const texto = svgNodo("text", { x: punto.x, y: alto - 5, class: "grafica__etiqueta", "text-anchor": "middle" });
            texto.textContent = punto.etiqueta; svg.appendChild(texto);
        }
    });
    destino.appendChild(svg);
}

function renderizarBarrasEmpresas(serie) {
    const destino = elemento("grafica-empresas"); if (!destino) return; limpiar(destino);
    const maximo = Math.max(...serie.map((p) => Number(p.nuevas_empresas || 0)), 1);
    serie.forEach((punto) => {
        const item = crearElemento("div", "", "barra-item");
        const barra = crearElemento("span", "", "barra-item__barra");
        barra.style.height = `${Math.max((Number(punto.nuevas_empresas || 0) / maximo) * 100, 3)}%`;
        barra.title = `${punto.etiqueta}: ${punto.nuevas_empresas}`;
        item.append(barra, crearElemento("small", punto.etiqueta)); destino.appendChild(item);
    });
}

function renderizarComposicionPlanes(planes) {
    const destino = elemento("grafica-planes"); if (!destino) return; limpiar(destino);
    const total = planes.reduce((suma, plan) => suma + Number(plan.cantidad || 0), 0);
    if (!total) { destino.appendChild(crearElemento("p", "Aún no hay planes vigentes.", "estado-carga")); return; }
    const colores = ["#4f46e5", "#06b6d4", "#10b981", "#f59e0b", "#ec4899"];
    let acumulado = 0; const segmentos = planes.map((plan, i) => { const inicio = acumulado; acumulado += plan.cantidad / total * 100; return `${colores[i % colores.length]} ${inicio}% ${acumulado}%`; });
    const dona = crearElemento("div", "", "planes-dona"); dona.style.background = `conic-gradient(${segmentos.join(",")})`;
    const centro = crearElemento("span", "", "planes-dona__centro"); centro.append(crearElemento("strong", total), crearElemento("small", "vigentes")); dona.appendChild(centro);
    const lista = crearElemento("ul", "", "planes-leyenda");
    planes.forEach((plan, i) => { const item = crearElemento("li"); const punto = crearElemento("i"); punto.style.background = colores[i % colores.length]; item.append(punto, crearElemento("span", plan.nombre), crearElemento("strong", plan.cantidad)); lista.appendChild(item); });
    destino.append(dona, lista);
}

function renderizarEmpresasResumen(empresas) {
    const cuerpo = elemento("resumen-empresas");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!empresas.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No existen empresas activas.",
            "tabla__vacio"
        );

        celda.colSpan = 3;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    empresas.forEach((empresa) => {
        const fila = crearElemento("tr");
        fila.appendChild(crearElemento("td", empresa.nombre || "—"));
        fila.appendChild(
            crearElemento("td", empresa.identificacion_fiscal || "—")
        );

        const estadoCelda = crearElemento("td");
        estadoCelda.appendChild(crearInsignia(empresa.estado));
        fila.appendChild(estadoCelda);

        cuerpo.appendChild(fila);
    });
}

function renderizarActividad(registros) {
    const lista = elemento("resumen-actividad");

    if (!lista) {
        return;
    }

    limpiar(lista);

    if (!registros.length) {
        lista.appendChild(
            crearElemento(
                "li",
                "No existe actividad registrada.",
                "estado-carga"
            )
        );
        return;
    }

    registros.forEach((registro) => {
        const item = crearElemento("li", "", "actividad");
        const punto = crearElemento("span", "", "actividad__punto");
        punto.setAttribute("aria-hidden", "true");

        const contenido = crearElemento("div");
        contenido.appendChild(
            crearElemento(
                "p",
                registro.accion || "Actividad registrada",
                "actividad__titulo"
            )
        );
        contenido.appendChild(
            crearElemento(
                "p",
                `${registro.modulo || "sistema"} · ${formatearFecha(registro.fecha)}`,
                "actividad__detalle"
            )
        );

        item.appendChild(punto);
        item.appendChild(contenido);
        lista.appendChild(item);
    });
}

async function cargarEmpresas(forzar = false) {
    if (estado.cargadas.has("empresas") && !forzar) {
        return;
    }

    const parametros = new URLSearchParams();
    const buscar = elemento("filtro-empresa-buscar")?.value.trim();
    const estadoEmpresa = elemento("filtro-empresa-estado")?.value;

    if (buscar) {
        parametros.set("buscar", buscar);
    }

    if (estadoEmpresa) {
        parametros.set("estado", estadoEmpresa);
    }

    const cuerpo = elemento("tabla-empresas");

    if (cuerpo) {
        limpiar(cuerpo);
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "Cargando empresas…",
            "estado-carga"
        );

        celda.colSpan = 5;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
    }

    try {
        const consulta = parametros.toString();
        const url = consulta
            ? `${API.empresas}?${consulta}`
            : API.empresas;

        const datos = await solicitarJson(url);

        renderizarEmpresas(datos.empresas || []);
        estado.cargadas.add("empresas");
    } catch (error) {
        renderizarErrorTabla(
            "tabla-empresas",
            5,
            error.message
        );
        notificar(error.message);
    }
}

function renderizarEmpresas(empresas) {
    const cuerpo = elemento("tabla-empresas");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!empresas.length) {
        const fila = crearElemento("tr");
        const celda = crearElemento(
            "td",
            "No se encontraron empresas.",
            "tabla__vacio"
        );

        celda.colSpan = 5;
        fila.appendChild(celda);
        cuerpo.appendChild(fila);
        return;
    }

    empresas.forEach((empresa) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento("td", empresa.nombre || "—")
        );

        fila.appendChild(
            crearElemento("td", empresa.email || "—")
        );

        fila.appendChild(
            crearElemento(
                "td",
                empresa.identificacion_fiscal || "—"
            )
        );

        const celdaEstado = crearElemento("td");
        celdaEstado.appendChild(crearInsignia(empresa.estado));
        fila.appendChild(celdaEstado);

        const celdaAcciones = crearElemento("td");
        const detalle = empresa.motivo_suspension
            ? `Motivo: ${empresa.motivo_suspension}`
            : "Sin observaciones";

        const boton = crearElemento(
            "button",
            "Ver estado",
            "boton boton--secundario boton--pequeno"
        );

        boton.type = "button";
        boton.addEventListener("click", () => {
            notificar(
                `${empresa.nombre}: ${empresa.estado}. ${detalle}`
            );
        });

        celdaAcciones.appendChild(boton);

const botonEstado = crearElemento(
    "button",
    empresa.estado === "activa" ? "Suspender" : "Reactivar",
    empresa.estado === "activa"
        ? "boton boton--peligro boton--pequeno"
        : "boton boton--primario boton--pequeno"
);

botonEstado.type = "button";

botonEstado.addEventListener("click", () => {
    cambiarEstadoEmpresa(
        empresa,
        empresa.estado === "activa" ? "suspendida" : "activa"
    );
});

celdaAcciones.appendChild(botonEstado);
fila.appendChild(celdaAcciones);
        cuerpo.appendChild(fila);
    });
}

function renderizarErrorTabla(id, columnas, mensaje) {
    const cuerpo = elemento(id);

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje || "No fue posible cargar la información.",
        "tabla__vacio"
    );

    celda.colSpan = columnas;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

async function cargarPlanes(forzar = false) {
    if (estado.cargadas.has("planes") && !forzar) {
        return;
    }

    const contenedor = elemento("lista-planes");

    if (contenedor) {
        limpiar(contenedor);
        contenedor.appendChild(
            crearElemento(
                "article",
                "Cargando planes…",
                "tarjeta estado-carga"
            )
        );
    }

    try {
        const datos = await solicitarJson(API.planes);
        renderizarCatalogoPlanes(datos.planes || []);
        estado.cargadas.add("planes");
    } catch (error) {
        renderizarErrorPlanes(error.message);
        notificar(error.message);
    }
}

function renderizarCatalogoPlanes(planes) {
    const contenedor = elemento("lista-planes");

    if (!contenedor) {
        return;
    }

    limpiar(contenedor);
    estado.planes = [...planes].sort((a, b) => (
        Number(b.es_publico) - Number(a.es_publico)
        || Number(a.orden || 0) - Number(b.orden || 0)
    ));

    const publicos = estado.planes.filter((plan) => plan.es_publico);
    const internos = estado.planes.filter((plan) => !plan.es_publico);
    asignarTexto("total-planes-publicos", publicos.length);
    asignarTexto(
        "total-planes-facturables",
        publicos.filter((plan) => plan.es_facturable).length
    );
    asignarTexto("total-niveles-internos", internos.length);

    if (!planes.length) {
        contenedor.appendChild(
            crearElemento(
                "article",
                "No existen planes configurados.",
                "tarjeta estado-carga"
            )
        );
        return;
    }

    let grupoActual = null;
    let rejillaActual = null;

    estado.planes.forEach((plan) => {
        const claveGrupo = plan.es_publico ? "publicos" : "internos";

        if (claveGrupo !== grupoActual) {
            grupoActual = claveGrupo;
            const grupo = crearElemento("section", "", "grupo-planes");
            const cabeceraGrupo = crearElemento("header", "", "grupo-planes__cabecera");
            cabeceraGrupo.append(
                crearElemento(
                    "h3",
                    plan.es_publico ? "Catálogo público" : "Niveles internos"
                ),
                crearElemento(
                    "p",
                    plan.es_publico
                        ? "Las cuatro opciones visibles en la página de planes."
                        : "Continuidad gratuita y contratos especiales; no aparecen en la portada."
                )
            );
            rejillaActual = crearElemento("div", "", "grupo-planes__rejilla");
            grupo.append(cabeceraGrupo, rejillaActual);
            contenedor.appendChild(grupo);
        }

        const tarjeta = crearElemento(
            "article",
            "",
            plan.es_publico
                ? "tarjeta tarjeta-plan"
                : "tarjeta tarjeta-plan tarjeta-plan--interna"
        );

        const cabecera = crearElemento(
            "div",
            "",
            "tarjeta__cabecera"
        );

        const encabezado = crearElemento("div");

        encabezado.appendChild(
            crearElemento(
                "h3",
                plan.nombre || plan.codigo || "Plan",
                "tarjeta__titulo"
            )
        );

        encabezado.appendChild(
            crearElemento(
                "p",
                plan.codigo || "Sin código",
                "tarjeta__descripcion"
            )
        );

        cabecera.appendChild(encabezado);
        cabecera.appendChild(
            crearInsignia(plan.activo ? "activo" : "inactivo")
        );

        tarjeta.appendChild(cabecera);

        const clasificacion = crearElemento("p", "", "tarjeta-plan__clasificacion");
        clasificacion.appendChild(
            crearElemento(
                "span",
                plan.es_publico ? "Público" : "Interno",
                plan.es_publico ? "insignia" : "insignia insignia--interna"
            )
        );
        clasificacion.appendChild(
            crearElemento(
                "span",
                plan.es_facturable ? "Facturable" : "No facturable",
                plan.es_facturable ? "insignia insignia--exito" : "insignia"
            )
        );
        tarjeta.appendChild(clasificacion);

        const precioMensual = crearElemento(
            "p",
            !plan.es_facturable
                ? "Prueba gratuita"
                : formatearDinero(plan.precio_mensual),
            "metrica__valor"
        );

        tarjeta.appendChild(precioMensual);

        tarjeta.appendChild(
            crearElemento(
                "p",
                plan.codigo === "prueba"
                    ? `${plan.dias_prueba} días · no facturable`
                    : plan.codigo === "basico"
                        ? "Continuidad mínima · uso interno"
                        : plan.codigo === "corporativo"
                            ? "Contrato especial · uso interno"
                    : `${formatearDinero(plan.precio_anual)} al año`,
                "metrica__detalle"
            )
        );

        const limites = crearElemento(
            "ul",
            "",
            "lista-actividad"
        );

        agregarDetallePlan(
            limites,
            "Artículos únicos",
            formatearLimite(plan.limite_productos)
        );

        agregarDetallePlan(
            limites,
            "Usuarios",
            formatearLimite(plan.limite_usuarios)
        );

        agregarDetallePlan(
            limites,
            "Movimientos mensuales",
            formatearLimite(plan.limite_movimientos_mes)
        );

        agregarDetallePlan(
            limites,
            "Sucursales",
            formatearLimite(plan.limite_sucursales)
        );

        agregarDetallePlan(
            limites,
            "Bodegas",
            formatearLimite(plan.limite_bodegas)
        );

        tarjeta.appendChild(limites);

        const funcionesActivas = Object.entries(plan.funciones || {})
            .filter(([, habilitada]) => habilitada === true)
            .map(([funcion]) => funcion.replaceAll("_", " "));

        tarjeta.appendChild(
            crearElemento(
                "p",
                funcionesActivas.length
                    ? `Funciones: ${funcionesActivas.join(", ")}`
                    : "Sin funciones adicionales habilitadas.",
                "tarjeta__descripcion"
            )
        );

        const acciones = crearElemento("div", "", "tarjeta__acciones");
        const editar = crearElemento(
            "button",
            "Editar plan",
            "boton boton--primario boton--pequeno"
        );

        editar.type = "button";
        editar.addEventListener("click", () => abrirEditorPlan(plan));
        acciones.appendChild(editar);
        tarjeta.appendChild(acciones);

        rejillaActual?.appendChild(tarjeta);
    });
}

function asignarValor(id, valor) {
    const campo = elemento(id);

    if (campo) {
        campo.value = valor ?? "";
    }
}

function abrirEditorPlan(plan) {
    asignarValor("editor-plan-id", plan.id);
    asignarValor("plan-nombre", plan.nombre);
    asignarValor("plan-descripcion", plan.descripcion);
    asignarValor("plan-precio-mensual", plan.precio_mensual);
    asignarValor("plan-precio-anual", plan.precio_anual);
    asignarValor("plan-dias-prueba", plan.dias_prueba);
    asignarValor("plan-limite-productos", plan.limite_productos);
    asignarValor("plan-limite-usuarios", plan.limite_usuarios);
    asignarValor("plan-limite-movimientos", plan.limite_movimientos_mes);
    asignarValor("plan-limite-sucursales", plan.limite_sucursales);
    asignarValor("plan-limite-bodegas", plan.limite_bodegas);
    asignarValor("plan-orden", plan.orden);

    asignarTexto("editor-plan-titulo", `Editar ${plan.nombre}`);
    asignarTexto("editor-plan-codigo", `Código permanente: ${plan.codigo}`);

    const activo = elemento("plan-activo");
    if (activo) {
        activo.checked = plan.activo === true;
        activo.disabled = plan.codigo === "prueba";
    }

    const reglas = plan.reglas_edicion || {};
    const precioMensual = elemento("plan-precio-mensual");
    const precioAnual = elemento("plan-precio-anual");
    const diasPrueba = elemento("plan-dias-prueba");
    if (precioMensual) precioMensual.disabled = reglas.precios !== true;
    if (precioAnual) precioAnual.disabled = reglas.precios !== true;
    if (diasPrueba) diasPrueba.disabled = reglas.dias_prueba !== true;
    asignarTexto(
        "plan-activo-etiqueta",
        plan.es_publico
            ? "Plan disponible en el catálogo público"
            : "Nivel técnico interno activo"
    );

    const funciones = elemento("editor-plan-funciones");
    limpiar(funciones);

    Object.entries(plan.funciones || {})
        .sort(([a], [b]) => a.localeCompare(b, "es"))
        .forEach(([codigo, habilitada]) => {
            const etiqueta = crearElemento("label", "", "funcion-plan");
            const control = crearElemento("input");
            const nombre = codigo.replaceAll("_", " ").replaceAll(".", " · ");

            control.type = "checkbox";
            control.checked = habilitada === true;
            control.dataset.funcion = codigo;
            etiqueta.append(control, crearElemento("span", nombre));
            funciones.appendChild(etiqueta);
        });

    elemento("editor-plan")?.showModal();
}

function cerrarEditorPlan() {
    const activo = elemento("plan-activo");
    if (activo) activo.disabled = false;
    elemento("editor-plan")?.close();
}

function numeroNullable(id) {
    const valor = elemento(id)?.value.trim();
    return valor === "" || valor === undefined ? null : Number(valor);
}

async function guardarPlan(evento) {
    evento.preventDefault();

    const planId = Number(elemento("editor-plan-id")?.value);
    const boton = elemento("guardar-plan");
    const funciones = {};

    elemento("editor-plan-funciones")
        ?.querySelectorAll("input[data-funcion]")
        .forEach((control) => {
            funciones[control.dataset.funcion] = control.checked;
        });

    const datos = {
        nombre: elemento("plan-nombre")?.value.trim(),
        descripcion: elemento("plan-descripcion")?.value.trim(),
        precio_mensual: Number(elemento("plan-precio-mensual")?.value),
        precio_anual: Number(elemento("plan-precio-anual")?.value),
        dias_prueba: Number(elemento("plan-dias-prueba")?.value),
        limite_productos: numeroNullable("plan-limite-productos"),
        limite_usuarios: numeroNullable("plan-limite-usuarios"),
        limite_movimientos_mes: numeroNullable("plan-limite-movimientos"),
        limite_sucursales: numeroNullable("plan-limite-sucursales"),
        limite_bodegas: numeroNullable("plan-limite-bodegas"),
        orden: Number(elemento("plan-orden")?.value),
        activo: elemento("plan-activo")?.checked === true,
        funciones,
    };

    boton.disabled = true;
    boton.textContent = "Guardando…";

    try {
        await solicitarJson(`${API.planes}/${planId}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": obtenerTokenCsrf(),
            },
            body: JSON.stringify(datos),
        });
        cerrarEditorPlan();
        estado.cargadas.delete("planes");
        await cargarPlanes(true);
        notificar("Plan actualizado correctamente.");
    } catch (error) {
        notificar(error.message);
    } finally {
        boton.disabled = false;
        boton.textContent = "Guardar cambios";
    }
}

function agregarDetallePlan(lista, nombre, valor) {
    const item = crearElemento("li", "", "actividad");
    const punto = crearElemento(
        "span",
        "",
        "actividad__punto"
    );

    punto.setAttribute("aria-hidden", "true");

    const contenido = crearElemento("div");

    contenido.appendChild(
        crearElemento(
            "p",
            nombre,
            "actividad__titulo"
        )
    );

    contenido.appendChild(
        crearElemento(
            "p",
            valor,
            "actividad__detalle"
        )
    );

    item.appendChild(punto);
    item.appendChild(contenido);
    lista.appendChild(item);
}

function formatearLimite(valor) {
    if (valor === null || valor === undefined) {
        return "Ilimitado";
    }

    return formatearNumero(valor);
}

function renderizarErrorPlanes(mensaje) {
    const contenedor = elemento("lista-planes");

    if (!contenedor) {
        return;
    }

    limpiar(contenedor);

    contenedor.appendChild(
        crearElemento(
            "article",
            mensaje || "No fue posible cargar los planes.",
            "tarjeta estado-carga"
        )
    );
}

async function cargarSuscripciones(forzar = false) {
    if (estado.cargadas.has("suscripciones") && !forzar) {
        return;
    }

    mostrarCargaTabla(
        "tabla-suscripciones",
        9,
        "Cargando suscripciones…"
    );
    mostrarCargaTabla(
        "tabla-contratos-empresariales",
        6,
        "Cargando contratos…"
    );

    try {
        const [datos, contratos] = await Promise.all([
            solicitarJson(API.suscripciones),
            solicitarJson(API.contratosEmpresariales),
        ]);
        renderizarSuscripciones(datos.suscripciones || []);
        renderizarContratosEmpresariales(contratos.solicitudes || []);
        estado.cargadas.add("suscripciones");
    } catch (error) {
        renderizarErrorTabla(
            "tabla-suscripciones",
            9,
            error.message
        );
        renderizarErrorTabla(
            "tabla-contratos-empresariales",
            6,
            error.message
        );
        notificar(error.message);
    }
}

function renderizarContratosEmpresariales(solicitudes) {
    const cuerpo = elemento("tabla-contratos-empresariales");
    if (!cuerpo) return;
    limpiar(cuerpo);
    if (!solicitudes.length) {
        agregarFilaVacia(cuerpo, 6, "No existen solicitudes empresariales.");
        return;
    }
    solicitudes.forEach((solicitud) => {
        const fila = crearElemento("tr");
        fila.appendChild(crearElemento("td", solicitud.empresa_nombre || "—"));
        fila.appendChild(crearElemento("td", `${solicitud.contacto_nombre || "—"}\n${solicitud.email || ""}`));
        fila.appendChild(crearElemento("td", `${formatearNumero(solicitud.productos_estimados)} productos · ${formatearNumero(solicitud.usuarios_estimados)} usuarios`));
        const estadoCelda = crearElemento("td");
        estadoCelda.appendChild(crearInsignia(solicitud.estado));
        fila.appendChild(estadoCelda);
        fila.appendChild(crearElemento("td", formatearFecha(solicitud.creado_en)));
        const control = crearElemento("td");
        const boton = crearElemento("button", "Gestionar", "boton boton--secundario boton--pequeno");
        boton.type = "button";
        boton.addEventListener("click", async () => {
            const nuevo = window.prompt("Estado: nueva, contactada, cotizada, contratada o descartada", solicitud.estado);
            if (!nuevo) return;
            const observacion = window.prompt("Observación interna:", solicitud.observacion_interna || "") || "";
            try {
                await solicitarJson(`${API.contratosEmpresariales}/${solicitud.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({estado: nuevo.trim(), observacion: observacion.trim()}),
                });
                await cargarSuscripciones(true);
                notificar("Solicitud empresarial actualizada.");
            } catch (error) {
                notificar(error.message, "error");
            }
        });
        control.appendChild(boton);
        fila.appendChild(control);
        cuerpo.appendChild(fila);
    });
}

function renderizarSuscripciones(suscripciones) {
    const cuerpo = elemento("tabla-suscripciones");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!suscripciones.length) {
        agregarFilaVacia(
            cuerpo,
            9,
            "No existen suscripciones registradas."
        );
        return;
    }

    suscripciones.forEach((suscripcion) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento("td", suscripcion.id ?? "—")
        );

        fila.appendChild(
            crearElemento("td", suscripcion.empresa_id ?? "—")
        );

        fila.appendChild(
            crearElemento("td", suscripcion.plan_id ?? "—")
        );

        const celdaEstado = crearElemento("td");
        celdaEstado.appendChild(
            crearInsignia(suscripcion.estado)
        );
        fila.appendChild(celdaEstado);

        fila.appendChild(
            crearElemento("td", suscripcion.ciclo || "—")
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(suscripcion.fecha_inicio)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(suscripcion.fecha_fin)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                suscripcion.renovacion_automatica ? "Automática" : "Manual"
            )
        );

        const celdaControl = crearElemento("td");
        const boton = crearElemento("button", "Administrar", "boton boton--secundario boton--pequeno");
        boton.type = "button";
        boton.addEventListener("click", async () => {
            const estadoNuevo = window.prompt(
                "Estado: prueba, activa, vencida, suspendida o cancelada",
                suscripcion.estado,
            );
            if (!estadoNuevo) return;
            const motivo = window.prompt("Motivo obligatorio de la modificación:");
            if (!motivo?.trim()) return;
            try {
                await solicitarJson(`${API.suscripciones}/${suscripcion.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({estado: estadoNuevo.trim(), motivo: motivo.trim()}),
                });
                estado.cargadas.delete("suscripciones");
                await cargarSuscripciones(true);
                notificar("Suscripción actualizada y auditada.");
            } catch (error) {
                notificar(error.message, "error");
            }
        });
        celdaControl.appendChild(boton);
        fila.appendChild(celdaControl);

        cuerpo.appendChild(fila);
    });
}

function mostrarCargaTabla(id, columnas, mensaje) {
    const cuerpo = elemento(id);

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje,
        "estado-carga"
    );

    celda.colSpan = columnas;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

function agregarFilaVacia(cuerpo, columnas, mensaje) {
    const fila = crearElemento("tr");
    const celda = crearElemento(
        "td",
        mensaje,
        "tabla__vacio"
    );

    celda.colSpan = columnas;
    fila.appendChild(celda);
    cuerpo.appendChild(fila);
}

async function cargarPagos(forzar = false) {
    if (estado.cargadas.has("pagos") && !forzar) {
        return;
    }

    mostrarCargaTabla(
        "tabla-pagos",
        6,
        "Cargando pagos…"
    );

    try {
        const datos = await solicitarJson(API.pagos);
        renderizarPagos(datos.pagos || []);
        estado.cargadas.add("pagos");
    } catch (error) {
        renderizarErrorTabla(
            "tabla-pagos",
            6,
            error.message
        );
        notificar(error.message);
    }
}

function renderizarPagos(pagos) {
    const cuerpo = elemento("tabla-pagos");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!pagos.length) {
        agregarFilaVacia(
            cuerpo,
            6,
            "No existen pagos registrados."
        );
        return;
    }

    pagos.forEach((pago) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento("td", pago.id ?? "—")
        );

        fila.appendChild(
            crearElemento("td", pago.empresa_id ?? "—")
        );

        fila.appendChild(
            crearElemento("td", pago.proveedor || "—")
        );

        fila.appendChild(
            crearElemento(
                "td",
                pago.referencia_externa || "—"
            )
        );

        const celdaEstado = crearElemento("td");
        celdaEstado.appendChild(
            crearInsignia(pago.estado)
        );
        fila.appendChild(celdaEstado);

        fila.appendChild(
            crearElemento(
                "td",
                formatearDinero(
                    pago.monto,
                    pago.moneda || "CLP"
                )
            )
        );

        cuerpo.appendChild(fila);
    });
}

async function cargarAuditoria(forzar = false) {
    if (estado.cargadas.has("auditoria") && !forzar) {
        return;
    }

    mostrarCargaTabla(
        "tabla-auditoria",
        6,
        "Cargando auditoría…"
    );

    try {
        const datos = await solicitarJson(
            `${API.auditoria}?limite=200`
        );

        renderizarAuditoria(datos.auditoria || []);
        estado.cargadas.add("auditoria");
    } catch (error) {
        renderizarErrorTabla(
            "tabla-auditoria",
            6,
            error.message
        );
        notificar(error.message);
    }
}

function renderizarAuditoria(registros) {
    const cuerpo = elemento("tabla-auditoria");

    if (!cuerpo) {
        return;
    }

    limpiar(cuerpo);

    if (!registros.length) {
        agregarFilaVacia(
            cuerpo,
            6,
            "No existen eventos de auditoría registrados."
        );
        return;
    }

    registros.forEach((registro) => {
        const fila = crearElemento("tr");

        fila.appendChild(
            crearElemento(
                "td",
                formatearFecha(registro.fecha)
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                registro.accion || "—"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                registro.modulo || "—"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                registro.empresa_id ?? "Global"
            )
        );

        fila.appendChild(
            crearElemento(
                "td",
                registro.usuario_id ?? "Sistema"
            )
        );

        const entidad = registro.entidad_tipo
            ? `${registro.entidad_tipo} #${registro.entidad_id ?? "—"}`
            : "—";

        fila.appendChild(
            crearElemento("td", entidad)
        );

        cuerpo.appendChild(fila);
    });
}

function cargarSeccion(nombre, forzar = false) {
 const cargadores = {
    resumen: cargarResumen,
    empresas: cargarEmpresas,
    planes: cargarPlanes,
    suscripciones: cargarSuscripciones,
    pagos: cargarPagos,
    auditoria: cargarAuditoria,
};

    const cargador = cargadores[nombre];

    if (cargador) {
        cargador(forzar);
    }
}

function registrarEventos() {
    elemento("periodo-analitica")?.addEventListener("change", () => {
        estado.cargadas.delete("resumen");
        cargarResumen(true);
    });

    document.querySelectorAll("[data-seccion]").forEach((boton) => {
        boton.addEventListener("click", () => {
            mostrarSeccion(boton.dataset.seccion);
        });
    });

    document.querySelectorAll("[data-actualizar]").forEach((boton) => {
        boton.addEventListener("click", () => {
            cargarSeccion(boton.dataset.actualizar, true);
        });
    });

    elemento("buscar-empresas")?.addEventListener("click", () => {
    estado.cargadas.delete("empresas");
    cargarEmpresas(true);
});

elemento("filtro-empresa-buscar")?.addEventListener(
    "keydown",
    (evento) => {
        if (evento.key === "Enter") {
            evento.preventDefault();
            estado.cargadas.delete("empresas");
            cargarEmpresas(true);
        }
    }
);

elemento("filtro-empresa-estado")?.addEventListener(
    "change",
    () => {
        estado.cargadas.delete("empresas");
        cargarEmpresas(true);
    }
);

    elemento("abrir-menu")?.addEventListener("click", abrirMenu);
    elemento("cerrar-menu")?.addEventListener("click", cerrarMenu);
    elemento("cerrar-editor-plan")?.addEventListener("click", cerrarEditorPlan);
    elemento("cancelar-editor-plan")?.addEventListener("click", cerrarEditorPlan);
    elemento("formulario-plan")?.addEventListener("submit", guardarPlan);

    elemento("editor-plan")?.addEventListener("click", (evento) => {
        if (evento.target === elemento("editor-plan")) {
            cerrarEditorPlan();
        }
    });

    window.addEventListener("keydown", (evento) => {
        if (evento.key === "Escape") {
            cerrarMenu();
        }
    });
}

document.addEventListener("DOMContentLoaded", () => {
    registrarEventos();
    mostrarSeccion("resumen");
});
