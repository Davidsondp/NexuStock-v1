"""Capacidades comerciales prioritarias con aislamiento por empresa."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import time
import requests

from sqlalchemy.exc import IntegrityError

from ..models import (
    AccesoEmpresaUsuario,
    Caja,
    Cliente,
    DocumentoTributario,
    Empresa,
    EventoIntegracion,
    GrupoEmpresa,
    IntegracionEmpresa,
    Inventario,
    MembresiaGrupoEmpresa,
    OrdenWMS,
    PagoVenta,
    Producto,
    TurnoCaja,
    Venta,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .ventas import ServicioVentas


class ErrorSuiteComercial(ValueError):
    codigo = "operacion_comercial_invalida"


class ClienteDTEHttp:
    """Adaptador neutro para un proveedor de DTE certificado por el SII."""

    def __init__(self, base_url, api_key, timeout=(5, 25)):
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.timeout = timeout
        if not self.base_url.startswith("https://") or not self.api_key:
            raise ErrorSuiteComercial("Proveedor tributario no configurado")

    def emitir(self, datos, clave_idempotencia):
        try:
            respuesta = requests.post(
                f"{self.base_url}/documentos",
                json=datos,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": clave_idempotencia,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            respuesta.raise_for_status()
            contenido = respuesta.json()
        except (requests.RequestException, ValueError) as exc:
            raise ErrorSuiteComercial("Proveedor tributario no disponible") from exc
        if (
            not isinstance(contenido, dict)
            or not contenido.get("folio")
            or not contenido.get("referencia")
        ):
            raise ErrorSuiteComercial("Respuesta tributaria inválida")
        return contenido


def _decimal(valor, nombre="monto"):
    try:
        resultado = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ErrorSuiteComercial(f"El {nombre} no es válido") from exc
    if resultado < 0:
        raise ErrorSuiteComercial(f"El {nombre} no puede ser negativo")
    return resultado


class _ServicioEmpresa:
    permiso = "dashboard.ver"

    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def exigir(self, permiso=None):
        decision = evaluar_permiso(
            self.usuario, permiso or self.permiso, empresa_id=self.usuario.empresa_id
        )
        if not decision.permitido:
            raise PermissionError(decision.mensaje)

    def auditar(self, accion, entidad, entidad_id, datos=None):
        registrar_auditoria(
            accion=accion,
            modulo="suite_comercial",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo=entidad,
            entidad_id=entidad_id,
            datos_nuevos=datos,
        )


class ServicioGrupoEmpresarial(_ServicioEmpresa):
    permiso = "multiempresa.ver"

    def resumen(self):
        self.exigir()
        membresia = db.session.scalar(
            db.select(MembresiaGrupoEmpresa).where(
                MembresiaGrupoEmpresa.empresa_id == self.usuario.empresa_id
            )
        )
        if not membresia:
            return {"grupo": None, "empresas": [], "totales": {"stock": "0.000", "valor": "0.00"}}
        acceso_ids = set(
            db.session.scalars(
                db.select(AccesoEmpresaUsuario.empresa_id).where(
                    AccesoEmpresaUsuario.usuario_id == self.usuario.id,
                    AccesoEmpresaUsuario.activo.is_(True),
                )
            )
        ) | {self.usuario.empresa_id}
        empresas_ids = (
            set(
                db.session.scalars(
                    db.select(MembresiaGrupoEmpresa.empresa_id).where(
                        MembresiaGrupoEmpresa.grupo_id == membresia.grupo_id
                    )
                )
            )
            & acceso_ids
        )
        empresas = list(db.session.scalars(db.select(Empresa).where(Empresa.id.in_(empresas_ids))))
        filas = []
        stock_total = Decimal("0")
        valor_total = Decimal("0")
        for empresa in empresas:
            stock, valor = db.session.execute(
                db.select(
                    db.func.coalesce(db.func.sum(Inventario.cantidad), 0),
                    db.func.coalesce(
                        db.func.sum(Inventario.cantidad * Inventario.costo_promedio), 0
                    ),
                ).where(Inventario.empresa_id == empresa.id)
            ).one()
            stock, valor = Decimal(stock), Decimal(valor)
            stock_total += stock
            valor_total += valor
            filas.append(
                {
                    "id": empresa.id,
                    "nombre": empresa.nombre,
                    "stock": str(stock),
                    "valor": str(valor),
                }
            )
        grupo = db.session.get(GrupoEmpresa, membresia.grupo_id)
        return {
            "grupo": {"id": grupo.id, "nombre": grupo.nombre, "moneda": grupo.moneda_consolidacion},
            "empresas": filas,
            "totales": {"stock": str(stock_total), "valor": str(valor_total)},
        }


class ServicioPOS(_ServicioEmpresa):
    permiso = "pos.operar"

    def abrir(self, caja_id, monto_apertura):
        self.exigir()
        caja = db.session.scalar(
            db.select(Caja)
            .where(
                Caja.id == caja_id,
                Caja.empresa_id == self.usuario.empresa_id,
                Caja.activa.is_(True),
            )
            .with_for_update()
        )
        if not caja:
            raise PermissionError("Caja no autorizada")
        turno = TurnoCaja(
            empresa_id=self.usuario.empresa_id,
            caja_id=caja.id,
            usuario_apertura_id=self.usuario.id,
            monto_apertura=_decimal(monto_apertura, "monto de apertura"),
        )
        try:
            db.session.add(turno)
            db.session.flush()
            self.auditar("pos.turno_abierto", "TurnoCaja", turno.id)
            db.session.commit()
            return turno
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorSuiteComercial("La caja ya tiene un turno abierto") from exc

    def vender(
        self, turno_id, *, numero, bodega_id, items, pagos, clave_idempotencia, cliente_id=None
    ):
        self.exigir()
        clave_idempotencia = str(clave_idempotencia or "").strip()
        if not clave_idempotencia or len(clave_idempotencia) > 90:
            raise ErrorSuiteComercial("Idempotency-Key es obligatorio y debe ser válido")
        turno = db.session.scalar(
            db.select(TurnoCaja).where(
                TurnoCaja.id == turno_id,
                TurnoCaja.empresa_id == self.usuario.empresa_id,
                TurnoCaja.estado == "abierto",
            )
        )
        if not turno:
            raise ErrorSuiteComercial("No existe un turno abierto autorizado")
        existente = db.session.scalar(
            db.select(PagoVenta).where(
                PagoVenta.empresa_id == self.usuario.empresa_id,
                PagoVenta.clave_idempotencia == clave_idempotencia,
            )
        )
        if existente:
            return db.session.get(Venta, existente.venta_id), False
        if not isinstance(pagos, list) or not pagos:
            raise ErrorSuiteComercial("Debes registrar al menos un pago")
        for pago in pagos:
            if str(pago.get("metodo") or "").lower() not in {
                "efectivo",
                "debito",
                "credito",
                "transferencia",
                "qr",
                "otro",
            }:
                raise ErrorSuiteComercial("Método de pago no admitido")
        # Venta, reserva, salida, pagos y auditoría quedan en una transacción.
        servicio = ServicioVentas(self.usuario)
        venta = servicio.crear(
            numero=numero,
            bodega_id=bodega_id,
            items=items,
            cliente_id=cliente_id,
            confirmar_transaccion=False,
        )
        total_pagado = sum((_decimal(p.get("monto")) for p in pagos), Decimal("0"))
        if total_pagado != Decimal(venta.total):
            db.session.rollback()
            raise ErrorSuiteComercial("Los pagos deben coincidir exactamente con el total")
        servicio.reservar(venta.id, confirmar_transaccion=False)
        servicio.confirmar(venta.id, confirmar_transaccion=False)
        try:
            for indice, pago in enumerate(pagos):
                metodo = str(pago.get("metodo") or "").lower()
                db.session.add(
                    PagoVenta(
                        empresa_id=self.usuario.empresa_id,
                        venta_id=venta.id,
                        turno_id=turno.id,
                        metodo=metodo,
                        monto=_decimal(pago.get("monto")),
                        referencia=str(pago.get("referencia") or "")[:150] or None,
                        clave_idempotencia=(
                            clave_idempotencia if indice == 0 else f"{clave_idempotencia}:{indice}"
                        ),
                    )
                )
            self.auditar("pos.venta_confirmada", "Venta", venta.id, {"turno_id": turno.id})
            db.session.commit()
            return venta, True
        except IntegrityError:
            db.session.rollback()
            existente = db.session.scalar(
                db.select(PagoVenta).where(
                    PagoVenta.empresa_id == self.usuario.empresa_id,
                    PagoVenta.clave_idempotencia == clave_idempotencia,
                )
            )
            if existente:
                return db.session.get(Venta, existente.venta_id), False
            raise
        except Exception:
            db.session.rollback()
            raise

    def cerrar(self, turno_id, monto_declarado):
        self.exigir()
        turno = db.session.scalar(
            db.select(TurnoCaja)
            .where(TurnoCaja.id == turno_id, TurnoCaja.empresa_id == self.usuario.empresa_id)
            .with_for_update()
        )
        if not turno or turno.estado != "abierto":
            raise ErrorSuiteComercial("El turno no está abierto")
        efectivo = db.session.scalar(
            db.select(db.func.coalesce(db.func.sum(PagoVenta.monto), 0)).where(
                PagoVenta.turno_id == turno.id, PagoVenta.metodo == "efectivo"
            )
        )
        calculado = Decimal(turno.monto_apertura) + Decimal(efectivo)
        declarado = _decimal(monto_declarado, "monto declarado")
        turno.estado = "cerrado"
        turno.usuario_cierre_id = self.usuario.id
        turno.monto_cierre_declarado = declarado
        turno.monto_cierre_calculado = calculado
        turno.diferencia = declarado - calculado
        turno.cerrado_en = utcnow()
        self.auditar(
            "pos.turno_cerrado", "TurnoCaja", turno.id, {"diferencia": str(turno.diferencia)}
        )
        db.session.commit()
        return turno


class ServicioWMS(_ServicioEmpresa):
    permiso = "wms.operar"
    TRANSICIONES = {
        "pendiente": "picking",
        "picking": "pickeada",
        "pickeada": "packing",
        "packing": "empacada",
        "empacada": "despachada",
    }

    @staticmethod
    def _cantidades_completas(orden, clave):
        requeridos = orden.progreso.get("requeridos", {})
        registrados = orden.progreso.get(clave, {})
        return set(requeridos) == set(registrados) and all(
            Decimal(requeridos[item]) == Decimal(registrados[item]) for item in requeridos
        )

    def crear(self, venta_id, numero, asignada_a_id=None):
        self.exigir()
        venta = db.session.scalar(
            db.select(Venta).where(
                Venta.id == venta_id, Venta.empresa_id == self.usuario.empresa_id
            )
        )
        if not venta or venta.estado != "reservada":
            raise ErrorSuiteComercial("La venta debe estar reservada")
        requeridos = {str(item.producto_id): str(item.cantidad) for item in venta.items}
        orden = OrdenWMS(
            empresa_id=self.usuario.empresa_id,
            venta_id=venta.id,
            bodega_id=venta.bodega_id,
            numero=str(numero).strip().upper(),
            asignada_a_id=asignada_a_id,
            progreso={"requeridos": requeridos, "pickeados": {}, "empacados": {}},
        )
        try:
            db.session.add(orden)
            db.session.flush()
            self.auditar("wms.orden_creada", "OrdenWMS", orden.id)
            db.session.commit()
            return orden
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorSuiteComercial("La venta ya posee una orden WMS") from exc

    def avanzar(self, orden_id, *, transportista=None, seguimiento=None):
        self.exigir()
        orden = db.session.scalar(
            db.select(OrdenWMS)
            .where(OrdenWMS.id == orden_id, OrdenWMS.empresa_id == self.usuario.empresa_id)
            .with_for_update()
        )
        if not orden or orden.estado not in self.TRANSICIONES:
            raise ErrorSuiteComercial("La orden no admite esa transición")
        nuevo = self.TRANSICIONES[orden.estado]
        if nuevo == "pickeada" and not self._cantidades_completas(orden, "pickeados"):
            raise ErrorSuiteComercial(
                "Debes escanear exactamente todos los productos antes de cerrar picking"
            )
        if nuevo == "empacada" and not self._cantidades_completas(orden, "empacados"):
            raise ErrorSuiteComercial(
                "Debes verificar exactamente todos los productos antes de cerrar packing"
            )
        if nuevo == "pickeada":
            orden.pickeada_en = utcnow()
        if nuevo == "empacada":
            orden.empacada_en = utcnow()
        if nuevo == "despachada":
            if not transportista or not seguimiento:
                raise ErrorSuiteComercial("Transportista y seguimiento son obligatorios")
            ServicioVentas(self.usuario).confirmar(orden.venta_id, confirmar_transaccion=False)
            orden.transportista, orden.seguimiento, orden.despachada_en = (
                str(transportista)[:100],
                str(seguimiento)[:150],
                utcnow(),
            )
        orden.estado = nuevo
        self.auditar(f"wms.{nuevo}", "OrdenWMS", orden.id)
        db.session.commit()
        return orden

    def escanear(self, orden_id, *, etapa, codigo_producto, cantidad):
        self.exigir()
        if etapa not in {"picking", "packing"}:
            raise ErrorSuiteComercial("Etapa de escaneo inválida")
        orden = db.session.scalar(
            db.select(OrdenWMS)
            .where(OrdenWMS.id == orden_id, OrdenWMS.empresa_id == self.usuario.empresa_id)
            .with_for_update()
        )
        estado_requerido = "picking" if etapa == "picking" else "packing"
        if not orden or orden.estado != estado_requerido:
            raise ErrorSuiteComercial("La orden no está en la etapa indicada")
        producto = db.session.scalar(
            db.select(Producto).where(
                Producto.empresa_id == self.usuario.empresa_id,
                Producto.codigo == str(codigo_producto or "").strip().upper(),
            )
        )
        if not producto or str(producto.id) not in orden.progreso.get("requeridos", {}):
            raise ErrorSuiteComercial("Producto no requerido por la orden")
        cantidad = _decimal(cantidad, "cantidad")
        if cantidad <= 0:
            raise ErrorSuiteComercial("Cantidad de escaneo inválida")
        clave = "pickeados" if etapa == "picking" else "empacados"
        progreso = dict(orden.progreso or {})
        acumulados = dict(progreso.get(clave, {}))
        acumulado = Decimal(acumulados.get(str(producto.id), "0")) + cantidad
        requerido = Decimal(progreso["requeridos"][str(producto.id)])
        if acumulado > requerido:
            raise ErrorSuiteComercial("La cantidad escaneada excede la requerida")
        acumulados[str(producto.id)] = str(acumulado)
        progreso[clave] = acumulados
        orden.progreso = progreso
        self.auditar(
            f"wms.{etapa}_escaneado",
            "OrdenWMS",
            orden.id,
            {"producto_id": producto.id, "cantidad": str(cantidad)},
        )
        db.session.commit()
        return orden


class ServicioDTE(_ServicioEmpresa):
    permiso = "dte.emitir"

    def emitir(
        self, venta_id, *, tipo, proveedor, clave_idempotencia, cliente, documento_referencia=None
    ):
        self.exigir()
        tipo = str(tipo or "").strip().lower()
        clave_idempotencia = str(clave_idempotencia or "").strip()
        if tipo not in {
            "boleta",
            "factura",
            "factura_exenta",
            "nota_credito",
            "nota_debito",
            "guia_despacho",
        }:
            raise ErrorSuiteComercial("Tipo de documento tributario no admitido")
        if not clave_idempotencia or len(clave_idempotencia) > 100:
            raise ErrorSuiteComercial("Idempotency-Key es obligatorio")
        existente = db.session.scalar(
            db.select(DocumentoTributario).where(
                DocumentoTributario.empresa_id == self.usuario.empresa_id,
                DocumentoTributario.clave_idempotencia == clave_idempotencia,
            )
        )
        if existente:
            return existente, False
        venta = db.session.scalar(
            db.select(Venta).where(
                Venta.id == venta_id,
                Venta.empresa_id == self.usuario.empresa_id,
                Venta.estado == "confirmada",
            )
        )
        if not venta:
            raise ErrorSuiteComercial("La venta debe estar confirmada")
        empresa = db.session.get(Empresa, self.usuario.empresa_id)
        receptor = db.session.get(Cliente, venta.cliente_id) if venta.cliente_id else None
        if tipo in {"factura", "factura_exenta", "nota_credito", "nota_debito"}:
            if not receptor or not receptor.identificacion_fiscal or not receptor.direccion:
                raise ErrorSuiteComercial("El receptor debe tener RUT y dirección para este DTE")
        referencia = None
        if tipo in {"nota_credito", "nota_debito"}:
            referencia = db.session.scalar(
                db.select(DocumentoTributario).where(
                    DocumentoTributario.id == documento_referencia,
                    DocumentoTributario.empresa_id == self.usuario.empresa_id,
                    DocumentoTributario.estado == "aceptado",
                )
            )
            if not referencia:
                raise ErrorSuiteComercial("La nota requiere un DTE original aceptado")
        detalles = []
        for item in venta.items:
            producto = db.session.get(Producto, item.producto_id)
            detalles.append(
                {
                    "codigo": producto.codigo,
                    "nombre": producto.nombre,
                    "cantidad": str(item.cantidad),
                    "precio_unitario": str(item.precio_unitario),
                    "descuento": str(item.descuento),
                    "impuesto": str(item.impuesto),
                    "total": str(item.total),
                }
            )
        neto = Decimal(venta.subtotal) - Decimal(venta.descuento)
        payload = {
            "venta_id": venta.id,
            "tipo": tipo,
            "moneda": venta.moneda,
            "emisor": {
                "rut": empresa.identificacion_fiscal,
                "razon_social": empresa.nombre,
                "direccion": empresa.direccion,
                "comuna": empresa.ciudad,
            },
            "receptor": (
                {
                    "rut": receptor.identificacion_fiscal,
                    "razon_social": receptor.nombre,
                    "direccion": receptor.direccion,
                }
                if receptor
                else None
            ),
            "totales": {
                "neto": str(neto),
                "iva": str(venta.impuesto),
                "exento": str(neto if tipo == "factura_exenta" else 0),
                "total": str(venta.total),
            },
            "items": detalles,
            "referencia": (
                {
                    "tipo": referencia.tipo,
                    "folio": referencia.folio,
                    "track_id": referencia.referencia_proveedor,
                }
                if referencia
                else None
            ),
        }
        if not empresa.identificacion_fiscal or not empresa.direccion or not empresa.ciudad:
            raise ErrorSuiteComercial("Completa RUT, dirección y comuna del emisor antes de emitir")
        # No se mantiene una transacción de escritura abierta durante la red externa.
        db.session.rollback()
        try:
            respuesta = cliente.emitir(payload, clave_idempotencia)
            existente = db.session.scalar(
                db.select(DocumentoTributario).where(
                    DocumentoTributario.empresa_id == self.usuario.empresa_id,
                    DocumentoTributario.clave_idempotencia == clave_idempotencia,
                )
            )
            if existente:
                return existente, False
            documento = DocumentoTributario(
                empresa_id=self.usuario.empresa_id,
                venta_id=venta_id,
                tipo=tipo,
                proveedor=proveedor,
                clave_idempotencia=clave_idempotencia,
                monto_total=payload["totales"]["total"],
                estado="enviando",
            )
            db.session.add(documento)
            db.session.flush()
            documento.folio = int(respuesta["folio"])
            documento.referencia_proveedor = str(respuesta["referencia"])
            documento.estado = "aceptado" if respuesta.get("estado") == "aceptado" else "enviando"
            documento.datos_proveedor = {
                k: v for k, v in respuesta.items() if k not in {"xml", "pdf"}
            }
            documento.emitido_en = utcnow() if documento.estado == "aceptado" else None
            self.auditar(
                "dte.emitido", "DocumentoTributario", documento.id, {"estado": documento.estado}
            )
            db.session.commit()
            return documento, True
        except Exception as exc:
            db.session.rollback()
            raise ErrorSuiteComercial("El proveedor tributario no confirmó la emisión") from exc


class ServicioIntegraciones(_ServicioEmpresa):
    permiso = "integraciones.gestionar"

    def crear(self, proveedor, secreto):
        self.exigir()
        proveedor = str(proveedor or "").strip().lower()
        if proveedor not in {
            "shopify",
            "woocommerce",
            "mercadolibre",
            "quickbooks",
            "slack",
            "microsoft_teams",
            "contabilidad",
            "otro",
        }:
            raise ErrorSuiteComercial("Proveedor de integración no admitido")
        if len(str(secreto or "")) < 24:
            raise ErrorSuiteComercial("El secreto debe tener al menos 24 caracteres")
        integracion = IntegracionEmpresa(
            empresa_id=self.usuario.empresa_id,
            proveedor=proveedor,
            secreto_webhook_hash=hashlib.sha256(str(secreto).encode()).hexdigest(),
        )
        try:
            db.session.add(integracion)
            db.session.flush()
            self.auditar("integracion.creada", "IntegracionEmpresa", integracion.id)
            db.session.commit()
            return integracion
        except IntegrityError as exc:
            db.session.rollback()
            raise ErrorSuiteComercial("La integración ya existe") from exc

    @staticmethod
    def firmar_webhook(secreto, marca_tiempo, cuerpo):
        """Firma estable: HMAC-SHA256(SHA256(secreto), timestamp + '.' + body)."""
        clave = hashlib.sha256(str(secreto).encode()).digest()
        mensaje = str(marca_tiempo).encode() + b"." + bytes(cuerpo)
        return hmac.new(clave, mensaje, hashlib.sha256).hexdigest()

    @staticmethod
    def _payload_seguro(payload):
        if not isinstance(payload, dict):
            raise ErrorSuiteComercial("El payload debe ser un objeto JSON")
        sensibles = {
            "password",
            "secret",
            "token",
            "authorization",
            "card",
            "cvv",
            "email",
            "phone",
            "address",
        }

        def limpiar(valor, profundidad=0):
            if profundidad > 4:
                return "[omitido]"
            if isinstance(valor, dict):
                return {
                    str(k)[:80]: limpiar(v, profundidad + 1)
                    for k, v in list(valor.items())[:100]
                    if str(k).lower() not in sensibles
                }
            if isinstance(valor, list):
                return [limpiar(v, profundidad + 1) for v in valor[:100]]
            if isinstance(valor, (str, int, float, bool)) or valor is None:
                return valor[:1000] if isinstance(valor, str) else valor
            return str(valor)[:1000]

        resultado = limpiar(payload)
        if len(json.dumps(resultado, ensure_ascii=False).encode()) > 64 * 1024:
            raise ErrorSuiteComercial("El payload excede el tamaño permitido")
        return resultado

    @staticmethod
    def recibir(integracion_id, evento_id, tipo, payload, firma, marca_tiempo, cuerpo):
        integracion = db.session.get(IntegracionEmpresa, integracion_id)
        if not integracion or integracion.estado != "activa":
            raise ErrorSuiteComercial("Integración no disponible")
        try:
            instante = int(str(marca_tiempo))
        except (TypeError, ValueError) as exc:
            raise PermissionError("Marca de tiempo de integración inválida") from exc
        if abs(int(time.time()) - instante) > 300:
            raise PermissionError("Webhook expirado")
        clave = bytes.fromhex(integracion.secreto_webhook_hash or "")
        esperada = hmac.new(
            clave, str(instante).encode() + b"." + bytes(cuerpo), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(esperada, str(firma or "").lower()):
            raise PermissionError("Firma de integración inválida")
        if not str(evento_id or "").strip():
            raise ErrorSuiteComercial("X-Event-ID es obligatorio")
        existente = db.session.scalar(
            db.select(EventoIntegracion).where(
                EventoIntegracion.integracion_id == integracion.id,
                EventoIntegracion.evento_externo_id == evento_id,
            )
        )
        if existente:
            return existente, False
        evento = EventoIntegracion(
            empresa_id=integracion.empresa_id,
            integracion_id=integracion.id,
            evento_externo_id=str(evento_id)[:150],
            tipo=str(tipo)[:80],
            payload=ServicioIntegraciones._payload_seguro(payload),
            estado="procesado",
            procesado_en=utcnow(),
        )
        db.session.add(evento)
        db.session.commit()
        return evento, True
