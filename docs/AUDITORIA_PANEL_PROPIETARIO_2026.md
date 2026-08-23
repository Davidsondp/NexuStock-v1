# Auditoría del panel propietario

## Cobertura confirmada

- Dashboard global e ingresos confirmados.
- Empresas: búsqueda, suspensión, cancelación, reactivación y revocación de sesiones.
- Planes: precios, límites, almacenamiento, capacidades, orden y disponibilidad.
- Suscripciones: consulta y corrección excepcional con motivo obligatorio y auditoría.
- Pagos: estado, proveedor, monto, referencia e incidencias.
- Facturación: consulta global de facturas y recibos emitidos.
- Identidad: directorio, estado, desbloqueo, verificación y cobertura 2FA.
- Auditoría global y por empresa.
- Salud: base de datos, migración, versión, actividad y riesgos de seguridad.

## Separación deliberada

El propietario no puede editar inventario, ventas, compras o clientes de un
tenant. Tampoco puede leer secretos, datos completos de tarjetas ni ejecutar
respaldos desde el navegador. Son límites de seguridad, no carencias del panel.

## Operaciones de infraestructura aún externas

- Crear y restaurar respaldos de PostgreSQL.
- Rotar claves y secretos.
- Desplegar versiones y revertir releases.
- Configurar DNS, TLS, SMTP y observabilidad.
- Gestionar contratos y credenciales de Mercado Pago/Webpay.
- Ejecutar pentest, respuesta a incidentes y certificaciones.

Estas operaciones deben permanecer protegidas por el proveedor cloud, con MFA,
registro de cambios y acceso mínimo.
