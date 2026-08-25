from pathlib import Path
import re

import pytest

from app.commands import PLANES
from app.extensions import correo
from app.models import PlanSaaS, db


@pytest.fixture(autouse=True)
def sembrar_planes_comerciales(app):
    with app.app_context():
        db.session.add_all(PlanSaaS(**datos) for datos in PLANES if datos["codigo"] != "prueba")
        db.session.commit()


def test_planes_publicos_no_requieren_sesion(
    client,
):
    respuesta = client.get("/planes")

    assert respuesta.status_code == 200


def test_planes_publicos_exponen_contrato_visual(
    client,
):
    respuesta = client.get("/planes")

    assert respuesta.status_code == 200

    contratos = (
        b'id="portada-planes"',
        b'id="selector-ciclo-publico"',
        b'id="selector-proveedor-publico"',
        b'id="planes-comerciales"',
        b'id="comparacion-publica"',
        b'id="demostracion-producto"',
        b'id="preguntas-planes"',
        b'id="cta-final-planes"',
        b'id="cta-movil-planes"',
        b'data-registro-base="/autenticacion/registro"',
        b"css/planes_publicos.css",
        b"js/planes_publicos.js",
    )

    for contrato in contratos:
        assert contrato in respuesta.data

    textos = (
        "Controla tu inventario",
        "Haz crecer tu negocio",
        "Elige el plan que acompa\u00f1a tu operaci\u00f3n",
        "30 d\u00edas gratis",
        "Capacidades que crecen contigo",
        "Inteligencia artificial",
        "Disponible",
        "Preguntas frecuentes",
    )

    for texto in textos:
        assert texto.encode("utf-8") in respuesta.data


def test_planes_publicos_incluyen_conversion_transparente(
    client,
):
    respuesta = client.get("/planes")

    contratos = (
        b'data-plan="basico"',
        b'data-plan="profesional"',
        b'data-plan="empresa"',
        b'data-ciclo="mensual"',
        b'data-ciclo="anual"',
        b'class="plan-publico__recomendado"',
        "M\u00e1s elegido".encode("utf-8"),
        b"Comparar capacidades",
        b"Probar Avanzado 30 d\xc3\xadas",
        b"Solicitar contrato",
    )

    for contrato in contratos:
        if contrato == b'data-plan="basico"':
            assert contrato not in respuesta.data
        else:
            assert contrato in respuesta.data

    assert len(re.findall(rb'<article\s+class="plan-publico', respuesta.data)) == 4


def test_prueba_gratuita_es_un_beneficio_de_cada_plan(client):
    respuesta = client.get("/planes")
    assert b'data-plan-prueba="true"' not in respuesta.data
    assert b"30 d\xc3\xadas" in respuesta.data
    assert b"Tarjeta requerida y renovaci\xc3\xb3n autom\xc3\xa1tica" in respuesta.data
    assert b' data-cotizacion="true"' in respuesta.data
    assert b'data-plan="prueba"' not in respuesta.data
    assert b"$0 al a\xc3\xb1o" not in respuesta.data


def test_portada_usa_precios_reales_y_refleja_edicion(app, client):
    respuesta = client.get("/planes")
    assert b'data-precio-mensual="19990.00"' in respuesta.data
    assert "$19.990".encode() in respuesta.data
    assert b'data-precio-mensual="49990.00"' in respuesta.data
    assert b"Empresarial" in respuesta.data
    assert b'data-plan="corporativo"' not in respuesta.data

    with app.app_context():
        profesional = db.session.scalar(db.select(PlanSaaS).where(PlanSaaS.codigo == "profesional"))
        profesional.precio_mensual = 24990
        profesional.precio_anual = 249900
        db.session.commit()

    actualizada = client.get("/")
    assert b'data-precio-mensual="24990.00"' in actualizada.data
    assert "$24.990".encode() in actualizada.data


def test_plan_publicado_es_aceptado_por_el_registro(client):
    respuesta = client.get(
        "/autenticacion/registro?plan=profesional&ciclo=mensual&proveedor=webpay"
    )
    assert respuesta.status_code == 200
    assert "Profesional".encode() in respuesta.data
    with client.session_transaction() as sesion:
        assert sesion["registro_plan_seleccionado"] == "profesional"
        assert sesion["registro_ciclo_seleccionado"] == "mensual"
        assert sesion["registro_proveedor_seleccionado"] == "webpay"


def test_planes_publicos_enlazan_autenticacion(
    client,
):
    respuesta = client.get("/planes")

    assert b"/autenticacion/ingresar" in respuesta.data
    assert b"/autenticacion/registro" in respuesta.data


