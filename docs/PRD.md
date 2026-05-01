NubeRush — Documento de Producto (PRD)

1. Visión General del Producto
NubeRush es un sistema operativo integral para tiendas de vapeo diseñado para controlar, automatizar y escalar todas las operaciones críticas del negocio.
El producto no se limita a facilitar ventas o delivery. Su propósito es establecer una infraestructura confiable que permita a las tiendas operar sin errores, cumplir con regulaciones y expandir su modelo de negocio de forma segura.
NubeRush busca convertirse en la capa central que conecta inventario, órdenes, cumplimiento regulatorio y logística de entrega en un único sistema coherente.

2. Naturaleza del Sistema
NubeRush es una plataforma multi-superficie compuesta por:
2.1 Aplicaciones móviles
Aplicación del cliente (Customer App)
Aplicación enfocada en el usuario final que permite:
ver catálogo en tiempo real
visualizar disponibilidad por tienda
realizar pedidos
realizar pagos
hacer seguimiento de órdenes
recibir notificaciones
Esta aplicación solo mostrará productos que estén permitidos por el sistema de compliance y disponibles en inventario.

Aplicación del driver (Driver App)
Aplicación operativa enfocada en entregas que permite:
recibir órdenes asignadas
ver rutas y direcciones
navegar hacia el cliente
validar identidad y edad del cliente
capturar prueba de entrega
completar órdenes
El driver no puede completar una entrega sin cumplir validaciones obligatorias (ej. edad).

2.2 Aplicación web operativa (Admin + Store Panel)
Una aplicación web centralizada que funciona como el núcleo operativo del negocio.
Será utilizada por:
owners
managers
staff
Permite:
gestión de inventario
gestión de productos
gestión de órdenes
auditoría
control de usuarios
control de cumplimiento
operaciones diarias de la tienda
Esta es la primera superficie crítica del sistema y la base del MVP.

3. Problema del Negocio
3.1 Inventario
Las tiendas actualmente enfrentan:
productos no registrados correctamente
ventas que no descuentan inventario
conteos incompletos
errores humanos frecuentes
robos o pérdidas no detectadas
Esto genera inconsistencia operativa y falta de control.

3.2 Compliance
El entorno regulatorio es cambiante y riesgoso:
productos pueden volverse ilegales
depende de revisión manual
no existe bloqueo automático
alto riesgo de incumplimiento

3.3 Operación
pocas personas manejan todo
múltiples tareas simultáneas
sistemas desconectados
procesos manuales

3.4 Delivery
existe demanda real
no se implementa por falta de control
preocupación por:
edad
fraude
inventario incorrecto

4. Propuesta de Valor
NubeRush ofrece:
control absoluto de inventario
cumplimiento automático de regulaciones
eliminación de errores humanos críticos
trazabilidad completa
base segura para delivery
El sistema está diseñado para forzar consistencia en lugar de depender de disciplina manual.

5. Arquitectura del Producto
5.1 Backend (núcleo del sistema)
El backend es la autoridad absoluta y contiene:
lógica de negocio
validaciones
reglas de cumplimiento
cálculo de totales
control de inventario
auditoría

5.2 Frontend
El frontend funciona como un cliente operativo:
no toma decisiones de negocio
no valida reglas críticas
no calcula datos sensibles
Responsabilidades:
mostrar datos
capturar input
ejecutar acciones
manejar estados visuales

6. Módulos Principales
6.1 Inventory Engine
Controla:
stock en tiempo real
movimientos de inventario
estados del producto
consistencia transaccional
Estados del inventario:
available
reserved
sold
returned
damaged
quarantined
Movimientos:
recepción
ajuste
reserva
venta
cancelación
devolución
bloqueo regulatorio
Regla fundamental:
No existe venta sin impacto en inventario.

6.2 Order Engine
Controla:
creación de órdenes
lifecycle completo
estados de la orden
sincronización con inventario
Estados típicos:
pending
accepted
preparing
ready
out_for_delivery
delivered
returned
cancelled

6.3 Compliance Engine
Responsable de:
determinar si un producto se puede vender
bloquear productos automáticamente
mantener estado regulatorio
Campos clave por producto:
regulatory_status
allowed_for_sale
hold_reason
Comportamiento:
Si un producto no está permitido:
no aparece en catálogo
no se puede vender
no se puede despachar
queda bloqueado en inventario

6.4 Audit Engine
Responsable de:
registrar todos los eventos del sistema
mantener historial de cambios
permitir trazabilidad completa
Ejemplos:
cambios de inventario
creación de órdenes
cambios de estado
acciones de usuarios

7. Usuarios y Roles
Owner
Control total del sistema.
Manager
Operación de tienda e inventario.
Staff
Ventas y operaciones básicas.
Driver
Entrega de órdenes.
Customer
Compra de productos.

8. Flujo Operativo
Producto registrado en inventario
Producto disponible si cumple compliance
Usuario crea orden
Inventario se reserva
Orden avanza en estados
Se genera auditoría
Inventario se actualiza

9. MVP (Estado Actual)
El sistema actualmente incluye:
Inventory
control real de stock
ajustes
logs
Orders
creación de órdenes
lifecycle completo
auditoría
sincronización automática
Resultado:
El sistema ya permite operar una tienda completa internamente.

10. Delivery (Fase Futura)
El delivery se construye sobre la base existente.
Requisitos previos:
inventario confiable
órdenes consistentes
compliance controlado
Flujo:
cliente ordena
sistema valida producto
tienda confirma
driver recoge
driver valida edad
driver entrega

11. Modelo de Negocio
Fase inicial:
sin costo mensual
comisión por orden
Fase futura:
modelo SaaS
reducción de comisión

12. Roadmap
Fase actual
Sistema operativo interno.
Próximas fases
Products (catálogo)
Users (roles)
Audit global
QA
mejoras visuales

13. Conclusión
NubeRush es una infraestructura operativa que:
elimina errores humanos
controla inventario
automatiza cumplimiento
habilita delivery
El sistema está diseñado para ser la base tecnológica sobre la cual operan las tiendas de vapeo de forma segura y escalable.
