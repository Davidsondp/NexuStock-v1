from app.models import (
    AlertaInventario,
    Bodega,
    Empresa,
    InteraccionIA,
    Inventario,
    Producto,
    Sucursal,
    Usuario,
    Venta,
    db,
    utcnow,
)
from app.services.asistente_ia import ServicioAsistenteIA
from app.services.planes import funciones_plan
from tests.test_autenticacion import REGISTRO


class _RespuestaOpenAI:
    def raise_for_status(self):
        return None

    def json(self):
        import json

        contenido = {
            "resumen": "Prioriza la reposición del producto crítico.",
            "hallazgos": [],
            "acciones": [],
            "preguntas_sugeridas": ["¿Cuánto debería reponer?"],
            "advertencia": "Confirma antes de actuar.",
        }
        return {
            "output": [{"content": [{"type": "output_text", "text": json.dumps(contenido)}]}],
            "usage": {"input_tokens": 120, "output_tokens": 40},
        }


def _preparar(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    with app.app_context():
        usuario = db.session.scalar(db.select(Usuario))
        usuario.empresa.suscripcion_actual.plan.funciones = {
            **usuario.empresa.suscripcion_actual.plan.funciones,
            "ia": True,
        }
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="IA-1",
            nombre="Producto crítico",
            costo_referencia=100,
            precio_venta=200,
            stock_minimo=5,
            punto_reorden=8,
        )
        db.session.add(producto)
        db.session.flush()
        bodega = db.session.scalar(db.select(Bodega))
        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                producto_id=producto.id,
                bodega_id=bodega.id,
                cantidad=2,
                cantidad_reservada=0,
                costo_promedio=100,
            )
        )
        db.session.commit()
        return usuario.id


def test_fallback_ia_es_util_y_no_ejecuta_mutaciones(app, client):
    usuario_id = _preparar(app, client)
    app.config["OPENAI_API_KEY"] = None
    respuesta = client.post(
        "/api/ia/consultar",
        json={"pregunta": "¿Qué compro esta semana?", "modo": "compras"},
    )
    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos["proveedor"] == "local"
    assert datos["respuesta"]["hallazgos"][0]["prioridad"] == "alta"
    assert datos["respuesta"]["acciones"][0]["requiere_confirmacion"]
    with app.app_context():
        assert db.session.scalar(db.select(Inventario.cantidad)) == 2
        assert db.session.scalar(db.select(InteraccionIA.usuario_id)) == usuario_id


def test_historial_y_feedback_son_personales(app, client):
    _preparar(app, client)
    creada = client.post(
        "/api/ia/consultar", json={"pregunta": "Resume mis riesgos", "modo": "riesgos"}
    ).get_json()
    assert client.post(f"/api/ia/{creada['id']}/valorar", json={"valoracion": 1}).status_code == 200
    historial = client.get("/api/ia").get_json()["interacciones"]
    assert len(historial) == 1 and historial[0]["valoracion"] == 1


def test_ia_solo_en_ultra_profesional_y_empresarial():
    assert funciones_plan("avanzado")["ia"] is False
    assert funciones_plan("ultra")["ia"] is True
    assert funciones_plan("profesional")["ia"] is True
    assert funciones_plan("empresa")["ia"] is True


