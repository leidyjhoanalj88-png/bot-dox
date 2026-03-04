#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BOT DOX - Sistema Unificado Completo
Keys + Licencias + Consultas + SISBEN + GPS
"""

import os
import logging
import random
import string
import pymysql
from datetime import datetime, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from sisben_scraper import consultar_sisben, formatear_resultado_telegram

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8781292195:AAEfjQZCV0-OgYq3VGJZ_7IDKSEsp3yMf-A")
BOT_PASSWORD   = os.getenv("BOT_PASSWORD",   "admin123")
DASHBOARD_URL  = os.getenv("DASHBOARD_URL",  "")
ADMIN_IDS      = set([int(x) for x in os.getenv("ADMIN_IDS", "8114050673").split(",") if x.strip()])

DB_CONFIG = {
    'host':            os.getenv('DB_HOST', 'localhost'),
    'user':            os.getenv('DB_USER', 'root'),
    'password':        os.getenv('DB_PASS', 'nabo94nabo94'),
    'charset':         'utf8mb4',
    'cursorclass':     pymysql.cursors.DictCursor,
    'connect_timeout': 5,
    'read_timeout':    10,
    'write_timeout':   10,
}
GPS_CONFIG = {
    'host':            os.getenv('GPS_DB_HOST', 'localhost'),
    'user':            os.getenv('GPS_DB_USER', 'systemph'),
    'password':        os.getenv('GPS_DB_PASS', '22zbV7I5zm'),
    'database':        'systemph_gpstracker',
    'charset':         'utf8mb4',
    'cursorclass':     pymysql.cursors.DictCursor,
    'connect_timeout': 5,
    'read_timeout':    10,
    'write_timeout':   10,
}

# ─── ESTADOS ──────────────────────────────────────────────────────────────────
(MENU_PRINCIPAL, ESPERANDO_PASSWORD, ESPERANDO_CEDULA,
 ESPERANDO_NOMBRE, ESPERANDO_APELLIDO, MENU_GPS,
 GPS_CC, GPS_NAME, GPS_DIR, GPS_CEL,
 SISBEN_TIPO_DOC, SISBEN_NUM_DOC) = range(12)

USUARIOS_AUTH = set()

# ─── TECLADOS ─────────────────────────────────────────────────────────────────
TECLADO_MENU = ReplyKeyboardMarkup([
    ["🔍 Buscar por Cédula",  "👤 Buscar por Nombre"],
    ["🏠 Núcleo Familiar",    "📡 Consulta SISBEN"],
    ["📞 Datos de Contacto",  "🛰️ Gestionar GPS"],
    ["🖥️ Panel Web",          "🚪 Salir"]
], resize_keyboard=True)

TECLADO_GPS = ReplyKeyboardMarkup([
    ["➕ Agregar Usuario GPS", "📋 Listar GPS"],
    ["❌ Eliminar GPS",        "🔙 Volver al Menú"]
], resize_keyboard=True)

TECLADO_TIPO_DOC = ReplyKeyboardMarkup([
    ["3️⃣ Cédula de Ciudadanía",  "2️⃣ Tarjeta de Identidad"],
    ["1️⃣ Registro Civil",         "4️⃣ Cédula de Extranjería"],
    ["8️⃣ Permiso Especial (PEP)", "9️⃣ Permiso Protección (PPT)"],
    ["🔙 Volver al Menú"]
], resize_keyboard=True)

MAPA_TIPO_DOC = {
    "3️⃣ Cédula de Ciudadanía":    "3",
    "2️⃣ Tarjeta de Identidad":    "2",
    "1️⃣ Registro Civil":           "1",
    "4️⃣ Cédula de Extranjería":    "4",
    "8️⃣ Permiso Especial (PEP)":   "8",
    "9️⃣ Permiso Protección (PPT)": "9",
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def _con(db):    return pymysql.connect(**{**DB_CONFIG, 'database': db})
def _con_gps():  return pymysql.connect(**GPS_CONFIG)
def v(val):      return str(val).strip() if val else ''
def gen_code(n=6): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

def es_admin(user_id):
    return user_id in ADMIN_IDS

def tiene_key_valida(user_id):
    if es_admin(user_id):
        return True
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("""
                SELECT 1 FROM user_keys
                WHERE user_id = %s AND redeemed = TRUE AND expiration_date > NOW()
            """, (user_id,))
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"tiene_key_valida: {e}")
        return False
    finally:
        if con: con.close()

def puede_usar(user_id):
    return user_id in USUARIOS_AUTH and tiene_key_valida(user_id)

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username or "sin_usuario"
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO users (user_id, telegram_username, date_registered) VALUES (%s,%s,%s)",
                    (user_id, username, datetime.now())
                )
                con.commit()
        con.close()
    except Exception as e:
        logger.error(f"start registro: {e}")

    if user_id in USUARIOS_AUTH and tiene_key_valida(user_id):
        await update.message.reply_text("✅ Ya estás autenticado.\n\nSelecciona una opción:", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL

    await update.message.reply_text(
        "<b>🔍 BOT DOX — Sistema de Consulta</b>\n\n"
        "<i>Ingresa la contraseña de acceso:</i>",
        parse_mode="HTML", reply_markup=ReplyKeyboardRemove()
    )
    return ESPERANDO_PASSWORD


async def verificar_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text.strip() == BOT_PASSWORD:
        if not tiene_key_valida(user_id):
            await update.message.reply_text(
                "🔑 Contraseña correcta.\n\n"
                "⚠️ No tienes licencia activa.\n"
                "Usa /redeem TU\\_KEY para activarla.",
                parse_mode="Markdown"
            )
            return ESPERANDO_PASSWORD
        USUARIOS_AUTH.add(user_id)
        await update.message.reply_text("✅ *Acceso concedido*\n\nBienvenido.", parse_mode="Markdown", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL
    await update.message.reply_text("❌ Contraseña incorrecta. Intenta de nuevo:")
    return ESPERANDO_PASSWORD

# ═══════════════════════════════════════════════════════════════════════════════
#  COMANDOS DE KEYS
# ═══════════════════════════════════════════════════════════════════════════════
async def cmd_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("❌ Uso: `/redeem TU_KEY`", parse_mode="Markdown")
        return
    key = context.args[0]
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute(
                "SELECT key_id, expiration_date FROM user_keys WHERE key_value=%s AND redeemed=FALSE",
                (key,)
            )
            result = cur.fetchone()
        if not result:
            await update.message.reply_text("❌ Clave no válida o ya redimida.")
            return
        if result['expiration_date'] < datetime.now():
            await update.message.reply_text("⏱️ Esta clave ya expiró.")
            return
        with con.cursor() as cur:
            cur.execute("UPDATE user_keys SET redeemed=TRUE, user_id=%s WHERE key_id=%s", (user_id, result['key_id']))
            con.commit()
        USUARIOS_AUTH.add(user_id)
        dias = (result['expiration_date'] - datetime.now()).days
        await update.message.reply_text(
            f"✅ *Clave activada*\n\n⏳ Expira en: *{dias} días*\n\nUsa /start para entrar.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"redeem: {e}")
        await update.message.reply_text("❌ Error al redimir la clave.")
    finally:
        if con: con.close()


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("""
                SELECT uk.key_value, uk.expiration_date, uk.created_at,
                       DATEDIFF(uk.expiration_date, NOW()) AS dias_restantes,
                       u.telegram_username
                FROM user_keys uk
                LEFT JOIN users u ON uk.user_id = u.user_id
                WHERE uk.user_id=%s AND uk.redeemed=TRUE
                ORDER BY uk.created_at DESC LIMIT 1
            """, (user_id,))
            r = cur.fetchone()
        if r:
            await update.message.reply_text(
                f"🔑 *Tu Licencia*\n\n"
                f"👤 @{v(r.get('telegram_username'))}\n"
                f"📅 Creada: {v(r.get('created_at'))}\n"
                f"⏳ Expira en: *{v(r.get('dias_restantes'))} días*\n"
                f"🔑 `{v(r.get('key_value'))}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Sin licencia activa. Usa `/redeem TU_KEY`", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        if con: con.close()


async def cmd_genkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es_admin(user_id):
        await update.message.reply_text("🚫 Sin permisos.")
        return
    if len(context.args) != 2:
        await update.message.reply_text("❌ Uso: `/genkey ID_USUARIO DIAS`", parse_mode="Markdown")
        return
    try:
        id_usr = int(context.args[0])
        dias   = int(context.args[1])
        key    = "KEY-" + ''.join(random.choices(string.ascii_letters + string.digits, k=15))
        expira = datetime.now() + timedelta(days=dias)
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("INSERT INTO user_keys (key_value, user_id, expiration_date) VALUES (%s,%s,%s)", (key, id_usr, expira))
            con.commit()
        con.close()
        await update.message.reply_text(
            f"✅ *Key generada*\n\n🔑 `{key}`\n👤 Para: `{id_usr}`\n⏳ {dias} días",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_delkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es_admin(user_id):
        await update.message.reply_text("🚫 Sin permisos.")
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: `/delkey KEY_VALUE`", parse_mode="Markdown")
        return
    try:
        key = context.args[0]
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("DELETE FROM user_keys WHERE key_value=%s", (key,))
            con.commit()
            ok = cur.rowcount > 0
        con.close()
        await update.message.reply_text("✅ Key eliminada." if ok else "⚠️ No encontrada.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


async def cmd_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es_admin(user_id):
        await update.message.reply_text("🚫 Sin permisos.")
        return
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("""
                SELECT uk.key_value, uk.expiration_date, uk.redeemed, u.telegram_username
                FROM user_keys uk LEFT JOIN users u ON uk.user_id=u.user_id
                ORDER BY uk.created_at DESC LIMIT 20
            """)
            claves = cur.fetchall()
        if not claves:
            await update.message.reply_text("⚠️ No hay keys.")
            return
        msg = "🔑 *Keys registradas:*\n\n"
        for c in claves:
            dias   = (c['expiration_date'] - datetime.now()).days if c['expiration_date'] else "?"
            estado = "✅" if c['redeemed'] else "⏳"
            usr    = f"@{c['telegram_username']}" if c['telegram_username'] else "Sin usuario"
            msg   += f"{estado} `{c['key_value']}`\n👤 {usr} | ⏳ {dias} días\n{'─'*20}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    finally:
        if con: con.close()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>📚 Comandos</b>\n\n"
        "<b>/start</b> — Iniciar sesión\n"
        "<b>/redeem KEY</b> — Activar licencia\n"
        "<b>/info</b> — Ver tu licencia\n"
        "<b>/cc CEDULA</b> — Buscar por cédula\n"
        "<b>/nombres NOMBRE AP1 AP2</b> — Buscar por nombre\n\n"
        "<b>👑 Admins:</b>\n"
        "<b>/genkey ID DIAS</b> — Generar key\n"
        "<b>/delkey KEY</b> — Eliminar key\n"
        "<b>/keys</b> — Ver todas las keys\n",
        parse_mode="HTML"
    )


async def cmd_cc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not puede_usar(user_id):
        await update.message.reply_text("🔐 Sin acceso. Usa /start")
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: `/cc CEDULA`", parse_mode="Markdown")
        return
    cedula = context.args[0]
    await update.message.reply_text("🔍 Consultando...")
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("SELECT * FROM ani WHERE ANINuip=%s LIMIT 1", (cedula,))
            r = cur.fetchone()
        if r:
            msg = (
                f"✅ *Datos del Ciudadano*\n\n"
                f"📋 `{v(r.get('ANINuip'))}`\n"
                f"👤 {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))} {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))}\n"
                f"👨 Padre: {v(r.get('ANINombresPadre'))}\n"
                f"👩 Madre: {v(r.get('ANINombresMadre'))}\n"
                f"📅 Nac: {v(r.get('ANIFchNacimiento'))} | Exp: {v(r.get('ANIFchExpedicion'))}\n"
                f"⚧ {v(r.get('ANISexo'))} | 📏 {v(r.get('ANIEstatura'))} | 🩸 {v(r.get('GRSId'))}\n"
                f"📍 {v(r.get('ANIDireccion'))}\n"
                f"📞 {v(r.get('ANITelefono'))}\n"
            )
        else:
            msg = f"⚠️ No se encontró la cédula `{cedula}`."
    except Exception as e:
        msg = f"❌ Error: `{e}`"
    finally:
        if con: con.close()
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_nombres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not puede_usar(user_id):
        await update.message.reply_text("🔐 Sin acceso. Usa /start")
        return
    if len(context.args) < 3:
        await update.message.reply_text("❌ Uso: `/nombres NOMBRE AP1 AP2`\nEjemplo: `/nombres CARLOS GARCIA LOPEZ`", parse_mode="Markdown")
        return
    nombre1, ap1, ap2 = context.args[0].upper(), context.args[1].upper(), context.args[2].upper()
    nombre2 = context.args[3].upper() if len(context.args) > 3 else None
    await update.message.reply_text("🔍 Buscando...")
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            query  = "SELECT ANINuip,ANINombre1,ANINombre2,ANIApellido1,ANIApellido2,ANIFchNacimiento FROM ani WHERE ANINombre1=%s AND ANIApellido1=%s AND ANIApellido2=%s"
            params = [nombre1, ap1, ap2]
            if nombre2:
                query += " AND ANINombre2=%s"
                params.append(nombre2)
            cur.execute(query + " LIMIT 50", params)
            resultados = cur.fetchall()
        if resultados:
            msg = f"✅ *{len(resultados)} resultado(s)*\n\n"
            for r in resultados[:10]:
                msg += f"📋 `{v(r.get('ANINuip'))}` — {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))} {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))}\n📅 {v(r.get('ANIFchNacimiento'))}\n{'─'*22}\n"
            if len(resultados) > 10:
                msg += f"_...y {len(resultados)-10} más._"
        else:
            msg = "⚠️ Sin resultados."
    except Exception as e:
        msg = f"❌ Error: `{e}`"
    finally:
        if con: con.close()
    await update.message.reply_text(msg, parse_mode="Markdown")

# ═══════════════════════════════════════════════════════════════════════════════
#  MENÚ PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not puede_usar(user_id):
        await update.message.reply_text("🔐 Sin acceso. Usa /start")
        return ESPERANDO_PASSWORD
    texto = update.message.text

    if texto == "🔍 Buscar por Cédula":
        context.user_data['modo'] = 'cedula'
        await update.message.reply_text("📄 Ingresa el número de cédula:", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "👤 Buscar por Nombre":
        await update.message.reply_text("👤 Ingresa el *primer nombre*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_NOMBRE
    elif texto == "🏠 Núcleo Familiar":
        context.user_data['modo'] = 'nucleo'
        await update.message.reply_text("🏠 Ingresa la *cédula*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "📡 Consulta SISBEN":
        await update.message.reply_text("📡 Selecciona el tipo de documento:", parse_mode="Markdown", reply_markup=TECLADO_TIPO_DOC)
        return SISBEN_TIPO_DOC
    elif texto == "📞 Datos de Contacto":
        context.user_data['modo'] = 'contacto'
        await update.message.reply_text("📞 Ingresa la *cédula*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "🛰️ Gestionar GPS":
        await update.message.reply_text("🛰️ *Gestión GPS*", parse_mode="Markdown", reply_markup=TECLADO_GPS)
        return MENU_GPS
    elif texto == "🖥️ Panel Web":
        if DASHBOARD_URL:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🖥️ Abrir Panel", web_app=WebAppInfo(url=DASHBOARD_URL))]])
            await update.message.reply_text("🖥️ *Panel de Control*", parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text("⚠️ Panel web no configurado.")
        return MENU_PRINCIPAL
    elif texto == "🚪 Salir":
        USUARIOS_AUTH.discard(user_id)
        await update.message.reply_text("👋 Sesión cerrada.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    await update.message.reply_text("Selecciona una opción:", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL

# ═══════════════════════════════════════════════════════════════════════════════
#  BÚSQUEDAS
# ═══════════════════════════════════════════════════════════════════════════════
async def buscar_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cedula = update.message.text.strip()
    modo   = context.user_data.get('modo', 'cedula')
    if not cedula.isdigit():
        await update.message.reply_text("❌ Solo números. Intenta de nuevo:")
        return ESPERANDO_CEDULA
    await update.message.reply_text("🔍 Consultando...")
    try:
        if modo == 'nucleo':
            con = _con('localizacion')
            with con.cursor() as cur:
                cur.execute("SELECT ficha FROM cedula_ficha WHERE cedula=%s LIMIT 1", (cedula,))
                row = cur.fetchone()
                if not row:
                    cur.execute("SELECT FICHA AS ficha FROM unifsisben WHERE DOC_NUM=%s LIMIT 1", (cedula,))
                    row = cur.fetchone()
            if not row:
                msg = "⚠️ No se encontró núcleo familiar."
            else:
                with con.cursor() as cur:
                    cur.execute("""SELECT apellido_a,apellido_b,nombre_a,nombre_b,doc_num,fec_nac,puntaje,nivel,zona,localidad,direccion,telefono FROM sisben_n WHERE ficha=%s ORDER BY persona""", (row['ficha'],))
                    ints = cur.fetchall()
                con.close()
                if not ints:
                    msg = "⚠️ Núcleo vacío."
                else:
                    msg = f"🏠 *Núcleo Familiar* — {len(ints)} integrante(s)\n\n"
                    for r in ints:
                        msg += f"👤 *{v(r.get('apellido_a'))} {v(r.get('apellido_b'))} {v(r.get('nombre_a'))} {v(r.get('nombre_b'))}*\n"
                        msg += f"📋 `{v(r.get('doc_num'))}` | 📅 {v(r.get('fec_nac'))}\n"
                        if v(r.get('puntaje')): msg += f"📊 Puntaje: *{v(r.get('puntaje'))}* Nivel: *{v(r.get('nivel'))}*\n"
                        if v(r.get('localidad')): msg += f"📍 {v(r.get('localidad'))}\n"
                        if v(r.get('telefono')):  msg += f"📞 {v(r.get('telefono'))}\n"
                        msg += f"{'─'*22}\n"
        elif modo == 'contacto':
            con = _con('localizacion')
            with con.cursor() as cur:
                cur.execute("SELECT APELLIDO1,APELLIDO2,NOMBRE,TELEFONO,TELFOFICINA,DIRECCION,DIRECCION2,CEL1,CEL2,EMPRESA,CIUDAD FROM unifsisben WHERE DOC_NUM=%s LIMIT 1", (cedula,))
                r1 = cur.fetchone()
            with con.cursor() as cur:
                cur.execute("SELECT papellido,sapellido,nombres,teloficina,direccion,telresiden,celular,empresa,ciudad,`e-mail` FROM bd WHERE cedula=%s LIMIT 1", (cedula,))
                r2 = cur.fetchone()
            con.close()
            if r1 or r2:
                msg = f"📞 *Datos de Contacto* `{cedula}`\n\n"
                if r1:
                    msg += f"👤 *{v(r1.get('APELLIDO1'))} {v(r1.get('APELLIDO2'))}* — {v(r1.get('NOMBRE'))}\n"
                    if r1.get('CEL1'):     msg += f"📱 {v(r1.get('CEL1'))}\n"
                    if r1.get('CEL2'):     msg += f"📱 {v(r1.get('CEL2'))}\n"
                    if r1.get('TELEFONO'): msg += f"📞 {v(r1.get('TELEFONO'))}\n"
                    if r1.get('DIRECCION'):msg += f"🏠 {v(r1.get('DIRECCION'))}\n"
                    if r1.get('CIUDAD'):   msg += f"🌆 {v(r1.get('CIUDAD'))}\n"
                if r2:
                    msg += f"\n{'─'*22}\n👤 {v(r2.get('papellido'))} {v(r2.get('sapellido'))} {v(r2.get('nombres'))}\n"
                    if r2.get('celular'):   msg += f"📱 {v(r2.get('celular'))}\n"
                    if r2.get('direccion'): msg += f"🏠 {v(r2.get('direccion'))}\n"
                    if r2.get('ciudad'):    msg += f"🌆 {v(r2.get('ciudad'))}\n"
                    if r2.get('e-mail'):    msg += f"✉️ {v(r2.get('e-mail'))}\n"
            else:
                msg = "⚠️ Sin datos de contacto."
        else:
            con = _con('ani')
            with con.cursor() as cur:
                cur.execute("SELECT * FROM ani WHERE ANINuip=%s LIMIT 1", (cedula,))
                r = cur.fetchone()
            con.close()
            if r:
                msg = (
                    f"✅ *Datos del Ciudadano*\n\n"
                    f"📋 `{v(r.get('ANINuip'))}`\n"
                    f"👤 {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))} {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))}\n"
                    f"👨 Padre: {v(r.get('ANINombresPadre'))}\n"
                    f"👩 Madre: {v(r.get('ANINombresMadre'))}\n"
                    f"📅 Nac: {v(r.get('ANIFchNacimiento'))} | Exp: {v(r.get('ANIFchExpedicion'))}\n"
                    f"⚧ {v(r.get('ANISexo'))} | 📏 {v(r.get('ANIEstatura'))} | 🩸 {v(r.get('GRSId'))}\n"
                    f"📍 {v(r.get('ANIDireccion'))}\n"
                    f"📞 {v(r.get('ANITelefono'))}\n"
                )
            else:
                msg = f"⚠️ No se encontró la cédula `{cedula}`."
    except Exception as e:
        logger.error(f"buscar_cedula: {e}")
        msg = f"❌ Error: `{e}`"

    context.user_data['modo'] = 'cedula'
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL


async def buscar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nombre1'] = update.message.text.strip().upper()
    await update.message.reply_text("📝 Ingresa el *primer apellido*:", parse_mode="Markdown")
    return ESPERANDO_APELLIDO


async def buscar_apellido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nombre1 = context.user_data.get('nombre1', '')
    ap1     = update.message.text.strip().upper()
    await update.message.reply_text("🔍 Buscando...")
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("SELECT ANINuip,ANINombre1,ANINombre2,ANIApellido1,ANIApellido2,ANIFchNacimiento FROM ani WHERE ANINombre1=%s AND ANIApellido1=%s LIMIT 50", (nombre1, ap1))
            res = cur.fetchall()
        if res:
            msg = f"✅ *{len(res)} resultado(s)*\n\n"
            for r in res[:10]:
                msg += f"📋 `{v(r.get('ANINuip'))}` — {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))} {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))}\n📅 {v(r.get('ANIFchNacimiento'))}\n{'─'*22}\n"
            if len(res) > 10: msg += f"_...y {len(res)-10} más._"
        else:
            msg = "⚠️ Sin resultados."
    except Exception as e:
        msg = f"❌ Error: `{e}`"
    finally:
        if con: con.close()
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL

# ═══════════════════════════════════════════════════════════════════════════════
#  SISBEN OFICIAL
# ═══════════════════════════════════════════════════════════════════════════════
async def sisben_tipo_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == "🔙 Volver al Menú":
        await update.message.reply_text("Menú:", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL
    tipo = MAPA_TIPO_DOC.get(texto)
    if not tipo:
        await update.message.reply_text("❌ Selecciona una opción válida:", reply_markup=TECLADO_TIPO_DOC)
        return SISBEN_TIPO_DOC
    context.user_data['sisben_tipo'] = tipo
    await update.message.reply_text(f"✅ Tipo: *{texto}*\n\nIngresa el número:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return SISBEN_NUM_DOC


async def sisben_num_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numero = update.message.text.strip()
    tipo   = context.user_data.get('sisben_tipo', '3')
    await update.message.reply_text("🔍 Consultando SISBEN IV...\n⏳ _Un momento_", parse_mode="Markdown")
    resultado = consultar_sisben(tipo, numero)
    msg = formatear_resultado_telegram(resultado)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL

# ═══════════════════════════════════════════════════════════════════════════════
#  GPS
# ═══════════════════════════════════════════════════════════════════════════════
async def menu_gps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == "📋 Listar GPS":
        try:
            con = _con_gps()
            with con.cursor() as cur:
                cur.execute("SELECT * FROM usersgps ORDER BY ide_per DESC LIMIT 50")
                usu = cur.fetchall()
            con.close()
            msg = "🛰️ *Usuarios GPS:*\n\n" + "".join([f"👤 {v(u.get('name'))} | CC:`{v(u.get('cc'))}` | 📞{v(u.get('cel'))} | 🔑`{v(u.get('code'))}`\n{'─'*22}\n" for u in usu]) if usu else "⚠️ No hay usuarios GPS."
        except Exception as e:
            msg = f"❌ Error: {e}"
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO_GPS)
        return MENU_GPS
    elif texto == "➕ Agregar Usuario GPS":
        await update.message.reply_text("➕ Cédula del nuevo usuario:", reply_markup=ReplyKeyboardRemove())
        return GPS_CC
    elif texto == "❌ Eliminar GPS":
        context.user_data['modo'] = 'eliminar_gps'
        await update.message.reply_text("❌ Cédula a eliminar:", reply_markup=ReplyKeyboardRemove())
        return GPS_CC
    elif texto == "🔙 Volver al Menú":
        await update.message.reply_text("Menú:", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL
    return MENU_GPS


async def gps_cc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cc = update.message.text.strip()
    context.user_data['gps_cc'] = cc
    if context.user_data.get('modo') == 'eliminar_gps':
        try:
            con = _con_gps()
            with con.cursor() as cur:
                cur.execute("DELETE FROM usersgps WHERE cc=%s", (cc,))
                con.commit()
                ok = cur.rowcount > 0
            con.close()
        except Exception as e:
            ok = False
        context.user_data['modo'] = ''
        await update.message.reply_text("✅ Eliminado." if ok else "⚠️ No encontrado.", reply_markup=TECLADO_GPS)
        return MENU_GPS
    await update.message.reply_text("👤 Nombre completo:")
    return GPS_NAME

async def gps_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gps_name'] = update.message.text.strip()
    await update.message.reply_text("📍 Dirección:")
    return GPS_DIR

async def gps_dir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gps_dir'] = update.message.text.strip()
    await update.message.reply_text("📞 Celular:")
    return GPS_CEL

async def gps_cel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gps_cel'] = update.message.text.strip()
    code = gen_code()
    try:
        con = _con_gps()
        with con.cursor() as cur:
            cur.execute("INSERT INTO usersgps (cc,name,dir,cel,code) VALUES (%s,%s,%s,%s,%s)",
                        (context.user_data['gps_cc'], context.user_data['gps_name'],
                         context.user_data['gps_dir'], context.user_data['gps_cel'], code))
            con.commit()
        con.close()
        msg = f"✅ *GPS agregado*\n\nCC: `{context.user_data['gps_cc']}`\n👤 {context.user_data['gps_name']}\n🔑 `{code}`"
    except Exception as e:
        msg = f"❌ Error: {e}"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=TECLADO_GPS)
    return MENU_GPS


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelado.", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ESPERANDO_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_password)],
            MENU_PRINCIPAL:     [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_principal)],
            ESPERANDO_CEDULA:   [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_cedula)],
            ESPERANDO_NOMBRE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_nombre)],
            ESPERANDO_APELLIDO: [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_apellido)],
            MENU_GPS:           [MessageHandler(filters.TEXT & ~filters.COMMAND, menu_gps)],
            GPS_CC:             [MessageHandler(filters.TEXT & ~filters.COMMAND, gps_cc)],
            GPS_NAME:           [MessageHandler(filters.TEXT & ~filters.COMMAND, gps_name)],
            GPS_DIR:            [MessageHandler(filters.TEXT & ~filters.COMMAND, gps_dir)],
            GPS_CEL:            [MessageHandler(filters.TEXT & ~filters.COMMAND, gps_cel)],
            SISBEN_TIPO_DOC:    [MessageHandler(filters.TEXT & ~filters.COMMAND, sisben_tipo_doc)],
            SISBEN_NUM_DOC:     [MessageHandler(filters.TEXT & ~filters.COMMAND, sisben_num_doc)],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("cc",      cmd_cc))
    app.add_handler(CommandHandler("nombres", cmd_nombres))
    app.add_handler(CommandHandler("redeem",  cmd_redeem))
    app.add_handler(CommandHandler("info",    cmd_info))
    app.add_handler(CommandHandler("genkey",  cmd_genkey))
    app.add_handler(CommandHandler("delkey",  cmd_delkey))
    app.add_handler(CommandHandler("keys",    cmd_keys))

    logger.info("✅ BOT DOX iniciado...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
