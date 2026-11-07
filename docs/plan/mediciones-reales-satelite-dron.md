# Mediciones reales del campo: satélite y dron (diseño, 7/11/2026)

Hoy DORA arma el plan con lo que dice el productor, sus facturas y los promedios de la zona. Este diseño le suma **lo que se mide en el lote**: el verde del cultivo desde el satélite y lo que ve un dron. La regla es la misma de siempre: el número lo mide una herramienta, el verificador controla que cada número de la respuesta esté respaldado por un resultado de herramienta, y el modelo de lenguaje solo explica. El verificador no sabe si la soja viene mal de verdad: sabe de dónde salió cada número.

Specs: [SPEC-46](../specs/SPEC-46-satellite-ndvi.md) (satélite) y [SPEC-47](../specs/SPEC-47-drone-mission.md) (dron). La SPEC-45 queda para la planilla v2.

## 1. Satélite: el NDVI del lote entra al plan (SPEC-46)

- **Qué hace.** Herramienta nueva `field_ndvi`: recibe el lote (el polígono dibujado en el mapa, o coordenadas), busca la última imagen de Sentinel-2 sin nubes sobre ese lote, calcula el NDVI (cuán verde y tupido está el cultivo) y lo compara con el mismo lote en los cinco años anteriores, en la misma fecha. Devuelve fecha de la imagen, verde de hoy, verde normal, la diferencia en %, las hectáreas flojas y un mapa del lote en colores.
- **Cómo mueve el plan.** Si el cultivo está en la etapa en que el verde dice algo del rinde (trigo de mediados de septiembre a principios de noviembre en la zona núcleo, soja de primera de mediados de enero a mediados de marzo, etc.), propone un rinde: rinde normal × (verde de hoy ÷ verde normal), acotado entre 50 % y 110 %. Lo dice como lo que es, una regla simple sin calibrar, y **pregunta antes de usarlo**. Si el productor dice que sí (o da su propio número), DORA rehace el plan con las hectáreas ya sembradas fijas, igual que con la foto de la inundación: ventas, acopio, crédito y caja.
- **Fuente elegida: Element84 Earth Search.** Es el mismo Sentinel-2 corregido (L2A) que distribuye Copernicus, en archivos que se pueden leer de a pedacitos: para un lote de 100 ha se bajan unos cientos de kB por imagen. **No pide cuenta, ni clave, ni cupo.** Planetary Computer exige firmar cada enlace con su servicio de tokens; Copernicus Data Space calcula las estadísticas de su lado pero pide registrarse. Copernicus queda como respaldo si Earth Search se cae.
- **Lo probé hoy (prototipo, gratis).** Un cuadrado inventado de 100 ha cerca de Pergamino: 8 imágenes entre el 1/9 y el 7/11, de 10 a 16 segundos cada una, NDVI 0,58 el 2/10 con el lote 100 % despejado. Dos hallazgos que van a la spec:
  1. **El porcentaje de nubes de la imagen entera no sirve para el lote.** El 2/10 la imagen tenía 45 % de nubes y el lote estaba limpio; el 29/9 tenía 14 % y el lote estaba 80 % tapado. Hay que mirar las nubes píxel por píxel dentro del lote (la clasificación SCL que viene con cada imagen).
  2. **Una trampa en los metadatos.** Earth Search ya le restó a los números el desplazamiento de reflectancia que usa Sentinel-2 desde 2022, pero igual declara ese desplazamiento. Si se aplica de nuevo, el NDVI da 1,43, que es imposible (el máximo es 1). La spec fija la regla y un test que la controla.
- **Nubes y fechas.** Se usa la imagen más nueva de los últimos 30 días con al menos 70 % del lote despejado. Si no hay, DORA no inventa: dice que las imágenes tienen nubes y que el satélite vuelve a pasar en 2 a 5 días. La fecha de la imagen y su antigüedad van siempre en la respuesta.

## 2. Dron: la misión de vuelo, el simulador y las fotos (SPEC-47)

