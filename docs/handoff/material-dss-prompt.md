# Prompt para Antigravity: convertir Dorfman, Samuelson y Solow en material de modelado (bilingüe)

**No es código de DORA.** Es lectura y escritura. No toques `D:\projects\dora-main`.

## El libro
Dorfman, Samuelson y Solow, *Linear Programming and Economic Analysis* (McGraw-Hill, 1958). Es un PDF escaneado de 538 páginas, sin texto:
- `D:\Material Clases\Operaciones\Dorfman-Samuelson-Solow-Linear-Programming-and-Economic-Analysis.pdf`
- copia local en `D:\projects\dora-hackathon\.claude\worktrees\keen-wilson-695e01\material-privado\` (ignorada por git).

**Tiene derechos de autor.**
- No copies párrafos ni transcribas el libro entero dentro del repositorio.
- Lo que escribís son notas propias: resúmenes, el método explicado con tus palabras, y los ejemplos reformulados con sus números, citando capítulo y página.
- Las citas textuales, si hacen falta, de menos de dos renglones.

## Dónde escribís
En la carpeta `D:\projects\dora-hackathon\.claude\worktrees\keen-wilson-695e01\docs\material\dss\`. Ahí no hay nada más. **No edites ningún otro archivo de ese worktree.** No hagas commit: Claude revisa y commitea.

## Qué se busca
Tres usos, en este orden de importancia:
1. **La receta de modelado.** Cómo pasar de un problema económico a un programa lineal: actividades, ítems, coeficientes, restricciones, función objetivo, y cómo leer los precios sombra. Nos sirve para tres cosas:
   - **la guía del agente de DORA:** el modelo de lenguaje llena un escenario y el código arma el programa;
   - **los "paquetes de dominio":** agro, aserradero, transporte;
   - **un analista humano que aprende.**

   Ya hicimos lo mismo con el libro de Tow: leé `docs/investigacion/2026-11-08-material-tow-curso.md` y su método de los cinco pasos.
2. **El catálogo de ejemplos**, cada uno con su planteo, para convertirlos en casos de prueba (SPEC-48) y en ejercicios de curso.
3. **Material de divulgación en español y en inglés** para M2M Labs (sección Economics): ideas que se puedan explicar en un video corto o en un post.

## Archivos que tenés que entregar
1. **`00-indice.md`:** el índice del libro (capítulos y páginas) y, por capítulo, tres renglones sobre qué tiene y si sirve para la receta, para ejemplos o para divulgación.
2. **`01-receta-de-modelado.es.md` y `01-modeling-recipe.en.md`:** el método del libro para armar un modelo, paso a paso, comparado con los cinco pasos de Tow:
   - qué agrega Dorfman, Samuelson y Solow;
   - en qué coinciden;
   - qué errores de modelado típicos señalan.

   Escrito para que lo use un agente: una lista ordenada de pasos y de chequeos ("¿cada ítem tiene su ecuación de balance?", "¿las unidades de cada fila son las mismas?").
3. **`02-ejemplos.jsonl`:** un objeto por ejemplo o ejercicio del libro, con estos campos:
   - `id`, `capitulo`, `pagina`, `tema` (producción, dieta, transporte, insumo-producto de Leontief, teoría de juegos, crecimiento, equilibrio, bienestar…), `dominio` (agro, industria, transporte, macro…);
   - `enunciado_es` y `statement_en`, reformulados con tus palabras y con todos los números;
   - `variables`, `restricciones` y `objetivo`, en notación simple;
   - `solucion_libro`, si el libro la da (valores y página);
   - `dificultad` (1 a 3);
   - `sirve_para`: `caso_de_prueba`, `curso` y/o `divulgacion`.

   Si un ejemplo no tiene todos los números, marcalo `incompleto: true` y no inventes nada.
4. **`03-dualidad-y-precios.es.md` y `03-duality-and-prices.en.md`:** cómo explica el libro los precios sombra, la imputación de valor a los recursos y la relación con los precios de mercado. Es la parte que DORA usa para explicar el plan.
5. **`04-ideas-divulgacion.md`:** entre 10 y 15 ideas cortas, cada una con:
   - un título en español y en inglés;
   - qué concepto explica;
   - qué ejemplo del libro usa;
   - qué visual se puede animar (por ejemplo con Manim: región factible, simplex, precio sombra, Leontief);
   - cómo se conecta con un agente local con modelos baratos que resuelve el problema con seguridad para la empresa.
6. **`05-pendientes.md`:** las páginas que no se leyeron bien (escaneo malo, tablas cortadas) y las dudas.

## Cómo trabajar
- **Leé el PDF por partes** (por ejemplo, de a 30 o 40 páginas). Anotá en `05-pendientes.md` el rango ya leído, así se puede retomar si se corta.
- **Priorizá:** primero el índice; después los capítulos de planteo de modelos, producción, transporte y dualidad; al final insumo-producto, juegos, crecimiento y bienestar.
- **Si una tabla del libro no se lee con seguridad**, no la completes de memoria: marcala en pendientes.
- **Para cada ejemplo con solución en el libro**, si podés, verificá la solución con `scipy.optimize.linprog`. Corré Python desde `D:\projects\tools\venv`, nunca desde C:, y con scripts en una carpeta temporal fuera del repo. Anotá en el jsonl `verificado: true/false` y la diferencia. Así cada ejemplo sirve como caso de prueba confiable.
- **Costo:** cero. No uses servicios pagos. Ninguna clave en ningún archivo ni en la línea de comando.
- **Cuando termines**, avisá con un resumen corto:
  - cuántos capítulos leíste;
  - cuántos ejemplos encontraste;
  - cuántos verificaste;
  - qué quedó pendiente.

  Claude revisa una muestra y commitea.
