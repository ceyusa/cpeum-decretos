# AGENTS.md

Este proyecto reconstruye el desarrollo legislativo de la Constitución Política
de los Estados Unidos Mexicanos (CPEUM) en formato `restructuredText` (sin
extensiones de Sphinx). Cada reforma Constitucional, desde 1917, está
representado como un `commit` en `git`.

## Fuente de información

La Constitución se ha reconstruido a partir de los decretos y otros cambios
Constitucionales registrados en
<https://www.diputados.gob.mx/LeyesBiblio/ref/cpeum_crono.htm>.

## Estructura del proyecto

- `CPEUM`: este directorio contiene los artículos de la Constitución en formato
  `rst`, cuyo nombre de archivo es el número del artículo. Además de
  `cpeum.rst`, que es la tabla de contenidos e incluye cada artículo.
  Finalmente, están los artículos transitorios, cuyos nombres de archivos
  comienzan con la letra `T` y el número de transitorio.
- `scripts`: scripts en bash o Python para automatizar diferentes
  tareas identificadas en este proyecto.
- `dof`: directorio donde se almacenan los documentos originales digitalizados
  del Diario Oficial de la Federación.

## Scripts

Los scripts serán de preferencia en Python, aunque, si son muy simples, entonces
se prefiere en Bash.

### Uso de Python

Python se usa a través de un entorno virtual controlado con `uv`. El archivo
`pyproject.toml` describe las dependencias actuales.

Todos los scripts en Python no deben tener ningún problema detectado por `ruff`
y `pylint`.

- **Linting:** `uv run ruff check scripts/*.py*`
- **Formateo:** `uv run ruff format scripts/*.py*`
- **Pylint:** `uv run pylint scripts/*.py*`

### Bash

Usar `shellcheck` para validar los scripts en bash.

## pre-commit

El proyecto utiliza `pre-commit` para realizar revisiones automáticas a cada
commit.

## Ortografía

Para revisar la ortografía se utiliza `pyspelling`:

```bash
uv run pyspelling -n ortografia
```

Las palabras no reconocidas se añaden al final de archivo `es-local.txt` y se
ejecuta el script `uv run scripts/corregir_diccionario.py` para procesar el
directorio. Las palabras que se añaden pueden ser nombres propios o *palabras
correctas* pero no registradas.

## Validación del formato `restructuredText`

Para validar que el formato de los archivos en `rst` sea correcto se usa
`rstcheck`.

```bash
uv run rstcheck CPEUM/*.rst
```

Para reajustar la longitud de las líneas (reflow) a 72 caracteres, se usa `uv
run scripts/reajustar_rst.py --ancho 72 <file.rst>`, que está incluído en el
pre-commit.

## Formato del mensajes de `commit`

*No* utilizar la especificación de `conventional commits`. En cambio, si
cambia algo en los `css`, el prefijo es `css`. Si cambia algo en los
`scripts`, el prefijo es `scripts`.

Reglas generales de formato del mensaje:

- El **cuerpo** (todo el mensaje salvo el asunto) se re-ajusta a **80
  caracteres por línea**.
- Se **conservan intactas**: la primera línea (asunto), las líneas
  `Presidente …` y `Publicado en el Diario Oficial de la Federación el …`,
  y los encabezados de lista `Se …:`.
- Las **URLs del Diario Oficial de la Federación** apuntan siempre a
  `https://www.dof.gob.mx` (con `https` y subdominio `www`), en su propia
  línea y **sin partir** aunque superen 80 caracteres.

### Decretos y cambios Constitucionales

El formato del mensaje de `commit` para cambios y Decretos
Constitucionales tiene el siguiente formato:

```text
  Artículo[s] <lista con el número de artículo de los artículos
  modificados>

  DECRETO con el que … <resumen del decreto incluido en el Decreto>.

  President[e,a] Nombre del Presidente de la República que firmó el
  Decreto

  Publicado en el Diario Oficial de la Federación el <fecha de
  publicación en formato `[día] del [mes] del [año]`>
  <url del Diario Oficial de la Federación (dof) con el Decreto>

  <Explicación opcional del decreto incluido en la página del Congreso>
  <Lista de cambios realizados por artículo>
```

## Artículos transitorios

Cada reforma con artículos transitorios se almacena en un archivo
`CPEUM/T<NNN>.rst`, donde `NNN` es el número de decreto (los transitorios
constitucionales originales de 1917 van en `CPEUM/T000.rst`). Un archivo por
decreto; se referencian en `CPEUM/cpeum.rst` mediante `.. include::`.

Reglas de los encabezados de los artículos transitorios:

- Cada artículo usa la forma `**Artículo transitorio <número en
  palabra>**`, con el numeral en **palabra** (no en numeral arábigo).
- Si el decreto tiene **un solo** transitorio, se usa
  `**Artículo transitorio único**`.
- Si tiene varios, se numeran en orden ordinal: `primero`, `segundo`,
  `tercero`, …, y para 11-19 la convención del proyecto es
  `décimo primero`, `décimo segundo`, …, `décimo noveno`; continúa
  `vigésimo`, `vigésimo primero`, etc.
- El orden numérico corresponde a la posición del artículo dentro del
  archivo del decreto.
