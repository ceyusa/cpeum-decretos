#!/usr/bin/env python3
"""Convierte el PDF de la Constitución de 1917 (`dof/CPEUM_orig_05feb1917.pdf`)
en archivos reStructuredText, uno por artículo, en el directorio `CPEUM`.

El PDF tiene capa de texto y un maquetado de periódico a tres columnas, por lo
que la extracción se hace por coordenadas con PyMuPDF: se descarta el
mobiliario (encabezado y pie del periódico) y se ordenan los bloques por
columna y posición vertical para reconstruir el orden de lectura.
"""

import argparse
import re
import sys
import textwrap
from pathlib import Path

import pymupdf

MARGEN_SUPERIOR = 45.0
MARGEN_INFERIOR = 745.0
MARGEN_PORTADA = 150.0
CORTES_COLUMNA = (219.5, 393.5)

ARTICULO_RE = re.compile(r"^Art\.\s*(\d+)o?\.\-\s*")
TITULO_RE = re.compile(r"^TITULO\s+\w+\.$")
CAPITULO_RE = re.compile(r"^CAPITULO\s+[IVX]+\.$")
SECCION_RE = re.compile(r"^SECCION\s+[IVX]+\.$")
TRANSITORIOS_RE = re.compile(r"^ARTÍCULOS TRANSITORIOS\.$")
CIERRE_RE = re.compile(r"^Dada en el Salón de Sesiones")
INCISO_RE = re.compile(r"^(\d+[oa]|[IVXLC]+|[A-Z])\.-\s+")

NUM_ARTICULOS = 136


def es_texto_espaciado(texto):
    """El mobiliario de la portada lleva las letras separadas por espacios."""
    palabras = texto.split()
    if not palabras:
        return False
    sueltas = sum(1 for palabra in palabras if len(palabra) == 1)
    return sueltas / len(palabras) > 0.7


def bloques_de_pagina(pagina):
    """Bloques de texto de una página, sin el mobiliario del periódico."""
    margen_superior = MARGEN_PORTADA if pagina.number == 0 else MARGEN_SUPERIOR
    bloques = []
    for x0, y0, x1, y1, texto, *_ in pagina.get_text("blocks"):
        if not texto.strip():
            continue
        if y0 < margen_superior or y0 > MARGEN_INFERIOR:
            continue
        if es_texto_espaciado(texto):
            continue
        bloques.append((x0, y0, x1, y1, texto))
    return bloques


def columna_de(bloque):
    """Columna (0, 1 o 2) a la que pertenece un bloque, según su centro."""
    x0, _, x1, _, _ = bloque
    centro = (x0 + x1) / 2
    if centro < CORTES_COLUMNA[0]:
        return 0
    if centro < CORTES_COLUMNA[1]:
        return 1
    return 2


def parrafos_de_pagina(pagina):
    """Párrafos de la página en orden de lectura: columna y luego vertical."""
    bloques = bloques_de_pagina(pagina)
    bloques.sort(key=lambda b: (columna_de(b), b[1]))
    return [texto for _, _, _, _, texto in bloques]


def texto_continuo(pdf):
    """Párrafos de todo el documento en orden de lectura."""
    parrafos = []
    for pagina in pdf:
        parrafos.extend(parrafos_de_pagina(pagina))
    return parrafos


def normalizar(parrafo):
    """Une las líneas de un párrafo y colapsa los espacios en blanco."""
    texto = " ".join(linea.strip() for linea in parrafo.splitlines())
    return re.sub(r"\s+", " ", texto).strip()


def unir_continuaciones(parrafos):
    """Une los párrafos partidos por un salto de columna o de página.

    Un párrafo que no termina en puntuación y al que sigue otro que
    empieza en minúscula es una continuación del anterior.
    """
    unidos = []
    for parrafo in parrafos:
        texto = normalizar(parrafo)
        if not texto:
            continue
        if (
            unidos
            and not re.search(r'[.!?:;"»)]$', unidos[-1])
            and re.match(r"[a-záéíóúñü]", texto)
        ):
            unidos[-1] += " " + texto
        else:
            unidos.append(texto)
    return unidos


def es_epigrafe(texto):
    """Un epígrafe es un renglón corto escrito completamente en mayúsculas."""
    return (
        len(texto) < 70 and texto == texto.upper() and any(c.isalpha() for c in texto)
    )


