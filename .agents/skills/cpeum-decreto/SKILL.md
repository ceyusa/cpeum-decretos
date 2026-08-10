---
name: cpeum-decreto
description: Aplicar un decreto de reforma a la CPEUM. Usar cuando se pida procesar, aplicar o commitear el siguiente decreto (o un decreto específico) de metadata/decretos.json — descargar el PDF del DOF, extraer el texto (OCR si es imagen escaneada), verificar la transcripción, modificar los artículos en CPEUM/*.rst y crear el commit con el formato del proyecto.
---

# Aplicar un decreto de reforma a la CPEUM

Flujo completo para incorporar un decreto de `metadata/decretos.json` al
repositorio. Un decreto = un commit.

## 1. Identificar el decreto a procesar

- `metadata/decretos.json` es una lista ordenada del más reciente al más
  antiguo (`numero` 284 en `[0]`, el 1 al final). Se procesan en orden
  cronológico: **de `numero` menor a mayor**.
- Para saber cuál sigue, revisa el historial: `git log --oneline` y
  localiza el último decreto aplicado. El siguiente es el que tenga el
  `numero` inmediato mayor en `decretos.json`.
- Campos de cada entrada:
  - `numero`, `decreto` (encabezado oficial del DECRETO),
    `resumen` (puede ser `null`), `publicacion` (fecha ISO).
  - `imagen`: URL al PDF escaneado (decretos antiguos, sin capa de
    texto).
  - `pdf` / `word`: URL al PDF/DOC con texto (decretos modernos).
  - `erratas`, `aclaracion`: documentos complementarios (revisar si no
    son `null`).

## 2. Descargar el PDF a `dof/`

```bash
curl -L -o dof/$(basename <url>) <url imagen|pdf>
```

- Conserva el nombre de archivo de la URL (`CPEUM_ref_NNN_DDmmmAA_ima.pdf`
  o `CPEUM_ref_NNN_DDmmmAA.pdf`).
- Verifica que el archivo sea un PDF válido (`file dof/<archivo>`).

## 3. Extraer el texto

- **PDF escaneado (`imagen`)**: usar el script del proyecto:

  ```bash
  uv run scripts/ocr_decreto_a_rst.py dof/<pdf> -o /tmp/decreto_NNN.txt
  ```

  El OCR es ruidoso en tipografía antigua. Para verificar palabras
  dudosas, rasteriza a mayor resolución y re-OCR recortes:
  `pdftoppm -r 600 -png dof/<pdf> /tmp/pagina`.
- **Recuperar texto mezclado por columnas o texto fantasma**: el DOF
  antiguo es un periódico de 3 columnas y el decreto puede continuar
  **al inicio de la columna siguiente**, no abajo. La posición de la
  columna del decreto varía por edición (izquierda o derecha; hay
  páginas que solo traen el encabezado del periódico y listas de
  asistencia). Técnica:
  1. `tesseract /tmp/pagina-1.png /tmp/out -l spa tsv` para obtener
     coordenadas (columnas `left top width height` antes del texto).
  2. Localiza una palabra vecina legible en el TSV.
  3. Recorta la zona con `convert /tmp/pagina-1.png -crop WxH+X+Y
     /tmp/recorte.png` y re-OCR con `tesseract /tmp/recorte.png stdout
     -l spa --psm 6` (o `--psm 7` por línea; `-level 20%,80%` ayuda
     con texto tenue).
  4. **Palabra aislada**: si el recorte de línea completa es ambiguo,
     recorta solo la palabra dudosa y prueba `--psm 7`, `8` y `13`
     (con `-resize 300-400%`); las lecturas aisladas suelen ser
     limpias. Cuando las lecturas discrepen entre pases, decide por
     mayoría de evidencias y sentido gramatical.
  5. **Preproceso destructivo**: `-normalize` y `-adaptive-threshold`
     borran los glifos en escaneos tenues; usa solo el recorte crudo o
     `-level 25-40%,60-75%`.
  6. Las líneas tapadas por publicidad del reverso pueden ser
     irrecuperables: confírmalas con el repo paralelo (sección 4).
  7. Los decretos citan los textos reformados entre comillas: la `”`
     final tras el punto no forma parte del artículo.
- **PDF con capa de texto (`pdf`)**: `pdftotext -layout dof/<pdf>
  /tmp/decreto_NNN.txt` suele bastar.
- El texto extraído va a `/tmp/`; **no** se persiste en el repositorio.

## 4. Verificar la transcripción contra fuentes

Nunca confíes ciegamente en el OCR. Contrasta con:

- **Repo paralelo `ceyusa/cpeum`** (antes `ceyusa/constitucion-mexicana`, repo
  id 8904137, misma estructura y secuencia de commits que este proyecto): lo más
  cómodo es clonarlo una vez y navegarlo con git:

  ```bash
  git clone --filter=blob:none https://github.com/ceyusa/cpeum.git /tmp/cpeum-ref
  # commit del decreto siguiente al ya conocido <sha-prev>:
  git -C /tmp/cpeum-ref log --oneline --reverse --ancestry-path \
    <sha-prev>..main -- CPEUM/<NNN>.rst
  git -C /tmp/cpeum-ref diff <sha-prev> <sha-nuevo> -- CPEUM/
  ```

  El commit correcto tiene como padre el commit del decreto anterior.
  Alternativa sin clonar:
  `https://api.github.com/repositories/8904137/commits?path=CPEUM/<NNN>.rst`
  (ojo: con muchos commits la respuesta se trunca). Ojo: contiene **erratas
  humanas frecuentes** —palabras cambiadas (decreto 6: "ese" por "este";
  "XXXXIV" por "XXXIV"; decreto 7: inserta "Federal" en "Distrito y Territorios
  Federales"; decreto 8: "toda República" sin "la"; decreto 9: "sirviendo la
  línea" sin "de"), puntuación omitida (decreto 4: coma en "inmediato, el
  ciudadano"; decretos 6 y 9) y acentos añadidos (decreto 8: "Único" por
  "Unico")— y **puede omitir transitorios enteros** (decreto 7). El OCR del
  documento original manda. Documenta las erratas detectadas en `memory`
  (archivos `decreto-NNN.md`).

  Erratas humanas adicionales detectadas durante los decretos 50-55:

  - dec 50: "el uso que hubiese hecho **con la facultado** concedida" → OCR
    "**de la facultad** concedida".
  - dec 53: "todos los varones y mujeres" (añade "todos") → OCR "los varones y
    las mujeres".
  - dec 54: suprime "el petróleo y todos los carburos de hidrógeno" en el
    párrafo 4 del art 27.
  - dec 55: "bases siguiente" → "siguientes"; "empleados, domésticos" →
    "empleados domésticos"; "los derechos **de** este artículo les consagra" →
    "los derechos **que** este artículo les consagra". Otras (dec 22): el ref
    omitió la "s" ("mexicano"→"mexicanos"), confundió "Capitán" por "Capital" y
    empezó el transitorio en minúscula. Vigila también en los transitorios: el
    ref puede numerarlos/distribuirlos distinto (en palabra vs. arábigo) o
    desviarse del DOF en mayúsculas.

  Para decretos **grandes que reestructuran un artículo completo** (p.ej. el
  art 123 con Apartados A/B del dec 55), la forma más fiable es usar el
  **texto final del ref** en `CPEUM/<NNN>.rst` como base y luego aplicar las
  correcciones del OCR sobre él. Para comparar el contenido (más allá del
  re-ajuste de líneas), normaliza ambos a un solo espacio y usa `python3`
  (no el sandbox de code_execution, que no tiene `difflib`) contra archivos
  temporales en `/tmp`; así el Apartado A debe coincidir salvo por las
  erratas documentadas. No adoptes cambios de puntuación que introduzca el
  ref dentro del texto ya consolidado si el decreto no los modifica.

  Este proyecto **no** es oficial ni válido. Usarlo sólo como referencia.

### Fe de erratas (tablas Dice/Debe decir)

  Los decretos con `erratas` traen una tabla oficial con columnas **Dice** y
  **Debe decir**. Para confirmar que quedaron resueltas y en la dirección
  correcta: recorta cada fila por columna (localiza los encabezados 'Dice:' y
  'Debe decir:' en el TSV y usa sus `left` como separación de columnas) y
  re-OCR. **Determina bien cuál columna es** cada una; el ref/commits pueden
  haber aplicado una corrección en dirección **invertida** (p.ej. el Transitorio
  Octavo del dec 49: el commit añadió "el" pero la fe de erratas lo quitaba).
  Documenta en el commit la lista de erratas y su estado.

- **La fe de erratas se aplica como commit aparte**, después del main del
  decreto, preservando la secuencia histórica publicada (el decreto sale con
  el texto "equivocado" y la fe lo corrige después). El ref (ceyusa) suele
  **mezclar** la fe en su commit main; no lo imitas. El main lleva el texto
  tal como se publicó. Ejemplos: dec 64 (commit aparte, "presos"/"presas" en
  el art 73 fr XIII) y dec 88 ("Madera"→"Maderera").

- La fe de erratas puede cubrir **decretos vecinos** (la del dec 64 corregía
  partes del 65 y del Reglamento): esas correcciones quedan pendientes y solo
  se aplican al procesar ese decreto.

- Si la fe de erratas **no tiene codnota propio** del DOF (el crono de
  diputados solo enlaza la "Imagen"), usa la URL del DOF del decreto base, o
  el enlace al PDF de diputados (`CPEUM_fe_ref_NNN_..._ima.pdf`), por decisión
  del usuario.

- **SCJN**: PDF histórico por artículo
  `https://www.scjn.gob.mx/sites/default/files/cpeum/documento/2020-05/CPEUM-<NNN>.pdf`
  (bloquea curl; consúltalo vía websearch).

- mley.mx, justia, sedia de diputados como respaldo.

- El DOF original puede traer errores (*sic*); documentarlos en el commit cuando
  afecten la redacción (ej. decreto 2: dice "inciso I" del art. 72, pero es el
  inciso J).

## 5. Modificar los artículos en `CPEUM/`

Convenciones de formato (AGENTS.md):

- Los artículos **no** son secciones rst: título en negritas `**Artículo N.**`.
- Texto envuelto a **72 columnas** máximo.
- Incisos como listas con números romanos (`I.`, `II.`, …) con continuación
  alineada.
- Conserva la ortografía de época del decreto cuando el proyecto así lo ha hecho
  (revisar artículos ya reformados como referencia).
- Aplica solo lo que el decreto ordena: reformas, adiciones y derogaciones por
  artículo/fracción/inciso.

### Artículos transitorios del decreto

- Busca siempre la sección `TRANSITORIO`/`TRANSITORIOS` en el OCR (`grep -i
  transitorio /tmp/decreto_NNN.txt`): el repo paralelo puede haberla omitido.
- Numeral de cada transitorio: el original suele escribir `ARTÍCULO Nº`
  o `ARTÍCULO PRIMERO/1º`; se rinde `**Artículo transitorio N**`
  arábigo, pero si el original numera **en palabra** los escribes en
  palabra (dec 21: PRIMERO/SEGUNDO → `**Artículo transitorio primero**`).
  Dec 22 usa `1º/2º` → `**Artículo transitorio 1**/2`.
- Si el decreto tiene transitorios, continúan la numeración de los transitorios
  constitucionales de acuerdo con el número de decreto (`T000.rst` son los de
  1917): el decreto 5 usó `T005.rst`, el 6 `T006.rst`, etc. Un archivo por
  decreto, con encabezados `**Artículo transitorio N**` (o `**Artículo
  transitorio único**` si es uno solo). Si un decreto **no tiene transitorios**
  (p.ej. dec 53), no se crea archivo y la numeración salta ese número.
- En `CPEUM/cpeum.rst`, tras el `.. include::` del último transitorio, añade la
  sección:

  ```rst
  Artículos transitorios de decretos de reforma (<N de decreto>)
  -------------------------------------------------

  <encabezado oficial del DECRETO/LEY>

  .. include:: T0NN.rst
  ```

## 6. Validar

```bash
awk 'length > 72 {print FILENAME": "FNR}' CPEUM/<NNN>.rst
uv run rstcheck CPEUM/*.rst
```

- `pyspelling` corre solo vía pre-commit al commitear.
- El hook `line-length` puede marcar líneas largas **preexistentes** en
  `CPEUM/cpeum.rst`: ignorarlas, no son tuyas.

## 7. Commitear

Incluir en el commit los `CPEUM/*.rst` modificados, peron **no** el PDF en
`dof/`. Formato del mensaje (AGENTS.md; ver commits `a77c2f9`, `c5140a6`,
`8ccde8d` como modelo):

```text
Artículo[s] <lista de artículos modificados>

<encabezado del DECRETO, tomado del campo "decreto">

President[e,a] <nombre del presidente que firmó>

Publicado en el Diario Oficial de la Federación el <día> de <mes> de <año>
<url del DOF; para decretos antiguos:
 https://www.dof.gob.mx/nota_to_imagen_fs.php?codnota=<id>&fecha=DD/MM/AAAA&cod_diario=<id>>

<resumen del decreto (campo "resumen" o redactado)>

Se reforman:            (o "Se adicionan:", etc., según el decreto)

+ el artículo N
+ el artículo M
```

- La URL `nota_to_imagen_fs.php` se construye desde la página del
  decreto en diputados.gob.mx (también aparece en el commit
  equivalente de `ceyusa/cpeum`); verifica que responda antes de
  usarla: redirige 302 a https y su certificado falla con curl
  (verificar con `curl -sk -o /dev/null -w '%{http_code}'`, debe dar
  200).
  Ojo: el servidor del DOF devuelve respuestas **transitorias** 301/403
  a curl (aun URLs previamente verificadas 200 pueden pasar a 301 en
  otra llamada). Si el `codnota` proviene del commit del ref, la URL es
  la correcta aunque ahora devuelva 3xx/403; no la cambies.
- Fecha en el mensaje: sigue el estilo de los commits previos
  ("el 24 de enero del 1928").
- Limpia el campo `resumen` de espacios y artefactos antes de
  incluirlo en el mensaje.
- No usar conventional commits; sin prefijos para decretos.
- Verifica que los hooks de pre-commit pasen; si `pyspelling` falla por
  palabras nuevas, agrégalas a `es-local.txt` y corre
  `uv run scripts/corregir_diccionario.py` (p.ej. "constituídas" en el
  dec 54 e "intersindicales" en el dec 55). Incluye en el commit tanto
  los `CPEUM/*.rst` modificados como el `es-local.txt` (y `T0NN.rst` si
  el decreto tiene transitorios).

## Notas

- Trabaja con `todo_write`: un paso por etapa (descargar, OCR,
  verificar, editar, validar+commitear).
- Los decretos con `erratas` o `aclaracion` pueden requerir commits o
  ajustes adicionales: consúltalos antes de editar.
