# Regresión visual

Dos scripts para comparar cómo se ve una página antes y después de un cambio.
`capture.mjs` fotografía una URL completa en tres anchos (375, 768 y 1440 px),
recorriéndola de arriba abajo en tiras, y guarda además un volcado del árbol de
accesibilidad. `diff.mjs` compara dos capturas tira por tira.

## Cuándo usarlos

Antes de tocar algo compartido —CSS global, el layout, el header, el footer, un
componente que usan varias páginas—, porque ahí es fácil romper una página
arreglando otra. Para un cambio de texto en una sola página no hace falta.

## Cómo

Se captura el "antes" contra producción, se hace el cambio, se despliega y se
captura el "después":

```sh
node tools/visual-regression/capture.mjs https://www.qpaypro.com/gt/precios /tmp/vr/antes
# …hacer el cambio y desplegarlo…
node tools/visual-regression/capture.mjs https://www.qpaypro.com/gt/precios /tmp/vr/despues
node tools/visual-regression/diff.mjs /tmp/vr/antes /tmp/vr/despues
```

Las capturas van fuera del repo, a una carpeta temporal. **No se versionan.**

## Por qué no hay fotos guardadas

Las hubo: 19 páginas, 545 archivos, 90 MB. El problema es que una foto guardada
envejece con el primer cambio de contenido, y nadie vuelve a actualizarla. Para
julio de 2026, 18 de las 19 eran anteriores a la reestructura multipaís, así que
cualquier comparación marcaba las 18 y había que revisarlas a mano para
descubrir que todas las diferencias eran intencionales. Una herramienta que
siempre dice "cambió todo" no dice nada.

Capturar el "antes" en el momento evita eso: la referencia es siempre el estado
real de producción, y no hay 90 MB de imágenes que mantener. Si alguna vez se
necesitan las viejas, están en el historial de git, antes de que se borraran.

## Al leer el resultado

- Las tiras se emparejan por índice, no por posición de scroll. Si la página
  creció o encogió aunque sea unos píxeles, todas las tiras de abajo salen
  desalineadas y marcadas, aunque el contenido esté bien. Una tira marcada es
  "andá a mirarla", no "hay un error".
- Las animaciones en bucle (los orbes decorativos, el cubo) nunca coinciden
  entre dos capturas independientes. Es ruido esperado.
- El diff del árbol de accesibilidad es texto y suele ser más útil que los
  píxeles para saber *qué* cambió: enlaces, encabezados y etiquetas aparecen
  con su valor viejo y nuevo.
