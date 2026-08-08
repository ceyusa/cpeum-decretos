#!/usr/bin/env python3
"""Re-fluye párrafos y enumeraciones de archivos reST a 72 caracteres por línea.

A diferencia de versiones anteriores, este script *no* re-construye la
estructura reST a mano con expresiones regulares, sino que deja que el parser
de ``docutils`` identifique los bloques de texto. A partir del árbol de
documentos generado por ``publish_doctree`` se recogen únicamente los
párrafos (``paragraph``) y se marca si son ítem de una enumeración (viven
dentro de una lista enumerada, de viñetas, de definición, etc.).

Cada párrafo se re-ajusta de forma *independiente* a un ancho máximo de
``ancho`` columnas, respetando la columna de inicio (sangría) de su primera
línea y, en las enumeraciones, la sangría de continuación tras el marcador.

Se ignoran (no se tocan) otros elementos: títulos, tablas, bloques de código
(literal), comentarios, directivas, transiciones, ``topic``/contenidos, etc.
Estos quedan fuera del conjunto de regiones a re-ajustar.

Los archivos se modifican *in situ*. El script sale con 0 si no hubo cambios
y con 1 si algún archivo fue modificado (comportamiento de un hook formateador
de pre-commit).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docutils import nodes
from docutils.core import publish_doctree

_DEFECTO_ANCHO = 72

# Tipos de bloque que se tratan como *contenedor de enumeración*: el párrafo
# dentro de alguno de ellos se re-ajusta respetando el marcador (romano,
# decimal, letra, ``#``) y su sangría.
_ENUM_CONTENEDOR = {
    "enumerated_list",
    "bullet_list",
    "definition_list",
    "field_list",
    "option_list",
    "list_item",
    "definition",
    "footnote",
    "citation",
}

# Tipos de bloque que se ignoran por completo (no se re-ajustan sus párrafos).
# ``title``/``table``/``literal_block``/``comment``/``system_message`` y demás.
_IGNORADO = {
    "title",
    "subtitle",
    "table",
    "literal_block",
    "doctest_block",
    "comment",
    "raw",
    "system_message",
    "transition",
    "figure",
    "image",
    "math_block",
    "line_block",
    "topic",
    "contents",
    "target",
    "substitution_definition",
}

# Marcador de ítem de enumeración: sangría + marcador (romano, decimal, letra
# o ``#``) terminado en ``.`` o ``)``.
_MARCADOR = re.compile(
    r"^(\s*)((?:[IVXLCDM]+|[ivxlcdm]+|[0-9]+|[A-Za-z]|#)[.)])(\s+|$)"
)


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


def _llenar(ancho: int, palabras: list[str]) -> list[str]:
    """Ajusta una lista de palabras a líneas de, a lo sumo, ``ancho``."""
    out: list[str] = []
    cur: list[str] = []
    largo = 0
    for palabra in palabras:
        if cur and largo + 1 + len(palabra) > ancho:
            out.append(" ".join(cur))
            cur = [palabra]
            largo = len(palabra)
        else:
            if cur:
                largo += 1
            cur.append(palabra)
            largo += len(palabra)
    if cur:
        out.append(" ".join(cur))
    return out


def _fluir_plano(lineas: list[str], ancho: int) -> list[str]:
    """Re-compone un párrafo plano respetando la sangría de su primera línea."""
    ident = _sangria(lineas[0])
    palabras = [p for ln in lineas for p in ln.strip().split()]
    if not palabras:
        return [lineas[0]]
    return [" " * ident + ln for ln in _llenar(ancho - ident, palabras)]


def _fluir_enumerado(lineas: list[str], ancho: int) -> list[str]:
    """Re-compone un ítem de enumeración conservando el marcador y sangría."""
    primera = lineas[0]
    m = _MARCADOR.match(primera)
    if not m:
        # Sin marcador reconocible (p. ej. lista numerada con ``[1]``): se
        # trata como párrafo plano.
        return _fluir_plano(lineas, ancho)
    ident = len(m.group(1))
    cabecera = m.group(2)
    resto = primera[m.end() :].split()
    for ln in lineas[1:]:
        resto.extend(ln.split())

    if len(lineas) == 1 or not resto:
        # Ítem de una sola línea: se conserva tal cual.
        return [primera]

    # La continuación se alinea tras el marcador (``ident + cabecera + 1``),
    # pero se respeta una sangría ya existente mayor (p. ej. apartados romanos
    # que se alinean verticalmente como ``IV.``/``V.``).
    continuacion = max(_sangria(lineas[1]), ident + len(cabecera) + 1)
    prefijo = " " * continuacion

    primero: list[str] = []
    largo = 0
    for palabra in resto:
        if largo + 1 + len(palabra) > ancho - ident - len(cabecera):
            break
        primero.append(palabra)
        largo += 1 + len(palabra)
    resto_l = resto[len(primero) :]

    salida = [" " * ident + cabecera]
    if primero:
        salida[0] += " " + " ".join(primero)
    salida.extend(prefijo + ln for ln in _llenar(ancho - continuacion, resto_l))
    return salida


def _fluir(lineas: list[str], ancho: int, es_enum: bool) -> list[str]:
    if es_enum:
        return _fluir_enumerado(lineas, ancho)
    return _fluir_plano(lineas, ancho)


def _recolectar(doc: nodes.document) -> tuple[list[tuple[int, bool]], set[int]]:
    """Recorre el árbol docutils.

    Devuelve:
    - ``parrafos``: lista de ``(línea, es_enumeración)`` para cada párrafo que
      debe re-ajustarse (línea 1-based).
    - ``otras``: conjunto de líneas de inicio de cualquier otro bloque
      (límites que cortan una región de párrafo).
    """
    parrafos: list[tuple[int, bool]] = []
    otras: set[int] = set()

    def _visit(node: nodes.Node, en_enum: bool, ignorado: bool) -> None:
        tn = type(node).__name__
        linea = getattr(node, "line", None)
        if linea is not None:
            otras.add(linea)
        if ignorado:
            for hijo in node.children:
                _visit(hijo, en_enum, True)
            return
        if tn == "paragraph":
            if linea is not None:
                parrafos.append((linea, en_enum))
            for hijo in node.children:
                _visit(hijo, en_enum, ignorado)
            return
        if tn in _IGNORADO:
            for hijo in node.children:
                _visit(hijo, en_enum, True)
            return
        es_enum_nuevo = en_enum or tn in _ENUM_CONTENEDOR
        for hijo in node.children:
            _visit(hijo, es_enum_nuevo, ignorado)

    _visit(doc, False, False)
    return parrafos, otras


def procesar(texto: str, ancho: int) -> str:
    """Re-fluye los párrafos del texto reST dado usando el parser de docutils."""
    lineas = texto.splitlines()
    doc = publish_doctree(
        texto,
        settings_overrides={
            "halt_level": 5,
            "report_level": 5,
            "file_insertion_enabled": False,
            "raw_enabled": False,
        },
    )
    parrafos, otras = _recolectar(doc)

    # Construye las regiones a re-ajustar.
    regiones: list[tuple[int, int, bool]] = []
    for linea, es_enum in parrafos:
        cab = linea - 1
        fin = cab
        while fin + 1 < len(lineas):
            nxt = fin + 1
            if not lineas[nxt].strip():
                break
            if nxt != cab and (nxt + 1) in otras:
                break
            fin = nxt
        regiones.append((cab, fin, es_enum))

    # Ordena por inicio y aplica de abajo hacia arriba para no desplazar
    # índices previos. Las regiones no se solapan (líneas en blanco entre sí).
    regiones.sort(reverse=True)
    nuevo = list(lineas)
    for cab, fin, es_enum in regiones:
        bloque = lineas[cab : fin + 1]
        nuevo[cab : fin + 1] = _fluir(bloque, ancho, es_enum)

    resultado = "\n".join(_colapsar_lineas_vacias(nuevo))
    if texto.endswith("\n"):
        resultado += "\n"
    return resultado


def _colapsar_lineas_vacias(lineas: list[str]) -> list[str]:
    """Colapsa dos o más líneas vacías consecutivas en una sola."""
    out: list[str] = []
    ultima_vacia = False
    for linea in lineas:
        vacia = not linea.strip()
        if vacia and ultima_vacia:
            continue
        out.append(linea)
        ultima_vacia = vacia
    return out


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: re-fluye los archivos indicados."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivos", nargs="*", type=Path)
    parser.add_argument(
        "--ancho",
        type=int,
        default=_DEFECTO_ANCHO,
        help="ancho máximo por línea",
    )
    args = parser.parse_args(argv)

    archivos = list(args.archivos)
    if not archivos:
        archivos = sorted(Path("CPEUM").glob("[T0-9]*.rst"))

    cambios = 0
    for path in archivos:
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        nuevo = procesar(original, args.ancho)
        if nuevo != original:
            path.write_text(nuevo, encoding="utf-8")
            cambios += 1
    if cambios:
        print(f"{cambios} archivo(s) re-ajustado(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
