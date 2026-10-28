"""Escritor mínimo de .xlsx (R51).

`DataFrame.to_excel` tarda unos 4 s con 100 000 filas de 3 columnas y 14 s con 10.
Aquí se arma el XML de cada hoja directamente y se comprime: lo mismo en una
fracción del tiempo, sin dependencias nuevas. Escribe números, textos y
booleanos; los NaN e infinitos quedan como celdas vacías.
"""
import math
import re
import zipfile
from xml.sax.saxutils import escape

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '{hojas}'
    '</Types>')
_HOJA_CT = ('<Override PartName="/xl/worksheets/sheet{n}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="xl/workbook.xml"/></Relationships>')
_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets>{hojas}</sheets></workbook>')
_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
_HOJA = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>')

_INVALIDOS = re.compile(r"[\[\]:*?/\\]")
_XML_ILEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def nombre_de_hoja(nombre, usados):
    """Nombre válido para Excel (31 caracteres, sin []:*?/\\) y sin repetir."""
    base = _INVALIDOS.sub("_", str(nombre)).strip("'")[:31] or "Hoja"
    candidato, n = base, 2
    while candidato.lower() in usados:
        sufijo = f"_{n}"
        candidato = base[:31 - len(sufijo)] + sufijo
        n += 1
    usados.add(candidato.lower())
    return candidato


def _letra(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _celda(ref, v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)):
        if isinstance(v, float):               # incluye np.float64, cuyo repr no es un número
            v = float(v)
            if not math.isfinite(v):
                return ""
        return f'<c r="{ref}"><v>{v!r}</v></c>'
    try:                                   # NumPy: float64, int64, bool_
        import numpy as np
        if isinstance(v, np.bool_):
            return f'<c r="{ref}" t="b"><v>{int(v)}</v></c>'
        if isinstance(v, np.integer):
            return f'<c r="{ref}"><v>{int(v)}</v></c>'
        if isinstance(v, np.floating):
            return _celda(ref, float(v))
    except ImportError:
        pass
    texto = escape(_XML_ILEGAL.sub("", str(v)))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'


def _filas(encabezados, filas):
    letras = {}
    yield _HOJA
    for n, fila in enumerate([encabezados, *filas] if encabezados is not None else filas, 1):
        celdas = []
        for j, v in enumerate(fila):
            if j not in letras:
                letras[j] = _letra(j)
            celdas.append(_celda(f"{letras[j]}{n}", v))
        yield f'<row r="{n}">{"".join(celdas)}</row>'
    yield "</sheetData></worksheet>"


def escribir_xlsx(ruta, secciones, progreso=None):
    """`secciones`: {nombre de hoja: (encabezados, filas)}. Una hoja por sección."""
    usados = set()
    nombres = [nombre_de_hoja(n, usados) for n in secciones]
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr("[Content_Types].xml",
                   _CONTENT_TYPES.format(hojas="".join(_HOJA_CT.format(n=i + 1) for i in range(len(nombres)))))
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _WORKBOOK.format(hojas="".join(
            f'<sheet name="{escape(n, {chr(34): "&quot;"})}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
            for i, n in enumerate(nombres))))
        z.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS.format(rels="".join(
            f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(nombres)))))
        for i, (encabezados, filas) in enumerate(secciones.values()):
            with z.open(f"xl/worksheets/sheet{i + 1}.xml", "w") as f:
                bloque = []
                for trozo in _filas(list(encabezados), filas):
                    bloque.append(trozo)
                    if len(bloque) >= 2000:
                        f.write("".join(bloque).encode("utf-8"))
                        bloque.clear()
                f.write("".join(bloque).encode("utf-8"))
            if progreso is not None:
                progreso(i + 1, len(nombres))