def test_empresarial_usa_flujo_contractual_y_registra_solicitud(app, client):
    portada = client.get("/planes")
    assert b"/empresarial/solicitar" in portada.data

    formulario = client.get("/empresarial/solicitar")
    assert formulario.status_code == 200
    assert b"Sin cobros autom" in formulario.data

    respuesta = client.post(
        "/empresarial/solicitar",
        data={
            "empresa_nombre": "Empresa Nacional",
            "contacto_nombre": "Ana Responsable",
            "email": "ana@empresa.cl",
            "telefono": "+56912345678",
            "productos_estimados": "25000",
            "usuarios_estimados": "30",
            "mensaje": "Necesitamos tres centros de distribución.",
        },
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    assert len(respuesta.history) == 1
    assert respuesta.history[0].status_code == 302
    assert "Solicitud recibida".encode() in respuesta.data

    from app.models import SolicitudContratoEmpresarial

    with app.app_context():
        solicitud = db.session.scalar(db.select(SolicitudContratoEmpresarial))
        assert solicitud.empresa_nombre == "Empresa Nacional"
        assert solicitud.productos_estimados == 25000
        assert solicitud.estado == "nueva"


def test_solicitud_empresarial_notifica_a_comercial_y_contacto(
    app,
    client,
):
    app.config["COMERCIAL_EMAIL"] = "comercial@nexustock.cl"

    with correo.record_messages() as enviados:
        respuesta = client.post(
            "/empresarial/solicitar",
            data={
                "empresa_nombre": "Empresa Nacional",
                "contacto_nombre": "Ana Responsable",
                "email": "ana@empresa.cl",
                "telefono": "+56912345678",
                "productos_estimados": "25000",
                "usuarios_estimados": "30",
                "mensaje": "Necesitamos una propuesta empresarial.",
            },
            follow_redirects=True,
        )

    assert respuesta.status_code == 200
    assert len(enviados) == 2

    destinatarios = {mensaje.recipients[0] for mensaje in enviados}

    assert destinatarios == {
        "comercial@nexustock.cl",
        "ana@empresa.cl",
    }

    aviso = next(
        mensaje for mensaje in enviados if mensaje.recipients == ["comercial@nexustock.cl"]
    )

    assert aviso.reply_to == "ana@empresa.cl"
    assert "Empresa Nacional" in aviso.body

    confirmacion = next(mensaje for mensaje in enviados if mensaje.recipients == ["ana@empresa.cl"])

    assert "revisar\u00e1" in confirmacion.body
    assert "se comunicar\u00e1" in confirmacion.body
    assert "N\u00famero de solicitud" in confirmacion.body
    assert "autom\u00e1tica" in confirmacion.body
    assert "per\u00edodo de evaluaci\u00f3n" in confirmacion.body
    assert "?" not in confirmacion.body


def test_solicitud_empresarial_se_conserva_si_falla_el_correo(
    app,
    client,
    monkeypatch,
):
    def fallar(*args, **kwargs):
        raise OSError("SMTP no disponible")

    monkeypatch.setattr(
        "app.services.contratos_empresariales.correo.send",
        fallar,
    )

    respuesta = client.post(
        "/empresarial/solicitar",
        data={
            "empresa_nombre": "Empresa Resiliente",
            "contacto_nombre": "Contacto Responsable",
            "email": "contacto@resiliente.cl",
            "telefono": "+56911112222",
            "productos_estimados": "15000",
            "usuarios_estimados": "20",
            "mensaje": "Necesitamos evaluar el plan Empresarial.",
        },
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert len(respuesta.history) == 1
    assert respuesta.history[0].status_code == 302
    assert "Solicitud recibida".encode() in respuesta.data

    from app.models import SolicitudContratoEmpresarial

    with app.app_context():
        solicitud = db.session.scalar(
            db.select(SolicitudContratoEmpresarial).where(
                SolicitudContratoEmpresarial.email == "contacto@resiliente.cl"
            )
        )

        assert solicitud is not None
        assert solicitud.estado == "nueva"


def test_javascript_planes_publicos_conserva_eleccion():
    contenido = Path("app/static/js/planes_publicos.js").read_text(encoding="utf-8-sig")

    contratos = (
        "registroBase",
        "selector-ciclo-publico",
        "data-plan",
        "plan",
        "ciclo",
        "proveedor",
        "URLSearchParams",
        "planes-comerciales",
        "comparacion-publica",
        "cta-movil-planes",
        "IntersectionObserver",
    )

    for contrato in contratos:
        assert contrato in contenido


def test_css_planes_publicos_es_responsive():
    contenido = Path("app/static/css/planes_publicos.css").read_text(encoding="utf-8-sig")

    contratos = (
        ".pagina-planes",
        ".portada-planes",
        ".plan-publico",
        ".plan-publico--destacado",
        ".comparacion-publica",
        ".cta-movil-planes",
        "@media",
        "prefers-reduced-motion",
    )

    for contrato in contratos:
        assert contrato in contenido


def test_planes_publicos_declaran_etiquetas_qr_ilimitadas():
    from pathlib import Path

    plantilla = Path("app/templates/planes_publicos.html").read_text(encoding="utf-8-sig")

    assert "Creación ilimitada de códigos QR " "y etiquetas de códigos de barras" in plantilla
    assert "Productos sin límite" not in plantilla


def test_terminologia_comercial_de_articulos_unicos():
    from pathlib import Path

    plantilla = Path("app/templates/planes_publicos.html").read_text(encoding="utf-8-sig")
    planes_js = Path("app/static/js/planes.js").read_text(encoding="utf-8-sig")
    super_js = Path("app/static/js/panel_superadministracion.js").read_text(encoding="utf-8-sig")
    panel_super = Path("app/templates/superadministracion/panel.html").read_text(
        encoding="utf-8-sig"
    )

    assert "artículos únicos</li>" in plantilla
    assert "¿Qué es un artículo único?" in plantilla
    assert (
        "La cantidad física disponible y su "
        "distribución entre bodegas no aumentan "
        "el límite." in plantilla
    )
    assert "Artículos únicos" in planes_js
    assert "artículos únicos`" in planes_js
    assert "Productos según contrato" not in planes_js
    assert "Artículos únicos" in super_js
    assert "Límite de artículos únicos" in panel_super
