NubeRush — Documento de Producto (PRD)

1. Visión General del Producto
NubeRush es un sistema operativo integral para tiendas de vapeo diseñado para controlar, automatizar y escalar todas las operaciones críticas del negocio.
El producto no se limita a facilitar ventas o delivery. Su propósito es establecer una infraestructura confiable que permita a las tiendas operar sin errores, cumplir con regulaciones y expandir su modelo de negocio de forma segura.
NubeRush busca convertirse en la capa central que conecta inventario, órdenes, cumplimiento regulatorio y logística de entrega en un único sistema coherente.
En su estado actual, NubeRush opera como el núcleo operativo interno: una Aplicación Web compuesta por el Admin Panel (supervisión y control de la plataforma) y el Store Panel (operaciones de tienda). Las superficies orientadas al cliente final (Customer App) y al repartidor (Driver App) son fases futuras y aún no existen.

2. Naturaleza del Sistema
NubeRush es una plataforma multi-superficie construida sobre un único backend autoritativo. Hoy existe una superficie en producción —la Aplicación Web operativa— y dos superficies móviles planificadas como fases futuras (Customer App y Driver App), que aún no existen.

2.1 Aplicación web operativa — núcleo operativo interno (superficie actual)
Una aplicación web centralizada que funciona como el núcleo operativo interno del negocio. Es la superficie crítica del sistema y la base del MVP, y se compone de dos paneles gobernados por el rol del usuario en el backend.

Admin Panel (supervisión y control de la plataforma)
Usado por el equipo de NubeRush. Identidad global, cross-store. Permite:
supervisar la plataforma completa
gestión y revisión de tiendas y de aplicaciones de tienda
visibilidad global de productos, inventario y órdenes
revisión de cumplimiento y superficie regulatoria de administración
auditoría unificada global
reportes y métricas operativas

Store Panel (operaciones de tienda)
Usado por owners, managers y staff. Identidad acotada a su propia tienda (tenancy reforzado por el backend). Permite:
gestión de inventario
gestión de productos
gestión de órdenes
control de usuarios del equipo
visibilidad de cumplimiento
auditoría de la tienda
operaciones diarias de la tienda

2.2 Aplicaciones móviles (superficies futuras)
Las superficies móviles aún no existen. Se construirán sobre el mismo backend una vez que el núcleo operativo esté consolidado.

Aplicación del cliente (Customer App) — superficie futura
Aplicación enfocada en el usuario final que, cuando se construya, permitirá:
ver catálogo
carrito de compras
checkout
pagos con Stripe (sujeto a aprobación y activación futura)
cuenta de cliente
seguimiento de órdenes
notificaciones al cliente
posible verificación de edad previa, si se aprueba más adelante
Mostrará únicamente productos permitidos por el sistema de compliance y disponibles en inventario.

Aplicación del driver (Driver App) — superficie futura
Aplicación operativa enfocada en entregas que, cuando se construya, permitirá:
flujo de recogida (pickup)
navegación hacia el cliente
ejecución de la entrega
verificación final de identidad y edad
captura de prueba de entrega
completar la entrega
flujo de entrega fallida / devolución
La verificación final de edad e identidad y la prueba de entrega vivirán en la Driver App, no en la Aplicación Web.

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
detección de señales regulatorias y alertas para revisión humana (sin acción automática)
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
Estados conceptuales del inventario:
available
reserved
sold
flagged
quarantined
Las reservas se gestionan operativamente como cantidad reservada (quantity_reserved) sobre el stock disponible. "reserved" también existe como concepto de estado, pero la reserva no se modela únicamente como un estado de ítem: el mecanismo principal es la cantidad reservada.
Tipos de movimiento de inventario:
receipt (recepción)
adjustment (ajuste)
reservation (reserva)
sale (venta)
cancellation (cancelación)
return (devolución)
damage (daño)
compliance_hold (retención por cumplimiento)
returned y damaged son movimientos de inventario, no estados primarios del ítem.
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
canceled

6.3 Compliance Engine
Responsable de:
determinar el estado de cumplimiento de un producto (si se puede vender)
mantener el estado regulatorio del producto
soportar decisiones de cumplimiento explícitas tomadas por un admin
Las acciones de cumplimiento son decisiones humanas explícitas. No hay bloqueo, hold ni ban automático.
Campos clave por producto:
regulatory_status
allowed_for_sale
hold_reason
Comportamiento:
Cuando un admin marca un producto como no permitido mediante una decisión explícita (hold o ban):
no aparece en catálogo
no se puede vender
no se puede despachar
el efecto sobre el inventario se aplica por una vía auditada, tras la decisión humana

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

6.5 Regulatory Intelligence (revisión admin)
Superficie de administración para señales regulatorias, basada en revisión humana explícita. Vive en /app/admin/regulatory y es solo para admin.
La superficie soporta:
lista de alertas
filtros
detalle de alerta
acciones de lifecycle: acknowledge, dismiss, resolve no_action, resolve hold, resolve ban
decision trail (historial de decisiones)
Todas las acciones son decisiones humanas explícitas. En F2.26 no ocurre ningún hold, ban ni bloqueo automático.
Los usuarios de tienda (Store Panel) aún no ven alertas regulatorias; por ahora es una superficie exclusiva de admin.

Flujo regulatorio (revisión humana):
existe una señal/aviso regulatorio (notice)
se crea un match de producto o una alerta
el admin revisa la alerta
el admin elige una acción explícita (acknowledge / dismiss / resolve no_action / hold / ban)
la decisión queda registrada en el decision trail
solo tras un hold o ban explícito el backend aplica la vía de cumplimiento auditada
En F2.26 no hay scraping, polling ni jobs automáticos; la ingesta automatizada de fuentes regulatorias (por ejemplo, FDA) sería una capacidad futura/diferida.

