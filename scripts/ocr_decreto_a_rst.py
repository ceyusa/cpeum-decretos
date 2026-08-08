#!/usr/bin/env python3
"""Extrae el texto de un PDF escaneado (sin capa de texto) mediante OCR.

Pensado para los decretos del Diario Oficial de la Federación guardados
en `dof/`: rasteriza cada página con `pdftoppm`, la pasa por `tesseract`
y reordena los párrafos respetando el maquetado a dos columnas propio
del periódico. La salida es texto plano envuelto a 72 columnas, listo
para la revisión humana; el decreto se aplica a mano y no se persiste
en el repositorio.

Requiere los programas `pdftoppm` (poppler-utils) y `tesseract` con el
modelo de idioma español (`tesseract-ocr-spa`).

Nota: los renglones que abarcan las dos columnas (mobiliario y
encabezados de sección, como «DIARIO OFICIAL» o «PODER EJECUTIVO»)
actúan como separadores: el texto columnado entre dos de ellos se
emite primero con su columna izquierda y luego con la derecha.
"""

import argparse
import csv
import io
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ANCHO = 72
RESOLUCION = 300


def verificar_programas():
    """Comprueba que `pdftoppm` y `tesseract` estén disponibles."""
    faltantes = [p for p in ("pdftoppm", "tesseract") if not shutil.which(p)]
    if faltantes:
        print(f"error: faltan programas: {', '.join(faltantes)}", file=sys.stderr)
        raise SystemExit(1)


def rasterizar(pdf, directorio):
    """Rasteriza cada página del PDF a PNG y devuelve la lista de archivos."""
    prefijo = str(Path(directorio) / "pag")
    subprocess.run(
        ["pdftoppm", "-r", str(RESOLUCION), "-png", str(pdf), prefijo],
        check=True,
    )
    return sorted(Path(directorio).glob("pag-*.png"))


def ocr_tsv(png):
    """Pasa una página por tesseract y devuelve su salida TSV."""
    resultado = subprocess.run(
        ["tesseract", str(png), "stdout", "-l", "spa", "--psm", "3", "tsv"],
        check=True,
        capture_output=True,
        text=True,
    )
    return resultado.stdout


def parrafos_de_tsv(tsv):
    """Agrupa las palabras del TSV de tesseract en párrafos con su caja.

    Devuelve la pareja (párrafos, ancho de página). Cada párrafo es un
    diccionario con sus líneas (cada una, una lista de palabras) y su
    caja envolvente (x0, y0, x1, y1).
    """
    parrafos = {}
    ancho_pagina = 0
    # QUOTE_NONE: el texto reconocido puede contener comillas; con el
    # manejo de citas de csv éstas fundirían varias filas en una sola.
    for fila in csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(fila) != 12:
            continue
        if fila[0] == "1":
            ancho_pagina = int(fila[8])
            continue
        if fila[0] != "5" or not fila[11].strip():
            continue
        x0, y0 = int(fila[6]), int(fila[7])
        ancho, alto = int(fila[8]), int(fila[9])
        parrafo = parrafos.setdefault((fila[2], fila[3]), {"lineas": {}, "caja": None})
        linea = parrafo["lineas"].setdefault(fila[4], [])
        linea.append(fila[11])
        x1, y1 = x0 + ancho, y0 + alto
        caja = parrafo["caja"]
        parrafo["caja"] = (
            min(caja[0], x0) if caja else x0,
            min(caja[1], y0) if caja else y0,
            max(caja[2], x1) if caja else x1,
            max(caja[3], y1) if caja else y1,
        )
    return list(parrafos.values()), ancho_pagina


def ordenar_parrafos(parrafos, ancho_pagina):
    """Devuelve los párrafos de la página en orden de lectura.

    Si la página está a dos columnas, los renglones que cruzan el corte
    central (mobiliario y encabezados) delimitan secciones; dentro de
    cada sección se emite primero la columna izquierda y luego la
    derecha. Si no hay columnas, el orden es simplemente vertical.
    """
    corte = ancho_pagina / 2

    def es_izquierda(parrafo):
        return parrafo["caja"][2] <= corte

    def es_derecha(parrafo):
        return parrafo["caja"][0] >= corte

    por_altura = sorted(parrafos, key=lambda p: p["caja"][1])
    izquierda = any(es_izquierda(p) for p in por_altura)
    derecha = any(es_derecha(p) for p in por_altura)
    if not (izquierda and derecha):
        return por_altura

    ordenados = []
    pendientes = []
    for parrafo in por_altura:
        if es_izquierda(parrafo) or es_derecha(parrafo):
            pendientes.append(parrafo)
            continue
        ordenados.extend(p for p in pendientes if es_izquierda(p))
        ordenados.extend(p for p in pendientes if es_derecha(p))
        pendientes.clear()
        ordenados.append(parrafo)
    ordenados.extend(p for p in pendientes if es_izquierda(p))
    ordenados.extend(p for p in pendientes if es_derecha(p))
    return ordenados


def unir_lineas(lineas):
    """Une las líneas de un párrafo, quitando el guionado de fin de línea."""
    texto = ""
    for palabras in lineas:
        linea = " ".join(palabras).strip()
        if not linea:
            continue
        if texto.endswith("-") and linea[0].islower():
            texto = texto[:-1] + linea
        elif texto:
            texto += " " + linea
        else:
            texto = linea
    return texto


def normalizar(parrafo):
    """Colapsa los espacios en blanco de un párrafo."""
    return re.sub(r"\s+", " ", parrafo).strip()


def unir_continuaciones(parrafos):
    """Une los párrafos partidos por un salto de columna o de página.

    Un párrafo que no termina en puntuación y al que sigue otro que
    empieza en minúscula es una continuación del anterior.
    """
    unidos = []
    for parrafo in parrafos:
        if (
            unidos
            and not re.search(r'[.!?:;"»)]$', unidos[-1])
            and re.match(r"[a-záéíóúñü]", parrafo)
        ):
            unidos[-1] += " " + parrafo
        else:
            unidos.append(parrafo)
    return unidos


def envolver(texto):
    """Refluye un párrafo a un ancho máximo de `ANCHO` caracteres."""
    return textwrap.fill(texto, width=ANCHO)


def texto_de_pdf(pdf):
    """Extrae los párrafos de todo el PDF en orden de lectura."""
    verificar_programas()
    parrafos = []
    with tempfile.TemporaryDirectory() as directorio:
        for png in rasterizar(pdf, directorio):
            pagina, ancho_pagina = parrafos_de_tsv(ocr_tsv(png))
            for parrafo in ordenar_parrafos(pagina, ancho_pagina):
                texto = normalizar(unir_lineas(parrafo["lineas"].values()))
                if texto:
                    parrafos.append(texto)
    return unir_continuaciones(parrafos)


def main():
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(
        description="Extrae el texto de un PDF escaneado mediante OCR."
    )
    parser.add_argument("pdf", type=Path, help="ruta del PDF escaneado")
    parser.add_argument(
        "-o",
        "--salida",
        type=Path,
        default=None,
        help="archivo de salida (por omisión: la salida estándar)",
    )
    args = parser.parse_args()

    parrafos = texto_de_pdf(args.pdf)
    texto = "\n\n".join(envolver(p) for p in parrafos) + "\n"
    if args.salida:
        args.salida.write_text(texto, encoding="utf-8")
        print(f"{len(parrafos)} párrafos escritos en {args.salida}")
    else:
        print(texto, end="")


if __name__ == "__main__":
    main()