def clasificar_encabezado(texto, seccion, ultimo_encabezado):
    """Clasifica un renglón de encabezado y devuelve la sección actualizada.

    Devuelve la pareja (sección, tipo de encabezado) si el renglón es un
    encabezado, o None en caso contrario. El nombre o descripción que
    sigue a un título, capítulo o sección se une al propio encabezado,
    no al epígrafe.
    """
    seccion = dict(seccion)
    if TITULO_RE.match(texto):
        return {"titulo": texto}, "titulo"
    if CAPITULO_RE.match(texto):
        seccion["capitulo"] = texto
        seccion.pop("epigrafe", None)
        return seccion, "capitulo"
    if SECCION_RE.match(texto):
        seccion["epigrafe"] = texto
        return seccion, "epigrafe"
    if "titulo" in seccion and es_epigrafe(texto):
        if ultimo_encabezado in ("titulo", "capitulo"):
            seccion[ultimo_encabezado] += f" {texto}"
            return seccion, ultimo_encabezado
        anterior = seccion.get("epigrafe")
        seccion["epigrafe"] = f"{anterior} {texto}" if anterior else texto
        return seccion, "epigrafe"
    return None


def segmentar(parrafos):
    """Divide los párrafos en preámbulo, artículos, transitorios y cierre.

    Devuelve un diccionario con el preámbulo del decreto, la lista de
    artículos y de transitorios (cada uno con su número, su contexto de
    sección y sus párrafos) y los párrafos de cierre (firmas y fórmulas).
    """
    documento = {
        "preambulo": [],
        "articulos": [],
        "transitorios": [],
        "cierre": [],
    }
    seccion = {}
    actual = None
    ultimo_encabezado = None
    en_transitorios = False
    en_cierre = False

    for texto in unir_continuaciones(parrafos):
        if re.fullmatch(r"_+", texto):
            continue
        if CIERRE_RE.match(texto):
            en_cierre = True
            actual = None
        if en_cierre:
            documento["cierre"].append(texto)
            continue

        inicio = ARTICULO_RE.match(texto)
        if inicio:
            numero = int(inicio.group(1))
            actual = {
                "numero": numero,
                "seccion": dict(seccion),
                "parrafos": [ARTICULO_RE.sub("", texto)],
            }
            clave = "transitorios" if en_transitorios else "articulos"
            documento[clave].append(actual)
            ultimo_encabezado = None
            continue

        if TRANSITORIOS_RE.match(texto):
            en_transitorios = True
            actual = None
            seccion = {}
            ultimo_encabezado = None
            continue

        encabezado = clasificar_encabezado(texto, seccion, ultimo_encabezado)
        if encabezado:
            seccion, ultimo_encabezado = encabezado
            actual = None
            continue

        if actual is None:
            documento["preambulo"].append(texto)
        else:
            actual["parrafos"].append(texto)

    return documento


def validar(documento):
    """Verifica que no falte ni sobre ningún artículo y que haya texto."""
    errores = []
    numeros = [a["numero"] for a in documento["articulos"]]
    if numeros != list(range(1, NUM_ARTICULOS + 1)):
        errores.append(f"artículos incompletos o desordenados: {numeros}")
    transitorios = [a["numero"] for a in documento["transitorios"]]
    if not transitorios or transitorios != list(range(1, len(transitorios) + 1)):
        errores.append(f"transitorios incompletos o desordenados: {transitorios}")
    for articulo in documento["articulos"] + documento["transitorios"]:
        if not any(p.strip() for p in articulo["parrafos"]):
            errores.append(f"artículo {articulo['numero']} sin texto")
        for parrafo in articulo["parrafos"]:
            if TITULO_RE.match(parrafo) or CAPITULO_RE.match(parrafo):
                errores.append(
                    f"encabezado dentro del artículo {articulo['numero']}: {parrafo}"
                )
    if not documento["preambulo"]:
        errores.append("preámbulo vacío")
    if errores:
        for error in errores:
            print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)


def titulo_rst(texto):
    """El título del documento, con adorno de `=` encima y debajo."""
    adorno = "=" * len(texto)
    return f"{adorno}\n{texto}\n{adorno}"


def subtitulo_rst(texto, adorno):
    """Un encabezado de sección subrayado con el adorno dado."""
    return f"{texto}\n{adorno * len(texto)}"