- **La misión.** Herramienta `plan_drone_mission`: con el polígono del lote y el objetivo (contar vacas, ver el pasto, recorrer el cultivo) calcula las pasadas en "cortadora de césped", la altura, la superposición, cuántas fotos, cuántos minutos y cuántas baterías, y escribe la misión en formatos estándar: `.plan` de QGroundControl, `.waypoints` de Mission Planner (los dos son MAVLink, lo que vuelan los drones con ArduPilot o PX4) y `.kml` para Google Earth. Controla sola que las fotos cubran el 99 % del lote y que ningún punto salga del perímetro.
- **El simulador: ArduPilot SITL, nativo en Windows.** PX4 necesita Linux (WSL o Docker) y esta máquina no tiene ninguno. ArduPilot publica un ejecutable de Windows (el mismo que usa Mission Planner). Lo bajé a `D:\projects\tools\sitl\copter\`, pero **no lo pude ejecutar desde mi sesión** (el sistema de permisos no me dejó correr un ejecutable bajado de internet); lo corre Antigravity o vos. Un script con `pymavlink` sube la misión al simulador, la vuela y compara la trayectoria con la planeada. Para mostrarlo se usa Mission Planner en versión portátil, descomprimido en D:.
- **Las fotos.** El simulador vuela pero no saca fotos. Para la demo se usan **fotos reales de dron de un dataset público**: el de vacas en pastoreo del Institut de l'Élevage (Zenodo, licencia CC-BY 4.0, 1.385 fotos con 4.941 vacas marcadas). Pesa 16,6 GB, pero Zenodo deja bajar pedazos del zip, así que se extraen solo unas 40 fotos. La demo dice en pantalla que son fotos de ejemplo, no de ese lote.
- **El análisis.** Herramienta `analyze_drone_photos`. Vacas: SAM 3.1, el mismo modelo de Meta que ya mide el agua en las fotos aéreas (E3, SPEC-18), ahora devolviendo cada vaca como objeto para contarlas, sin contar dos veces la misma vaca. Pasto y cultivo: cobertura verde con un índice de color (ExG − ExR), sin ningún modelo, para que el número sea reproducible. El conteo entra al plan como cabezas del rodeo (`cow_herd_heads`, SPEC-30), siempre después de preguntar: "Conté 377 vacas. ¿Uso 377 en vez de 400?".
- **Dron de juguete (opcional, decidís vos).** Un Tello (unos 100 USD, se programa desde Python) no tiene GPS ni cámara hacia abajo: no puede volar una misión real. Sirve para un número de escenario: volar la misma "cortadora" a escala sobre un mapa impreso en el piso y contar vacas de juguete. Si lo comprás, va en una SPEC-47b chica.

## 3. Orden recomendado

1. **SPEC-46, satélite, primero.** Es dato real del lote, gratis, sin hardware, y mueve el plan de verdad (rinde → ventas, crédito, caja). Además el prototipo ya mostró que la fuente anda. Se apila sobre `spec-44-public-connector` (o sobre la planilla v2 si va antes).
2. **SPEC-47, dron, después,** apilada sobre la 46 porque tocan los mismos archivos. La parte de geometría y archivos de misión no gasta nada; el simulador corre en esta máquina; el conteo con SAM gasta créditos de Meta.
3. **E13**, la evaluación del conteo de vacas contra las marcas del dataset, recién cuando apruebes los créditos.

Las dos specs piden **no redesplegar** la app ni el servidor MCP antes del 10/11; las herramientas quedan listas para desplegar después.

## 4. Qué necesito de vos

- **Aprobar las dos specs** (o pedir cambios) para pasárselas a Antigravity.
- **Correr el simulador:** dejar que Antigravity ejecute `ArduCopter.elf` (si Windows Defender o SmartScreen pregunta, aprobarlo). No hay que instalar nada en C:.
- **Créditos de Meta para SAM:** la evaluación E13 son unas 60 llamadas (30 fotos × 2 conceptos), y la demo usa el caché para no gastar dos veces. Decime si va.
- **Elegir el lote de la demo satelital:** un lote de trigo de la zona núcleo que este año venga más flojo que lo normal. Tiene que ser público o con permiso del dueño, no un campo privado de un productor sin avisarle.
- **Tello: sí o no.** Nada más depende de esto.

Nada de esto pide cuentas nuevas, claves ni trámites.

## 5. Guiones de demo (resumen; el detalle está en cada spec)

- **Satélite:** dibujar el lote en el mapa → botón "Ver cómo viene el lote" → aparece el mapa verde-amarillo-rojo con la fecha de la imagen → en el chat: "¿Cómo viene el trigo?" → "Está 16 % menos verde que lo normal para esta fecha; si uso esa diferencia el rinde baja de 3,8 a 3,2 t/ha. ¿Rehago el plan?" → "Sí" → el plan cambia y todo sale verificado. Si no hay internet, responde la lectura guardada esa mañana. Los números de este guion son ilustrativos: la demo muestra lo que diga el satélite ese día.
- **Dron:** "Quiero contar las vacas con un dron" → la misión aparece dibujada sobre el potrero (pasadas, fotos, minutos, baterías) → se baja el `.waypoints` → en Mission Planner el dron simulado despega y recorre ese potrero → "Fotos del vuelo simulado" → recuadros numerados sobre cada vaca → "SAM contó 377; vos dijiste 400. ¿Uso 377?" → el plan cambia. Respaldo: el vuelo grabado de antemano.
- Cierre común: la foto de la factura dice cuánto gastaste; el satélite y el dron dicen cómo viene lo que tenés. En los tres casos el número lo mide una herramienta y DORA lo controla antes de decírtelo.

## Qué aprendimos

- **Un dato "real" no es automáticamente un dato correcto.** La fuente gratuita trae los metadatos contradictorios (el desplazamiento ya aplicado y declarado igual) y el NDVI salió imposible a la primera. El verificador de DORA no lo habría detectado: el 1,43 venía de una herramienta. Por eso la herramienta tiene sus propios controles (NDVI entre −1 y 1, píxeles suficientes) y un test fija la regla. Verificar de dónde sale un número no reemplaza verificar cómo se calculó.
- **Medir en el lugar correcto.** El porcentaje de nubes de la imagen entera engañaba en los dos sentidos. La medición tiene que hacerse sobre los píxeles del lote, no sobre el resumen del proveedor.
- **Medición no es predicción.** El satélite mide el verde; el rinde es una inferencia. El diseño lo separa: el NDVI es un dato, la propuesta de rinde es una regla con nombre que el productor confirma, y calibrarla contra los rindes de MAGyP por partido queda como experimento propio. Lo mismo con el dron: SAM cuenta vacas en fotos, y su error se mide en E13 contra un dataset con la respuesta, cosa que en producción nunca se tiene.
- **Lo más simple que se puede mostrar.** Para el dron, lo difícil no es volar sino planear la misión y convertir cientos de fotos en un número. Un simulador gratis y un dataset público alcanzan para probar las dos cosas sin comprar nada; el hardware se decide después.
- **Para agentes en empresas:** el patrón se repite con cualquier sensor. Hay una herramienta que mide, devuelve números con su fuente y su fecha, el agente propone pero pregunta antes de cambiar el plan, y el verificador exige que cada número tenga respaldo. Cambiar la factura por un satélite o un dron no cambia la arquitectura, solo suma herramientas.
