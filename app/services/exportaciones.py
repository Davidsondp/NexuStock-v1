"""Exportación segura de reportes CSV y XLSX sin archivos temporales."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape  # nosec B406

from ..permisos import evaluar_permiso
from .auditoria import registrar_auditoria
from .reportes import Periodo, ServicioReportes
from ..models import db


class ErrorExportacion(ValueError):
    codigo = "exportacion_invalida"


REPORTES = frozenset({"productos", "stock", "movimientos", "analitica"})
FORMATOS = frozenset({"csv", "xlsx"})


def _texto_seguro(valor):
    texto = "" if valor is None else str(valor)
    # Evita que hojas de cálculo ejecuten contenido controlado por usuarios.
    if texto.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + texto
    return texto


class ServicioExportaciones:
    def __init__(self, usuario):
        self.usuario = usuario
        if not usuario.empresa_id or usuario.rol == "super_admin":
            raise PermissionError("Usuario sin ámbito empresarial")

    def exportar(
        self, reporte: str, formato: str, *, periodo: Periodo, bodega_id=None
    ) -> tuple[BytesIO, str, str]:
        self._exigir("reportes.exportar")
        reporte, formato = (reporte or "").lower(), (formato or "").lower()
        plan = self.usuario.empresa.suscripcion_actual.plan
        if not (
            plan.tiene_funcion("exportacion.basica") or plan.tiene_funcion("exportacion.avanzada")
        ):
            raise PermissionError("La exportación no está incluida en el plan")
        if reporte not in REPORTES:
            raise ErrorExportacion("Reporte no permitido")
        if formato not in FORMATOS:
            raise ErrorExportacion("Formato no permitido")
        if reporte in {"movimientos", "analitica"}:
            decision = evaluar_permiso(
                self.usuario,
                "reportes.avanzados",
                empresa_id=self.usuario.empresa_id,
            )
            if not decision.permitido or not plan.tiene_funcion("exportacion.avanzada"):
                raise PermissionError("La exportación avanzada no está incluida en el plan")
        encabezados, filas = self._datos(reporte, periodo, bodega_id)
        contenido = (
            self._csv(encabezados, filas)
            if formato == "csv"
            else self._xlsx(encabezados, filas, reporte)
        )
        registrar_auditoria(
            accion="reporte.exportado",
            modulo="reportes",
            usuario_id=self.usuario.id,
            empresa_id=self.usuario.empresa_id,
            entidad_tipo="Reporte",
            datos_nuevos={
                "reporte": reporte,
                "formato": formato,
                "filas": len(filas),
                "bodega_id": bodega_id,
                "desde": periodo.desde.date().isoformat(),
                "hasta": periodo.hasta.date().isoformat(),
            },
        )
        db.session.commit()
        fecha = periodo.hasta.date().isoformat()
        nombre = f"nexustock_{reporte}_{fecha}.{formato}"
        mime = (
            "text/csv; charset=utf-8"
            if formato == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        contenido.seek(0)
        return contenido, nombre, mime

    def _datos(self, reporte, periodo, bodega_id):
        servicio = ServicioReportes(self.usuario)
        if reporte == "productos":
            return (
                [
                    "Código",
                    "Nombre",
                    "Categoría",
                    "Marca",
                    "Unidad",
                    "Costo referencia",
                    "Precio venta",
                ],
                [
                    [
                        p.codigo,
                        p.nombre,
                        p.categoria,
                        p.marca,
                        p.unidad_medida,
                        p.costo_referencia,
                        p.precio_venta,
                    ]
                    for p in servicio.productos()
                ],
            )
        if reporte == "stock":
            return (
                [
                    "Código",
                    "Producto",
                    "Bodega",
                    "Cantidad",
                    "Reservada",
                    "Disponible",
                    "Costo promedio",
                    "Valor inventario",
                ],
                [
                    [
                        p.codigo,
                        p.nombre,
                        b.nombre,
                        i.cantidad,
                        i.cantidad_reservada,
                        i.cantidad_disponible,
                        i.costo_promedio,
                        i.cantidad * i.costo_promedio,
                    ]
                    for i, p, b in servicio.stock(bodega_id=bodega_id)
                ],
            )
        if reporte == "movimientos":
            return (
                [
                    "Fecha UTC",
                    "Tipo",
                    "Producto ID",
                    "Bodega ID",
                    "Cantidad",
                    "Stock anterior",
                    "Stock nuevo",
                    "Costo unitario",
                    "Precio unitario",
                    "Motivo",
                ],
                [
                    [
                        m.fecha.isoformat(),
                        m.tipo,
                        m.producto_id,
                        m.bodega_id,
                        m.cantidad,
                        m.stock_anterior,
                        m.stock_nuevo,
                        m.costo_unitario,
                        m.precio_unitario,
                        m.motivo,
                    ]
                    for m in servicio.movimientos(periodo, bodega_id=bodega_id, limite=2000)
                ],
            )
        datos = servicio.analitica(periodo, bodega_id=bodega_id, limite=100)
        return (
            ["Indicador", "Valor"],
            [
                ["Desde", datos["periodo"]["desde"]],
                ["Hasta", datos["periodo"]["hasta"]],
                ["Ventas confirmadas", datos["ventas_confirmadas"]],
                ["Ingresos", datos["ingresos"]],
                ["Costo de ventas", datos["costo_ventas"]],
                ["Margen bruto", datos["margen_bruto"]],
                ["Valor inventario actual", datos["valor_inventario_actual"]],
                ["Unidades vendidas", datos["unidades_vendidas"]],
                ["Días cobertura actual", datos["dias_cobertura_actual"]],
                ["Rotación operativa aproximada", datos["rotacion_operativa_aproximada"]],
                ["Nota rotación", datos["nota_rotacion"]],
            ],
        )

    @staticmethod
    def _csv(encabezados, filas):
        salida = StringIO(newline="")
        escritor = csv.writer(salida, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        escritor.writerow([_texto_seguro(v) for v in encabezados])
        escritor.writerows([[_texto_seguro(v) for v in fila] for fila in filas])
        return BytesIO(("\ufeff" + salida.getvalue()).encode("utf-8"))

    @staticmethod
    def _xlsx(encabezados, filas, titulo):
        todas = [encabezados, *filas]
        filas_xml = []
        for indice_fila, fila in enumerate(todas, 1):
            celdas = []
            for indice_columna, valor in enumerate(fila, 1):
                referencia = f"{ServicioExportaciones._columna(indice_columna)}{indice_fila}"
                seguro = _texto_seguro(valor)
                estilo = ' s="1"' if indice_fila == 1 else ""
                celdas.append(
                    f'<c r="{referencia}" t="inlineStr"{estilo}><is><t xml:space="preserve">{escape(seguro)}</t></is></c>'
                )
            filas_xml.append(f'<row r="{indice_fila}">{"".join(celdas)}</row>')
        hoja = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(filas_xml)}</sheetData><autoFilter ref="A1:{ServicioExportaciones._columna(len(encabezados))}1"/>'
            "</worksheet>"
        )
        archivos = {
            "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
            "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
            "xl/workbook.xml": f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{escape(titulo.title())}" sheetId="1" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
            "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/><family val="2"/></font><font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
            "xl/worksheets/sheet1.xml": hoja,
        }
        salida = BytesIO()
        with ZipFile(salida, "w", ZIP_DEFLATED) as archivo:
            for nombre, contenido in archivos.items():
                archivo.writestr(nombre, contenido)
        salida.seek(0)
        return salida

    @staticmethod
    def _columna(numero):
        resultado = ""
        while numero:
            numero, resto = divmod(numero - 1, 26)
            resultado = chr(65 + resto) + resultado
        return resultado

    def _exigir(self, permiso):
        decision = evaluar_permiso(self.usuario, permiso, empresa_id=self.usuario.empresa_id)
        if not decision.permitido:
            raise PermissionError(decision.mensaje)