PALABRAS_ENCABEZADO = {
    "CAPITULO": "Capítulo",
    "CIUDADANOS": "Ciudadanos",
    "COMISION": "Comisión",
    "CONGRESO": "Congreso",
    "CONSTITUCION": "Constitución",
    "CUARTO": "Cuarto",
    "DE": "de",
    "DEL": "del",
    "DIVISION": "División",
    "E": "e",
    "EJECUTIVO": "Ejecutivo",
    "ELECCION": "Elección",
    "ESTADOS": "Estados",
    "EXTRANJEROS": "Extranjeros",
    "FACULTADES": "Facultades",
    "FEDERACION": "Federación",
    "FORMA": "Forma",
    "FORMACION": "Formación",
    "FUNCIONARIOS": "Funcionarios",
    "GARANTIAS": "Garantías",
    "GENERALES": "Generales",
    "GOBIERNO": "Gobierno",
    "INDIVIDUALES": "Individuales",
    "INICIATIVA": "Iniciativa",
    "INSTALACION": "Instalación",
    "INTEGRANTES": "Integrantes",
    "INVIOLABILIDAD": "Inviolabilidad",
    "JUDICIAL": "Judicial",
    "LA": "la",
    "LAS": "las",
    "LEGISLATIVO": "Legislativo",
    "LEYES": "Leyes",
    "LOS": "los",
    "MEXICANOS": "Mexicanos",
    "NACIONAL": "Nacional",
    "NOVENO": "Noveno",
    "OCTAVO": "Octavo",
    "PARTES": "Partes",
    "PERMANENTE": "Permanente",
    "PODER": "Poder",
    "PODERES": "Poderes",
    "PREVENCIONES": "Prevenciones",
    "PREVISION": "Previsión",
    "PRIMERO": "Primero",
    "PÚBLICOS": "Públicos",
    "QUINTO": "Quinto",
    "REFORMAS": "Reformas",
    "RESPONSABILIDADES": "Responsabilidades",
    "SECCION": "Sección",
    "SEGUNDO": "Segundo",
    "SEPTIMO": "Séptimo",
    "SEXTO": "Sexto",
    "SOBERANÍA": "Soberanía",
    "SOCIAL": "Social",
    "TERCERO": "Tercero",
    "TERRITORIO": "Territorio",
    "TITULO": "Título",
    "TRABAJO": "Trabajo",
    "Y": "y",
}


def titular(texto):
    """Convierte un encabezado en mayúsculas a tipo título con acentos.

    Las conjunciones y preposiciones (de, del, la, las, los, y, e) van en
    minúsculas y los numerales romanos se conservan. La primera palabra
    del encabezado y la que sigue a un punto (inicio de la descripción)
    van con mayúscula inicial. Falla si aparece una palabra desconocida,
    para no perder acentos por omisión.
    """
    palabras = []
    mayuscula = True
    for palabra in texto.split():
        if re.fullmatch(r"[IVX]+\.", palabra):
            palabras.append(palabra)
            mayuscula = True
            continue
        clave = palabra.rstrip(".")
        if clave not in PALABRAS_ENCABEZADO:
            raise KeyError(f"palabra desconocida en encabezado: {palabra}")
        convertida = PALABRAS_ENCABEZADO[clave]
        if mayuscula:
            convertida = convertida[0].upper() + convertida[1:]
        if palabra.endswith("."):
            convertida += "."
        palabras.append(convertida)
        mayuscula = palabra.endswith(".")
    return " ".join(palabras).removesuffix(".")


ANCHO = 72


def envolver(texto, inicial="", subsecuente=""):
    """Refluye un párrafo a un ancho máximo de `ANCHO` caracteres."""
    return textwrap.fill(
        texto,
        width=ANCHO,
        initial_indent=inicial,
        subsequent_indent=subsecuente,
    )


def clase_inciso(marca, clase_anterior):
    """Clase y forma rst de un marcador de inciso: romano, letra u ordinal.

    Los ordinales (``1a``, ``2o``, …) pierden la terminación para ser
    listas numeradas de rst. Las letras ambiguas con numerales romanos
    (I, V, X, L, C, D, M) heredan la clase del inciso anterior en la
    corrida; al inicio de una corrida, sólo ``I`` se considera romano.
    """
    if re.fullmatch(r"\d+[oa]", marca):
        return marca[:-1], "ordinal"
    if len(marca) > 1:
        return marca, "romano"
    if marca not in "IVXLCDM":
        return marca, "letra"
    if clase_anterior in ("romano", "letra"):
        return marca, clase_anterior
    return marca, "romano" if marca == "I" else "letra"


