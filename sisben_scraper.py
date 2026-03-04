#!/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL_CONSULTA = "https://www.sisben.gov.co/dnp_sisbenconsulta"
URL_PAGINA   = "https://www.sisben.gov.co/Paginas/consulta-tu-grupo.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CO,es;q=0.9",
    "Referer": URL_PAGINA,
    "Origin": "https://www.sisben.gov.co",
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
        time.sleep(1)
        soup = BeautifulSoup(resp.text, "html.parser")
        token = None
        token_input = soup.find("input", {"name": "__RequestVerificationToken"})
        if token_input:
            token = token_input.get("value")
        payload = {"TipoID": tipo_doc, "documento": numero_doc}
        if token:
            payload["__RequestVerificationToken"] = token
        resp2 = session.post(URL_CONSULTA, data=payload, timeout=20)
        resp2.raise_for_status()
        try:
            data = resp2.json()
            return _parsear_json(data, tipo_doc, numero_doc)
        except:
            return _parsear_html(resp2.text, tipo_doc, numero_doc)
    except requests.exceptions.Timeout:
        return {"error": "⏱️ El servidor tardó demasiado. Intenta de nuevo."}
    except requests.exceptions.ConnectionError:
        return {"error": "🌐 No se pudo conectar con sisben.gov.co"}
    except Exception as e:
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
        "direccion":     data.get("direccion") or "",
        "telefono":      data.get("telefono") or "",
        "correo":        data.get("correo") or "",
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
    msg = "📡 *Consulta SISBEN IV — Resultado Oficial*\n🌐 _Fuente: sisben.gov.co_\n\n"
    if v("grupo"):
        msg += f"🏷️ *{v('grupo')}*"
        if v("clasificacion"): msg += f" — {v('clasificacion')}"
        msg += "\n\n"
    msg += "─────────────────────\n👤 *Datos Personales*\n"
    if v("nombres"):      msg += f"📝 Nombres: {v('nombres')}\n"
    if v("apellidos"):    msg += f"📝 Apellidos: {v('apellidos')}\n"
    if v("tipo_doc"):     msg += f"🪪 Tipo: {v('tipo_doc')}\n"
    if v("num_doc"):      msg += f"📋 Número: `{v('num_doc')}`\n"
    if v("municipio"):    msg += f"🌆 Municipio: {v('municipio')}\n"
    if v("departamento"): msg += f"🗺️ Depto: {v('departamento')}\n"
    if any(v(k) for k in ["ficha","encuesta","fecha"]):
        msg += "\n─────────────────────\n📋 *Registro*\n"
        if v("ficha"):    msg += f"📌 Ficha: {v('ficha')}\n"
        if v("encuesta"): msg += f"📅 Encuesta: {v('encuesta')}\n"
        if v("fecha"):    msg += f"🗓️ Fecha: {v('fecha')}\n"
    return msg