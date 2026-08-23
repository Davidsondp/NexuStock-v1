"""Motor determinista y centralizado de alertas de inventario."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from ..models import (
    AlertaInventario,
    Bodega,
    ConfiguracionEmpresa,
    Inventario,
    Lote,
    Movimiento,
    Producto,
    Proveedor,
    db,
    utcnow,
)
from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .contexto import sucursales_autorizadas
from .perfiles_empresa import tiene_capacidad
from .notificaciones import notificar_empresa


class ErrorAlerta(ValueError):
    codigo = "alerta_invalida"


@dataclass(frozen=True)
class ResultadoGeneracion:
    creadas: int
    actualizadas: int
    resueltas: int


class ServicioAlertas:
    VENTANA_CONSUMO_DIAS = 30

    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def listar(self, *, estado="activa", tipo=None, bodega_id=None):
        self._exigir("alertas.ver")
        bodegas = self._bodegas_autorizadas()
        consulta = db.select(AlertaInventario).where(
            AlertaInventario.empresa_id == self.usuario.empresa_id,
            AlertaInventario.bodega_id.in_(bodegas),
        )
        if estado:
            consulta = consulta.where(AlertaInventario.estado == estado)
        if tipo:
            consulta = consulta.where(AlertaInventario.tipo == tipo)
        if bodega_id:
            if bodega_id not in bodegas:
                raise PermissionError("Bodega no autorizada")
            consulta = consulta.where(AlertaInventario.bodega_id == bodega_id)
        return list(
            db.session.scalars(
                consulta.order_by(
                    AlertaInventario.prioridad.desc(), AlertaInventario.creado_en.desc()
                )
            )
        )

    def generar(self) -> ResultadoGeneracion:
        self._exigir("alertas.gestionar")
        ahora = utcnow()
        bodegas = self._bodegas_autorizadas()

        configuracion = db.session.scalar(
            db.select(ConfiguracionEmpresa).where(
                ConfiguracionEmpresa.empresa_id == self.usuario.empresa_id
            )
        )
        dias_sin_movimiento = configuracion.dias_sin_movimiento if configuracion else 90

        inventarios = list(
            db.session.scalars(
                db.select(Inventario)
                .join(
                    Producto,
                    db.and_(
                        Producto.id == Inventario.producto_id,
                        Producto.empresa_id == Inventario.empresa_id,
                    ),
                )
                .where(
                    Inventario.empresa_id == self.usuario.empresa_id,
                    Inventario.bodega_id.in_(bodegas),
                    Producto.activo.is_(True),
                    Producto.eliminado.is_(False),
                )
            )
        )

        alertas_activas = list(
            db.session.scalars(
                db.select(AlertaInventario)
                .where(
                    AlertaInventario.empresa_id == self.usuario.empresa_id,
                    AlertaInventario.bodega_id.in_(bodegas),
                    AlertaInventario.estado == "activa",
                )
                .with_for_update()
            )
        )

        activas_generales = {
            (
                alerta.producto_id,
                alerta.bodega_id,
                alerta.tipo,
            ): alerta
            for alerta in alertas_activas
            if alerta.lote_id is None
        }
        activas_lotes = {
            (
                alerta.lote_id,
                alerta.tipo,
            ): alerta
            for alerta in alertas_activas
            if alerta.lote_id is not None
        }

        detectadas_generales = set()
        detectadas_lotes = set()
        creadas = 0
        actualizadas = 0
        resueltas = 0

        try:
            for inventario in inventarios:
                producto = db.session.get(
                    Producto,
                    inventario.producto_id,
                )
                reglas = self._evaluar(
                    inventario,
                    producto,
                    ahora,
                    dias_sin_movimiento,
                    configuracion,
                )

                for (
                    tipo,
                    prioridad,
                    titulo,
                    mensaje,
                    datos,
                ) in reglas:
                    clave = (
                        producto.id,
                        inventario.bodega_id,
                        tipo,
                    )
                    detectadas_generales.add(clave)
                    alerta = activas_generales.get(clave)

                    if alerta:
                        alerta.prioridad = prioridad
                        alerta.titulo = titulo
                        alerta.mensaje = mensaje
                        alerta.datos = datos
                        actualizadas += 1
                    else:
                        alerta_nueva = AlertaInventario(
                            empresa_id=self.usuario.empresa_id,
                            producto_id=producto.id,
                            bodega_id=inventario.bodega_id,
                            lote_id=None,
                            tipo=tipo,
                            prioridad=prioridad,
                            titulo=titulo,
                            mensaje=mensaje,
                            datos=datos,
                        )
                        db.session.add(alerta_nueva)
                        db.session.flush()
                        notificar_empresa(
                            empresa_id=self.usuario.empresa_id,
                            tipo="alerta_inventario",
                            titulo=titulo,
                            mensaje=mensaje,
                            referencia_tipo="alerta",
                            referencia_id=alerta_nueva.id,
                        )
                        creadas += 1

            if tiene_capacidad(
                self.usuario.empresa,
                "control_vencimientos",
            ):
                lotes = db.session.execute(
                    db.select(
                        Lote,
                        Producto,
                    )
                    .join(
                        Producto,
                        db.and_(
                            Producto.id == Lote.producto_id,
                            Producto.empresa_id == Lote.empresa_id,
                        ),
                    )
                    .where(
                        Lote.empresa_id == self.usuario.empresa_id,
                        Lote.bodega_id.in_(bodegas),
                        Lote.activo.is_(True),
                        Lote.cantidad > 0,
                        Lote.fecha_vencimiento.is_not(None),
                        Producto.activo.is_(True),
                        Producto.eliminado.is_(False),
                        Producto.controla_vencimiento.is_(True),
                    )
                ).all()

                for lote, producto in lotes:
                    regla = self._evaluar_lote(
                        lote,
                        producto,
                    )

                    if regla is None:
                        continue

                    (
                        tipo,
                        prioridad,
                        titulo,
                        mensaje,
                        datos,
                    ) = regla

                    clave = (
                        lote.id,
                        tipo,
                    )
                    detectadas_lotes.add(clave)
                    alerta = activas_lotes.get(clave)

                    if alerta:
                        alerta.prioridad = prioridad
                        alerta.titulo = titulo
                        alerta.mensaje = mensaje
                        alerta.datos = datos
                        actualizadas += 1
                    else:
                        alerta_nueva = AlertaInventario(
                            empresa_id=self.usuario.empresa_id,
                            producto_id=producto.id,
                            bodega_id=lote.bodega_id,
                            lote_id=lote.id,
                            tipo=tipo,
                            prioridad=prioridad,
                            titulo=titulo,
                            mensaje=mensaje,
                            datos=datos,
                        )
                        db.session.add(alerta_nueva)
                        db.session.flush()
                        notificar_empresa(
                            empresa_id=self.usuario.empresa_id,
                            tipo="alerta_vencimiento",
                            titulo=titulo,
                            mensaje=mensaje,
                            referencia_tipo="alerta",
                            referencia_id=alerta_nueva.id,
                        )
                        creadas += 1

            for clave, alerta in activas_generales.items():
                if clave not in detectadas_generales:
                    alerta.estado = "resuelta"
                    alerta.resuelta_en = ahora
                    alerta.resuelta_por_id = self.usuario.id
                    resueltas += 1

            for clave, alerta in activas_lotes.items():
                if clave not in detectadas_lotes:
                    alerta.estado = "resuelta"
                    alerta.resuelta_en = ahora
                    alerta.resuelta_por_id = self.usuario.id
                    resueltas += 1

            registrar_auditoria(
                accion="alertas.generadas",
                modulo="alertas",
                usuario_id=self.usuario.id,
                empresa_id=self.usuario.empresa_id,
                entidad_tipo="AlertaInventario",
                datos_nuevos={
                    "creadas": creadas,
                    "actualizadas": actualizadas,
                    "resueltas": resueltas,
                },
            )
            db.session.commit()

            return ResultadoGeneracion(
                creadas,
                actualizadas,
                resueltas,
            )
        except Exception:
            db.session.rollback()
            raise

    def cambiar_estado(self, alerta_id: int, estado: str) -> AlertaInventario:
        self._exigir("alertas.gestionar")
        if estado not in {"resuelta", "ignorada"}:
            raise ErrorAlerta("El estado debe ser resuelta o ignorada")
        bodegas = self._bodegas_autorizadas()
        alerta = db.session.scalar(
            db.select(AlertaInventario)
            .where(
                AlertaInventario.id == alerta_id,
                AlertaInventario.empresa_id == self.usuario.empresa_id,
                AlertaInventario.bodega_id.in_(bodegas),
            )
            .with_for_update()
        )
        if not alerta:
            raise PermissionError("Alerta no autorizada")
        if alerta.estado != "activa":
            raise ErrorAlerta("Solo se puede gestionar una alerta activa")
        alerta.estado = estado
        alerta.resuelta_por_id = self.usuario.id
        alerta.resuelta_en = utcnow()
        registrar_auditoria(
            accion=f"alerta.{estado}",
            modulo="alertas",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="AlertaInventario",
            entidad_id=alerta.id,
            datos_nuevos={"estado": estado},
        )
        db.session.commit()
        return alerta

    def _evaluar(self, inventario, producto, ahora, dias_sin_movimiento, configuracion=None):
        reglas = []
        disponible = Decimal(inventario.cantidad_disponible)
        minimo = Decimal(producto.stock_minimo)
        reorden = Decimal(producto.punto_reorden)
        maximo = Decimal(producto.stock_maximo) if producto.stock_maximo is not None else None
        base = {
            "stock": str(inventario.cantidad),
            "reservado": str(inventario.cantidad_reservada),
            "disponible": str(disponible),
        }
        stock_bajo_habilitado = configuracion is None or configuracion.alerta_stock_bajo
        sobrestock_habilitado = configuracion is None or configuracion.alerta_sobrestock
        if stock_bajo_habilitado and disponible <= minimo:
            prioridad = "critica" if disponible <= 0 else "alta"
            reglas.append(
                (
                    "stock_bajo",
                    prioridad,
                    f"Stock bajo: {producto.nombre}",
                    f"Quedan {disponible} unidades disponibles; el mínimo es {minimo}.",
                    {**base, "stock_minimo": str(minimo)},
                )
            )
        if sobrestock_habilitado and maximo is not None and Decimal(inventario.cantidad) > maximo:
            exceso = Decimal(inventario.cantidad) - maximo
            reglas.append(
                (
                    "sobrestock",
                    "media",
                    f"Sobrestock: {producto.nombre}",
                    f"El stock supera el máximo en {exceso} unidades.",
                    {**base, "stock_maximo": str(maximo), "exceso": str(exceso)},
                )
            )

        inicio = ahora - timedelta(days=self.VENTANA_CONSUMO_DIAS)
        consumo = abs(
            Decimal(
                db.session.scalar(
                    db.select(db.func.coalesce(db.func.sum(Movimiento.cantidad), 0)).where(
                        Movimiento.empresa_id == self.usuario.empresa_id,
                        Movimiento.producto_id == producto.id,
                        Movimiento.bodega_id == inventario.bodega_id,
                        Movimiento.tipo == "salida",
                        Movimiento.fecha >= inicio,
                        Movimiento.fecha <= ahora,
                    )
                )
                or 0
            )
        )
        promedio = consumo / Decimal(self.VENTANA_CONSUMO_DIAS)
        proveedor = (
            db.session.get(Proveedor, producto.proveedor_principal_id)
            if producto.proveedor_principal_id
            else None
        )
        dias_reposicion = proveedor.dias_entrega if proveedor and proveedor.activo else 7
        if promedio > 0:
            cobertura = disponible / promedio
            if cobertura <= Decimal(dias_reposicion):
                reglas.append(
                    (
                        "riesgo_agotamiento",
                        "alta",
                        f"Riesgo de agotamiento: {producto.nombre}",
                        f"La cobertura estimada es de {cobertura.quantize(Decimal('0.1'))} días.",
                        {
                            **base,
                            "ventana_dias": self.VENTANA_CONSUMO_DIAS,
                            "consumo": str(consumo),
                            "promedio_diario": str(promedio),
                            "dias_cobertura": str(cobertura),
                            "dias_reposicion": dias_reposicion,
                        },
                    )
                )
        plan = self.usuario.empresa.suscripcion_actual.plan
        permite_recomendaciones = plan.tiene_funcion("recomendaciones") or plan.codigo == "prueba"
        if disponible <= reorden and permite_recomendaciones:
            objetivo = (
                maximo if maximo is not None else reorden + (promedio * Decimal(dias_reposicion))
            )
            sugerida = max(Decimal(0), objetivo - disponible).quantize(
                Decimal("1"), rounding=ROUND_CEILING
            )
            reglas.append(
                (
                    "recomendacion_compra",
                    "alta" if disponible <= minimo else "media",
                    f"Recomendación de compra: {producto.nombre}",
                    f"Se recomienda comprar {sugerida} unidades para recuperar el nivel objetivo.",
                    {
                        **base,
                        "punto_reorden": str(reorden),
                        "cantidad_sugerida": str(sugerida),
                        "metodo": "nivel_objetivo",
                        "dias_reposicion": dias_reposicion,
                    },
                )
            )

        ultimo = db.session.scalar(
            db.select(db.func.max(Movimiento.fecha)).where(
                Movimiento.empresa_id == self.usuario.empresa_id,
                Movimiento.producto_id == producto.id,
                Movimiento.bodega_id == inventario.bodega_id,
            )
        )
        limite = ahora - timedelta(days=dias_sin_movimiento)
        referencia = ultimo or producto.creado_en
        if Decimal(inventario.cantidad) > 0 and referencia <= limite:
            reglas.append(
                (
                    "sin_movimiento",
                    "baja",
                    f"Producto sin movimiento: {producto.nombre}",
                    f"No registra movimientos desde hace al menos {dias_sin_movimiento} días.",
                    {
                        **base,
                        "dias_umbral": dias_sin_movimiento,
                        "ultimo_movimiento": ultimo.isoformat() if ultimo else None,
                    },
                )
            )
        return reglas

    def _evaluar_lote(
        self,
        lote,
        producto,
    ):
        vencimiento = lote.fecha_vencimiento

        if vencimiento is None:
            return None

        dias = (vencimiento - date.today()).days

        datos = {
            "lote_id": lote.id,
            "numero_lote": lote.numero,
            "producto_id": producto.id,
            "producto_codigo": producto.codigo,
            "fecha_vencimiento": vencimiento.isoformat(),
            "dias_para_vencer": dias,
            "cantidad": str(lote.cantidad),
        }

        if dias < 0:
            return (
                "lote_vencido",
                "critica",
                (f"Lote vencido: " f"{producto.nombre}"),
                (
                    f"El lote {lote.numero} venció "
                    f"hace {abs(dias)} días y mantiene "
                    f"{lote.cantidad} unidades."
                ),
                datos,
            )

        if dias == 0:
            return (
                "lote_vence_hoy",
                "critica",
                (f"Lote vence hoy: " f"{producto.nombre}"),
                (f"El lote {lote.numero} vence hoy " f"y mantiene {lote.cantidad} " "unidades."),
                datos,
            )

        if dias <= 30:
            prioridad = "critica" if dias <= 7 else "alta"

            return (
                "lote_proximo_vencer",
                prioridad,
                (f"Lote próximo a vencer: " f"{producto.nombre}"),
                (
                    f"El lote {lote.numero} vence "
                    f"en {dias} días y mantiene "
                    f"{lote.cantidad} unidades."
                ),
                datos,
            )

        return None

    def _bodegas_autorizadas(self):
        sucursales = {s.id for s in sucursales_autorizadas(self.usuario)}
        return set(
            db.session.scalars(
                db.select(Bodega.id).where(
                    Bodega.empresa_id == self.usuario.empresa_id,
                    Bodega.sucursal_id.in_(sucursales),
                    Bodega.activa.is_(True),
                    Bodega.eliminado.is_(False),
                )
            )
        )

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