def formatear_parrafos(parrafos):
    """Convierte los párrafos de un artículo a rst.

    Los incisos se emiten como listas enumeradas que conservan el
    marcador original. Las letras y los ordinales que siguen a un
    inciso romano se anidan bajo él, como sublistas. Los ``(sic)`` del
    original se enfatizan: ``(*sic*)``.
    """
    partes = []
    clase_corrida = None
    nivel_corrida = 0
    sangria_padre = 0
    for parrafo in parrafos:
        parrafo = parrafo.replace("(sic)", "(*sic*)")
        inciso = INCISO_RE.match(parrafo)
        if not inciso:
            partes.append(envolver(parrafo))
            clase_corrida = None
            continue
        marca, clase = clase_inciso(inciso.group(1), clase_corrida)
        if clase != clase_corrida:
            nivel_corrida = 1 if clase_corrida == "romano" else 0
        if clase == "romano":
            sangria_padre = len(marca) + 2
        clase_corrida = clase
        marcador = marca + "."
        inicial = " " * (sangria_padre if nivel_corrida else 0) + marcador + " "
        partes.append(
            envolver(
                parrafo[inciso.end() :],
                inicial=inicial,
                subsecuente=" " * len(inicial),
            )
        )
    return partes


def escribir_articulos(documento, salida):
    """Escribe un archivo rst por artículo en el directorio de salida.

    El número del artículo se escribe en negritas, no como encabezado de
    sección, para no alterar la jerarquía de títulos, capítulos y
    secciones.
    """
    for articulo in documento["articulos"]:
        numero = articulo["numero"]
        ruta = salida / f"{numero:03d}.rst"
        partes = [f"**Artículo {numero}**"]
        partes.extend(formatear_parrafos(articulo["parrafos"]))
        ruta.write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    for articulo in documento["transitorios"]:
        numero = articulo["numero"]
        ruta = salida / f"T{numero:03d}.rst"
        partes = [f"**Artículo transitorio {numero}**"]
        partes.extend(formatear_parrafos(articulo["parrafos"]))
        ruta.write_text("\n\n".join(partes) + "\n", encoding="utf-8")


def escribir_indice(documento, salida):
    """Escribe `cpeum.rst`: título, preámbulo, artículos incluidos y cierre."""
    partes = [titulo_rst("Constitución Política de los Estados Unidos Mexicanos")]
    partes.extend(envolver(p) for p in documento["preambulo"])
    partes.append(".. contents::")

    anterior = {}
    for articulo in documento["articulos"]:
        seccion = articulo["seccion"]
        cambio = False
        for nivel in ("titulo", "capitulo", "epigrafe"):
            if seccion.get(nivel) != anterior.get(nivel):
                cambio = True
            if not cambio or nivel not in seccion:
                continue
            if nivel == "titulo":
                adorno = "-"
            elif nivel == "capitulo":
                adorno = "~"
            else:
                adorno = "^" if "capitulo" in seccion else "~"
            partes.append(subtitulo_rst(titular(seccion[nivel]), adorno))
        partes.append(f".. include:: {articulo['numero']:03d}.rst")
        anterior = seccion

    partes.append(subtitulo_rst("Artículos transitorios", "-"))
    for articulo in documento["transitorios"]:
        partes.append(f".. include:: T{articulo['numero']:03d}.rst")

    partes.extend(envolver(p) for p in documento["cierre"])
    (salida / "cpeum.rst").write_text("\n\n".join(partes) + "\n", encoding="utf-8")


def main():
    """Punto de entrada del script."""
    parser = argparse.ArgumentParser(
        description="Convierte el PDF de la Constitución de 1917 a rst."
    )
    parser.add_argument("pdf", type=Path, help="ruta del PDF de origen")
    parser.add_argument(
        "-o",
        "--salida",
        type=Path,
        default=Path("CPEUM"),
        help="directorio de salida (por omisión: CPEUM)",
    )
    args = parser.parse_args()

    with pymupdf.open(args.pdf) as pdf:
        parrafos = texto_continuo(pdf)
    documento = segmentar(parrafos)
    validar(documento)

    args.salida.mkdir(parents=True, exist_ok=True)
    escribir_articulos(documento, args.salida)
    escribir_indice(documento, args.salida)

    total = len(documento["articulos"]) + len(documento["transitorios"])
    print(f"{total} artículos escritos en {args.salida}")


if __name__ == "__main__":
    main()
