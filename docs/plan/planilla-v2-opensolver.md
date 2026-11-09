# Planilla v2: el problema entero adentro, OpenSolver y un menú DORA (diseño, 7/11/2026)

Spec: [SPEC-45](../specs/SPEC-45-spreadsheet-v2.md). Prompt para Antigravity: [spec-45-prompt.md](../handoff/spec-45-prompt.md).

## La idea (de Guillermo)

La planilla de la SPEC-42 ya le da al productor el plan, la caja quincena por quincena y de dónde sale cada número. Pero las decisiones de DORA están como valores fijos: si cambia un precio, se mueven los márgenes y el plan no. Guillermo probó en Google Sheets el complemento OpenSolver, que funciona como el Solver de Excel que usaba en Arauco para los aserraderos, y propuso que la planilla traiga el problema ya armado, para volver a optimizar ahí mismo, con un menú para hablar con DORA.

## Qué se puede y qué no

- **El problema entra cómodo.** Lo medí con los datos de siempre: zona núcleo con 2.000 ha da 196 variables, 181 restricciones y 598 coeficientes distintos de cero. En una hoja es una grilla de 181 × 196, casi toda vacía.
- **Excel trae su propio Solver, pero tiene un tope de 200 variables.** DORA está en el borde y lo pasa en cuanto hay ganado, opciones de acopio o rutas. Por eso la planilla recomienda **OpenSolver**, que no tiene tope (en Excel usa CBC, en Sheets el solver de Google), es gratis y de código abierto.
- **Un archivo no puede abrir un complemento solo.** Cada usuario instala OpenSolver una vez. Lo que sí se puede es dejar el modelo **ya cargado**: en Excel con los nombres ocultos que leen el Solver y OpenSolver. Cómo lo guarda OpenSolver en Sheets todavía no se sabe, y es lo primero que se prueba (paso 0, con una planilla mínima que sube Guillermo).
- **Un `.xlsx` no puede llevar un menú.** El menú DORA vive en una **planilla plantilla de Google con su script**. El enlace "hacer una copia" copia también el script, así que el productor tiene el menú sin instalar nada y sin que haya que publicar un complemento en el Marketplace, que exige la revisión de Google. La primera vez, Google muestra el aviso "app no verificada" y hay que hacer un clic en "Configuración avanzada". Se dice tal cual.

## Cómo queda

1. **Fase A (gratis):** la hoja **Modelo** con el problema entero: variables, objetivo y restricciones, donde cada coeficiente que depende de un supuesto es una fórmula atada a la hoja **Supuestos**. Se suman además una hoja de **estrategia de venta** (cuándo, cuánto y por dónde vender) y una **verificación visible**: qué modelo de lenguaje armó el escenario, la fecha y los controles explicados con palabras. Seis planillas de ejemplo para que Guillermo las pruebe ya.
2. **Fase B (gratis):** la plantilla de Google con el menú DORA (Cargar plan, Recalcular con DORA, Volver al plan de DORA, ¿Qué cambié?), una ruta HTTP simple en el servidor y, en la app, el botón "Abrir en Google Sheets" con un código del plan para pegar.
3. **Fase C (con permiso para gastar):** una planilla por cada modelo certificado, armada con el escenario que construyó cada uno, y un caso descartado (el modelo barato solo, sin DORA, con sus números sin respaldo marcados en rojo).

## El test que sostiene todo

El argumento de la demo es "no nos creas, resolvelo vos". Para poder decirlo, un test toma la planilla exportada, evalúa sus fórmulas, arma el problema con lo que hay en la hoja Modelo y lo resuelve con HiGHS **sin usar el motor de DORA**. Tiene que dar el mismo plan, y también después de cambiar precios, capital o rindes en Supuestos. Si un cambio no se puede reflejar con fórmulas, la planilla lo avisa en vez de aproximar. Y si el usuario resolvió por su cuenta, la hoja de Verificación pasa a rojo ("plan recalculado fuera de DORA, sin verificar") hasta que lo mande de vuelta.

## Orden

SPEC-46 (satélite, ya la tiene Antigravity), después la 45 en fases y después la 47 (dron). La 45 se apila sobre la 46 y la 47 sobre la 45. La evaluación del conteo de vacas de la SPEC-47 pasó a llamarse **E13**, porque E12 es el piloto del "mecánico de LLM" (su ficha está en `docs/investigacion/2026-11-07-mecanico-de-llm.md`, rama local `claude/keen-wilson-695e01`, sin subir).

## Qué necesita de Guillermo

- El **paso 0**: subir `lp-minimo.xlsx` a Sheets y fijarse si OpenSolver muestra el modelo cargado (5 minutos).
- Para la fase B: crear la plantilla en su Drive y pegar el script (los pasos van en el handoff).
- Para la fase C: aprobar el gasto en modelos.

## Qué aprendimos

- **La verificación más fuerte es la que no depende de nosotros.** El verificador de DORA controla de dónde sale cada número, pero el usuario igual tiene que confiar en DORA. Con el problema entero en la planilla, cualquiera lo resuelve con otro solver y compara. Pasamos de "confiá en el verificador" a "controlalo vos".
- **Medir antes de diseñar.** Contar las variables (196) mostró al toque que el problema entra en una hoja y que el Solver de Excel queda justo en el límite. Sin ese número la recomendación habría sido otra.
- **Las limitaciones de la plataforma definen la arquitectura.** Un archivo no lleva scripts, un complemento publicado exige revisión, y el enlace de copia arrastra el script. La solución salió de esas tres restricciones, no de una preferencia.
- **Decir lo que la planilla no puede.** Algunos coeficientes no se pueden escribir como fórmula exacta. En vez de aproximar, la planilla avisa "este cambio necesita a DORA". Es la misma regla de todo el proyecto: mejor un "no sé" con su motivo que un número sin respaldo.