def test_contexto_ia_respeta_sucursales_y_bodegas_autorizadas(
    app,
    client,
):
    usuario_id = _preparar(app, client)

    with app.app_context():
        usuario = db.session.get(Usuario, usuario_id)

        sucursal = Sucursal(
            empresa_id=usuario.empresa_id,
            codigo="NO-AUTORIZADA",
            nombre="Sucursal no autorizada",
        )
        db.session.add(sucursal)
        db.session.flush()

        bodega = Bodega(
            empresa_id=usuario.empresa_id,
            sucursal_id=sucursal.id,
            codigo="BOD-SECRETA",
            nombre="Bodega secreta",
        )
        producto = Producto(
            empresa_id=usuario.empresa_id,
            codigo="SECRETO-SUCURSAL",
            nombre="Producto secreto de otra sucursal",
            costo_referencia=100,
            precio_venta=200,
            stock_minimo=5,
            punto_reorden=8,
        )
        db.session.add_all([bodega, producto])
        db.session.flush()

        db.session.add(
            Inventario(
                empresa_id=usuario.empresa_id,
                producto_id=producto.id,
                bodega_id=bodega.id,
                cantidad=99,
                cantidad_reservada=0,
                costo_promedio=100,
            )
        )
        db.session.add(
            Venta(
                empresa_id=usuario.empresa_id,
                bodega_id=bodega.id,
                creada_por_id=usuario.id,
                numero="VENTA-SECRETA-IA",
                estado="confirmada",
                subtotal=999,
                total=999,
                confirmada_en=utcnow(),
            )
        )
        db.session.add(
            AlertaInventario(
                empresa_id=usuario.empresa_id,
                producto_id=producto.id,
                bodega_id=bodega.id,
                tipo="stock_bajo",
                estado="activa",
                prioridad="alta",
                titulo="ALERTA-SECRETA-IA",
                mensaje="No debe enviarse a este usuario.",
                datos={"marcador": "SECRETO-ALERTA"},
            )
        )
        db.session.commit()

        contexto = ServicioAsistenteIA(usuario)._contexto()
        serializado = str(contexto)

        assert "SECRETO-SUCURSAL" not in serializado
        assert "ALERTA-SECRETA-IA" not in serializado
        assert contexto["resumen"]["ventas_30_dias"] == 0
        assert contexto["resumen"]["alertas_activas"] == 0


def test_contexto_enviado_depende_del_modo():
    contexto = {
        "fecha_utc": "2026-08-25T00:00:00",
        "moneda": "CLP",
        "resumen": {},
        "productos_prioritarios": [],
        "productos_mas_vendidos": [],
        "alertas": [],
    }

    ventas = ServicioAsistenteIA._contexto_para_modo(
        "ventas",
        contexto,
    )
    riesgos = ServicioAsistenteIA._contexto_para_modo(
        "riesgos",
        contexto,
    )

    assert "productos_mas_vendidos" in ventas
    assert "productos_prioritarios" not in ventas
    assert "alertas" not in ventas

    assert "productos_prioritarios" in riesgos
    assert "alertas" in riesgos
    assert "productos_mas_vendidos" not in riesgos


def test_contexto_ia_no_incluye_empresa_ajena(app, client):
    usuario_id = _preparar(app, client)
    with app.app_context():
        actor = db.session.get(Usuario, usuario_id)
        ajena = Empresa(nombre="Ajena", email="ia-ajena@nexustock.cl")
        db.session.add(ajena)
        db.session.flush()
        db.session.add(
            Producto(
                empresa_id=ajena.id,
                codigo="SECRETO",
                nombre="No debe aparecer",
                costo_referencia=1,
                precio_venta=2,
            )
        )
        db.session.commit()
        contexto = ServicioAsistenteIA(actor)._contexto()
        assert "SECRETO" not in str(contexto)


def test_plan_sin_ia_bloquea_panel_y_api(app, client):
    client.post("/autenticacion/registro", data=REGISTRO)
    assert client.get("/panel/asistente").status_code == 403
    assert client.post("/api/ia/consultar", json={"pregunta": "Ayúdame"}).status_code == 403


def test_openai_usa_responses_con_esquema_y_sin_retencion(app, client, monkeypatch):
    _preparar(app, client)
    app.config["OPENAI_API_KEY"] = "clave-de-prueba"
    capturada = {}

    def post(url, **kwargs):
        capturada.update(url=url, **kwargs)
        return _RespuestaOpenAI()

    monkeypatch.setattr("app.services.asistente_ia.requests.post", post)
    respuesta = client.post("/api/ia/consultar", json={"pregunta": "¿Qué debo priorizar?"})

    assert respuesta.status_code == 201
    assert respuesta.get_json()["proveedor"] == "openai"
    assert capturada["url"] == "https://api.openai.com/v1/responses"
    assert capturada["json"]["store"] is False
    assert capturada["json"]["text"]["format"]["strict"] is True
    assert "clave-de-prueba" not in str(capturada["json"])


def test_limite_diario_evitar_costos_descontrolados(app, client):
    _preparar(app, client)
    app.config["IA_LIMITE_DIARIO_EMPRESA"] = 1
    assert (
        client.post("/api/ia/consultar", json={"pregunta": "Primera consulta"}).status_code == 201
    )

    bloqueada = client.post("/api/ia/consultar", json={"pregunta": "Segunda consulta"})
    assert bloqueada.status_code == 400
    assert bloqueada.get_json()["codigo"] == "limite_ia"