KPI de regulatorio en el dashboard (diferido):
el tile de KPI regulatorio del dashboard está diferido
todavía no existe un agregado regulatorio en el Admin Dashboard
una implementación futura debería usar un agregado en el backend en lugar de una segunda query en el dashboard

7. Usuarios y Roles
Admin
Operador de la plataforma NubeRush. Identidad global, cross-store; supervisión y control de la plataforma (Admin Panel).
Owner
Control total de su tienda.
Manager
Operación de tienda e inventario.
Staff
Ventas y operaciones básicas.
Driver
Entrega de órdenes (rol asociado a la Driver App, superficie futura).
Customer
Compra de productos (rol asociado a la Customer App, superficie futura).

8. Flujo Operativo
Producto registrado en inventario
Producto disponible si cumple compliance
Usuario crea orden
Inventario se reserva
Orden avanza en estados
Se genera auditoría
Inventario se actualiza

9. MVP / Estado Actual (lo que ya está en producción)
La Aplicación Web operativa (núcleo operativo interno) está en producción. Lo ya enviado incluye:
Núcleo operativo web (Admin Panel + Store Panel)
Admin Panel — supervisión y control de la plataforma
Store Panel — operaciones de tienda
Productos y detalle de producto
Imágenes de producto
Inventario (control real de stock, movimientos, ajustes y logs)
Órdenes (creación, lifecycle completo y sincronización con inventario)
Usuarios (gestión por rol)
Auditoría (feed unificado: global para admin, acotado por tienda para usuarios de tienda)
Cumplimiento (visibilidad y revisión)
Superficie regulatoria de administración (alertas con revisión humana explícita; sin acción automática)
Earnings / ganancias como estimaciones de contabilidad interna (Stripe pendiente; ver fases futuras)
Settings (administración y tienda)
RBAC y tenancy (aislamiento por tienda; admin global)
Autoridad del backend como fuente de verdad
Resultado:
El sistema ya permite operar una tienda completa de forma interna y supervisar la plataforma desde el Admin Panel.

10. Delivery (fase futura)
El delivery se construirá sobre la base existente. Es una capacidad futura asociada a la Customer App y a la Driver App; no existe hoy.
Requisitos previos:
inventario confiable
órdenes consistentes
compliance controlado
Flujo previsto (futuro):
el cliente ordena
el sistema valida producto
la tienda confirma
el driver recoge
el driver realiza la verificación final de edad e identidad
el driver entrega y captura la prueba de entrega

11. Modelo de Negocio y Estado de Pagos

11.1 Modelo de negocio (previsto / futuro)
El modelo de negocio previsto puede incluir flujos futuros de:
comisión por orden
planes SaaS
tarifas de onboarding / setup
La captura de pagos requiere la aprobación de Stripe y el checkout futuro de la Customer App. Hoy, el Web App solo registra datos operativos de órdenes y estimaciones de contabilidad interna; no cobra ni liquida dinero.
Fase inicial prevista:
sin costo mensual
comisión por orden
Fase futura prevista:
modelo SaaS
reducción de comisión

11.2 Estado de pagos (Stripe pendiente)
NubeRush está a la espera de la aprobación de Stripe. En el estado actual:
la aprobación de Stripe está pendiente
la integración de Stripe es una fase futura
no se procesan pagos reales hoy en ninguna parte del Web App
no se crea ningún PaymentIntent hoy
no hay ningún webhook de Stripe activo hoy
no existe checkout hoy
no existe flujo de pago del cliente hoy
no hay captura ni liquidación de pagos hoy
Stripe no confirma órdenes hoy; las órdenes avanzan por su lifecycle interno sin movimiento de dinero.

11.3 Responsabilidad de pagos por superficie
el Web App no procesa pagos de clientes
el Store Panel no captura pagos reales
el Admin Panel puede ver estimaciones operativas y de contabilidad interna, no dinero liquidado por Stripe
la Customer App será dueña del checkout y del pago del cliente en una fase futura
la Driver App no es responsable del procesamiento de pagos

11.4 Ganancias y resúmenes comerciales (contabilidad interna)
Las ganancias, los ingresos y los resúmenes comerciales mostrados son estimaciones de contabilidad interna:
se basan en órdenes registradas y en reglas de negocio internas
no son ingresos liquidados por Stripe
no son la verdad del procesador de pagos
la liquidación final de pagos dependerá de la futura integración de Stripe

12. Roadmap
Fase actual (en producción)
Núcleo operativo interno: Aplicación Web con Admin Panel y Store Panel (productos, detalle de producto, imágenes, inventario, órdenes, usuarios, auditoría, cumplimiento, superficie regulatoria de administración, earnings internos, settings; RBAC/tenancy; backend autoritativo).
Próximas fases (futuras)
Activación de pagos con Stripe (pendiente de aprobación)
Customer App (catálogo, carrito, checkout, pagos, cuenta, seguimiento, notificaciones)
Driver App (recogida, navegación, ejecución de entrega, verificación final de edad/identidad, prueba de entrega, entrega fallida)
Delivery end-to-end sobre las superficies anteriores

13. Conclusión
NubeRush es una infraestructura operativa que:
elimina errores humanos
controla inventario
asiste el cumplimiento mediante detección de señales y revisión humana
sienta las bases para el delivery futuro
El sistema está diseñado para ser la base tecnológica sobre la cual operan las tiendas de vapeo de forma segura y escalable.
