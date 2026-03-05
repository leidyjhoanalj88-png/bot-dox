#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL_PAGINA  = "https://www.sisben.gov.co/Paginas/consulta-tu-grupo.html"
URL_CONSULTA = "https://www.sisben.gov.co/dnp_sisbenconsulta"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": URL_PAGINA,
    "Origin": "https://www.sisben.gov.co",
    "Cache-Control": "no-cache",
}

TIPOS_DOCUMENTO = {
    "1": "Registro Civil",
    "2": "Tarjeta de Identidad",
    "3": "Cedula de Ciudadania",
    "4": "Cedula de Extranjeria",
    "8": "Permiso Especial Permanencia",
    "9": "Permiso Proteccion Temporal",
}

def consultar_sisben(tipo_doc, numero_doc):
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        resp = session.get(URL_PAGINA, timeout=15)
        resp.raise_for_status()
        time.sleep(2)

        soup = BeautifulSoup(resp.text, "html.parser")
        token = None
        for inp in soup.find_all("input"):
            if "token" in (inp.get("name","")).lower():
                token = inp.get("value")
                break

        payload = {"TipoID": tipo_doc, "documento": numero_doc}
        if token:
            payload["__RequestVerificationToken"] = token

        headers_post = {**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}
        resp2 = session.post(URL_CONSULTA, data=payload, headers=headers_post, timeout=20)

        try:
            data = resp2.json()
            return _parsear_json(data, tipo_doc, numero_doc)
        except:
            return _parsear_html(resp2.text, tipo_doc, numero_doc)

    except requests.exceptions.Timeout:
        return {"error": "⏱️ Tiempo de espera agotado. Intenta de nuevo."}
    except requests.exceptions.ConnectionError:
        return {"error": "🌐 No se pudo conectar con sisben.gov.co"}
    except Exception as e:
        logger.error(f"SISBEN error: {e}")
        return {"error": f"❌ Error: {str(e)}"}

def _parsear_json(data, tipo_doc, numero_doc):
    if not data:
        return {"no_encontrado": True}
    resultado = {
        "grupo":         data.get("grupo") or data.get("Grupo") or "",
        "clasificacion": data.get("clasificacion") or "",
        "nombres":       data.get("nombres") or data.get("Nombres") or "",
        "apellidos":     data.get("apellidos") or data.get("Apellidos") or "",
        "tipo_doc":      TIPOS_DOCUMENTO.get(tipo_doc, tipo_doc),
        "num_doc":       numero_doc,
        "municipio":     data.get("municipio") or "",
        "departamento":  data.get("departamento") or "",
        "ficha":         data.get("ficha") or "",
        "encuesta":      data.get("encuesta") or "",
        "fecha":         data.get("fecha") or "",
    }
    if not any([resultado["nombres"], resultado["apellidos"], resultado["grupo"]]):
        return {"no_encontrado": True}
    return resultado

def _parsear_html(html, tipo_doc, numero_doc):
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text().lower()
    if "no se encontr" in texto or "no registra" in texto:
        return {"no_encontrado": True}
    return {"no_encontrado": True}

def formatear_resultado_telegram(r):
    if "error" in r:
        return r["error"]
    if r.get("no_encontrado"):
        return "⚠️ *No se encontró registro SISBEN IV*\n\nEl documento no está en la base del SISBEN IV."
    def v(k): return str(r.get(k, "")).strip()
    msg = "📡 *Consulta SISBEN IV*\n🌐 _Fuente: sisben.gov.co_\n\n"
    if v("grupo"):
        msg += f"🏷️ *{v('grupo')}*"
        if v("clasificacion"): msg += f" — {v('clasificacion')}"
        msg += "\n\n"
    msg += "👤 *Datos Personales*\n"
    if v("nombres"):      msg += f"📝 {v('nombres')}\n"
    if v("apellidos"):    msg += f"📝 {v('apellidos')}\n"
    if v("num_doc"):      msg += f"📋 `{v('num_doc')}`\n"
    if v("municipio"):    msg += f"🌆 {v('municipio')}\n"
    if v("departamento"): msg += f"🗺️ {v('departamento')}\n"
    return msg