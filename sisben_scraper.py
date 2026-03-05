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

def consultar_sisben_selenium(tipo_doc, numero_doc):
    """Consulta SISBEN usando Selenium con Chrome headless."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")
        options.binary_location = "/usr/bin/chromium"

        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)

        try:
            driver.get(URL_PAGINA)
            wait = WebDriverWait(driver, 15)

            # Seleccionar tipo de documento
            try:
                select_elem = wait.until(EC.presence_of_element_located((By.NAME, "TipoID")))
                select = Select(select_elem)
                select.select_by_value(tipo_doc)
            except:
                pass

            # Ingresar número de documento
            try:
                input_doc = wait.until(EC.presence_of_element_located((By.NAME, "documento")))
                input_doc.clear()
                input_doc.send_keys(numero_doc)
            except:
                input_doc = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
                input_doc.clear()
                input_doc.send_keys(numero_doc)

            # Clic en consultar
            try:
                btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
                btn.click()
            except:
                pass

            time.sleep(4)
            html = driver.page_source
            return _parsear_html_selenium(html, tipo_doc, numero_doc)

        finally:
            driver.quit()

    except Exception as e:
        logger.error(f"Selenium error: {e}")
        return consultar_sisben_requests(tipo_doc, numero_doc)


def consultar_sisben_requests(tipo_doc, numero_doc):
    """Fallback con requests."""
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


def consultar_sisben(tipo_doc, numero_doc):
    """Función principal — intenta Selenium primero, luego requests."""
    return consultar_sisben_selenium(tipo_doc, numero_doc)


def _parsear_html_selenium(html, tipo_doc, numero_doc):
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text()
    texto_lower = texto.lower()

    if "no se encontr" in texto_lower or "no registra" in texto_lower or "no está" in texto_lower:
        return {"no_encontrado": True}

    resultado = {
        "tipo_doc": TIPOS_DOCUMENTO.get(tipo_doc, tipo_doc),
        "num_doc":  numero_doc,
        "grupo": "", "clasificacion": "", "nombres": "",
        "apellidos": "", "municipio": "", "departamento": "",
        "ficha": "", "encuesta": "", "fecha": "",
    }

    # Buscar grupo SISBEN
    for tag in soup.find_all(["h1","h2","h3","h4","p","div","span","td"]):
        t = tag.get_text(strip=True)
        if "grupo" in t.lower() and len(t) < 100:
            resultado["grupo"] = t
            break

    # Buscar nombre
    for tag in soup.find_all(["td","p","div","span"]):
        t = tag.get_text(strip=True)
        if len(t) > 5 and t.isupper() and len(t.split()) >= 2:
            if not any(x in t.lower() for x in ["grupo","sisben","consulta","municipio"]):
                if not resultado["nombres"]:
                    partes = t.split()
                    if len(partes) >= 4:
                        resultado["apellidos"] = " ".join(partes[:2])
                        resultado["nombres"]   = " ".join(partes[2:])
                    else:
                        resultado["nombres"] = t

    if not resultado["grupo"] and not resultado["nombres"]:
        return {"no_encontrado": True}

    return resultado


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
