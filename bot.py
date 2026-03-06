#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BOT DOX - Sistema Unificado Completo
Acceso con aprobaci\u00f3n de Admin + Consultas + SISBEN + GPS
"""

import os
import logging
import random
import string
import pymysql
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from sisben_scraper import consultar_sisben, formatear_resultado_telegram
from db import Database

# \u2500\u2500\u2500 LOGGING \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# \u2500\u2500\u2500 CONFIG \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8781292195:AAEfjQZCV0-OgYq3VGJZ_7IDKSEsp3yMf-A")
DASHBOARD_URL  = os.getenv("DASHBOARD_URL",  "")
ADMIN_IDS      = set([int(x) for x in os.getenv("ADMIN_IDS", "8114050673").split(",") if x.strip()])

DB_CONFIG = {
    'host':            'metro.proxy.rlwy.net',
    'port':            51432,
    'user':            'root',
    'password':        'rIWnZxNXgktqOaJEXrPVcCyXENRmpLfQ',
    'database':        'railway',
    'charset':         'utf8mb4',
    'cursorclass':     pymysql.cursors.DictCursor,
    'connect_timeout': 10,
    'read_timeout':    15,
    'write_timeout':   15,
}

GPS_CONFIG = {
    'host':            'metro.proxy.rlwy.net',
    'port':            51432,
    'user':            'root',
    'password':        'rIWnZxNXgktqOaJEXrPVcCyXENRmpLfQ',
    'database':        'railway',
    'charset':         'utf8mb4',
    'cursorclass':     pymysql.cursors.DictCursor,
    'connect_timeout': 10,
    'read_timeout':    15,
    'write_timeout':   15,
}

(MENU_PRINCIPAL, ESPERANDO_CEDULA,
 ESPERANDO_NOMBRE, ESPERANDO_APELLIDO, MENU_GPS,
 GPS_CC, GPS_NAME, GPS_DIR, GPS_CEL,
 SISBEN_TIPO_DOC, SISBEN_NUM_DOC) = range(11)

USUARIOS_APROBADOS = set()

db = Database()

TECLADO_MENU = ReplyKeyboardMarkup([
    ["\ud83d\udd0d Buscar por C\u00e9dula",  "\ud83d\udc64 Buscar por Nombre"],
    ["\ud83c\udfe0 N\u00facleo Familiar",    "\ud83d\udce1 Consulta SISBEN"],
    ["\ud83d\udcde Datos de Contacto",  "\ud83d\udef0\ufe0f Gestionar GPS"],
    ["\ud83d\udda5\ufe0f Panel Web",          "\ud83d\udeaa Salir"]
], resize_keyboard=True)

TECLADO_GPS = ReplyKeyboardMarkup([
    ["\u2795 Agregar Usuario GPS", "\ud83d\udccb Listar GPS"],
    ["\u274c Eliminar GPS",        "\ud83d\udd19 Volver al Men\u00fa"]
], resize_keyboard=True)

TECLADO_TIPO_DOC = ReplyKeyboardMarkup([
    ["3\ufe0f\u20e3 C\u00e9dula de Ciudadan\u00eda",  "2\ufe0f\u20e3 Tarjeta de Identidad"],
    ["1\ufe0f\u20e3 Registro Civil",         "4\ufe0f\u20e3 C\u00e9dula de Extranjer\u00eda"],
    ["8\ufe0f\u20e3 Permiso Especial (PEP)", "9\ufe0f\u20e3 Permiso Protecci\u00f3n (PPT)"],
    ["\ud83d\udd19 Volver al Men\u00fa"]
], resize_keyboard=True)

MAPA_TIPO_DOC = {
    "3\ufe0f\u20e3 C\u00e9dula de Ciudadan\u00eda":    "3",
    "2\ufe0f\u20e3 Tarjeta de Identidad":    "2",
    "1\ufe0f\u20e3 Registro Civil":           "1",
    "4\ufe0f\u20e3 C\u00e9dula de Extranjer\u00eda":    "4",
    "8\ufe0f\u20e3 Permiso Especial (PEP)":   "8",
    "9\ufe0f\u20e3 Permiso Protecci\u00f3n (PPT)": "9",
}

def _con(database=None):
    config = dict(DB_CONFIG)
    if database:
        config['database'] = database
    return pymysql.connect(**config)

def _con_gps():
    return pymysql.connect(**GPS_CONFIG)

def v(val):        return str(val).strip() if val else ''
def gen_code(n=6): return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))
def es_admin(user_id): return user_id in ADMIN_IDS

def esta_aprobado(user_id):
    if es_admin(user_id):
        return True
    return user_id in USUARIOS_APROBADOS

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# FALLBACK: busca en cedulasri \u2192 bd (MySQL) \u2192 cach\u00e9 RAM (db.py)
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def _buscar_cedula_extra(cedula):
    """Busca en: 1) cedulasri MySQL  2) bd MySQL  3) cach\u00e9 RAM"""
    # 1. Tabla cedulasri
    try:
        con = _con('localizacion')
        with con.cursor() as cur:
            cur.execute(
                "SELECT cedula,papellido,sapellido,nombres,teloficina,"
                "direccion,telresiden,celular,ciudad "
                "FROM cedulasri WHERE cedula=%s LIMIT 1", (cedula,)
            )
            r = cur.fetchone()
        con.close()
        if r:
            return {'fuente': 'cedulasri', 'datos': r}
    except Exception as e:
        logger.warning(f"cedulasri fallback: {e}")

    # 2. Tabla bd
    try:
        con = _con('localizacion')
        with con.cursor() as cur:
            cur.execute(
                "SELECT cedula,papellido,sapellido,nombres,teloficina,"
                "direccion,telresiden,celular,ciudad "
                "FROM bd WHERE cedula=%s LIMIT 1", (cedula,)
            )
            r = cur.fetchone()
        con.close()
        if r:
            return {'fuente': 'bd', 'datos': r}
    except Exception as e:
        logger.warning(f"bd fallback: {e}")

    # 3. Cach\u00e9 en memoria (CEDULAS_DATA en db.py)
    try:
        r = db.buscar_cedula(cedula)
        if r:
            return {'fuente': 'cache', 'datos': r}
    except Exception as e:
        logger.warning(f"cache RAM fallback: {e}")

    return None


def _fmt_extra(cedula, res):
    """Formatea resultado de cedulasri/bd/cache para Telegram."""
    r = res['datos']
    # Si viene de MySQL con DictCursor es dict; si viene del cach\u00e9 tambi\u00e9n es dict
    if isinstance(r, (tuple, list)):
        r = {
            'cedula':     r[0] if len(r) > 0 else '',
            'papellido':  r[1] if len(r) > 1 else '',
            'sapellido':  r[2] if len(r) > 2 else '',
            'nombres':    r[3] if len(r) > 3 else '',
            'teloficina': r[4] if len(r) > 4 else '',
            'direccion':  r[5] if len(r) > 5 else '',
            'telresiden': r[6] if len(r) > 6 else '',
            'celular':    r[7] if len(r) > 7 else '',
            'ciudad':     r[8] if len(r) > 8 else '',
        }
    nombre = f"{v(r.get('papellido',''))} {v(r.get('sapellido',''))} {v(r.get('nombres',''))}".strip()
    tel    = v(r.get('celular')) or v(r.get('telresiden')) or v(r.get('teloficina')) or 'N/A'
    ciudad = v(r.get('ciudad'))    or 'N/A'
    dire   = v(r.get('direccion')) or 'N/A'
    return (
        f"\u2705 *Datos Encontrados*\n\n"
        f"\ud83d\udccb `{cedula}`\n"
        f"\ud83d\udc64 *{nombre}*\n"
        f"\ud83d\udccd {ciudad}\n"
        f"\ud83c\udfe0 {dire}\n"
        f"\ud83d\udcde {tel}"
    )

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username or "sin_usuario"
    nombre   = update.effective_user.first_name or "Usuario"
    if es_admin(user_id):
        await update.message.reply_text(f"\ud83d\udc51 *Bienvenido Admin!*\n\nSelecciona una opci\u00f3n:", parse_mode="Markdown", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL
    if esta_aprobado(user_id):
        await update.message.reply_text(f"\u2705 *Bienvenido, {nombre}!*\n\nSelecciona una opci\u00f3n:", parse_mode="Markdown", reply_markup=TECLADO_MENU)
        return MENU_PRINCIPAL
    await update.message.reply_text(f"\ud83d\udc4b Hola *{nombre}*!\n\n\u23f3 Tu solicitud de acceso fue enviada al administrador.\nEspera la aprobaci\u00f3n para continuar.", parse_mode="Markdown")
    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("\u2705 Aprobar", callback_data=f"aprobar_{user_id}"), InlineKeyboardButton("\u274c Rechazar", callback_data=f"rechazar_{user_id}")]])
            await context.bot.send_message(chat_id=admin_id, text=f"\ud83d\udd14 *Nueva solicitud de acceso*\n\n\ud83d\udc64 Nombre: *{nombre}*\n\ud83c\udd94 ID: `{user_id}`\n\ud83d\udcdb Usuario: @{username}", parse_mode="Markdown", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error notificando admin {admin_id}: {e}")
    return ConversationHandler.END

async def callback_aprobacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    admin_id = query.from_user.id
    if not es_admin(admin_id):
        await query.answer("\ud83d\udeab No tienes permisos.")
        return
    data   = query.data
    accion, uid = data.split("_", 1)
    uid = int(uid)
    if accion == "aprobar":
        USUARIOS_APROBADOS.add(uid)
        await query.edit_message_text(f"\u2705 Usuario `{uid}` *aprobado*.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=uid, text="\u2705 *\u00a1Acceso aprobado!*\n\nUsa /start para entrar al bot.", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error notificando usuario {uid}: {e}")
    elif accion == "rechazar":
        USUARIOS_APROBADOS.discard(uid)
        await query.edit_message_text(f"\u274c Usuario `{uid}` *rechazado*.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=uid, text="\u274c Tu solicitud de acceso fue *rechazada*.\n\nContacta al administrador.", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error notificando usuario {uid}: {e}")
    await query.answer()

async def cmd_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es_admin(user_id):
        await update.message.reply_text("\ud83d\udeab Sin permisos.")
        return
    if not USUARIOS_APROBADOS:
        await update.message.reply_text("\u26a0\ufe0f No hay usuarios aprobados.")
        return
    msg = "\ud83d\udc65 *Usuarios aprobados:*\n\n"
    for uid in USUARIOS_APROBADOS:
        msg += f"\ud83c\udd94 `{uid}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_revocar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not es_admin(user_id):
        await update.message.reply_text("\ud83d\udeab Sin permisos.")
        return
    if not context.args:
        await update.message.reply_text("\u274c Uso: `/revocar ID_USUARIO`", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
        USUARIOS_APROBADOS.discard(uid)
        await update.message.reply_text(f"\u2705 Acceso revocado para `{uid}`.", parse_mode="Markdown")
        try:
            await context.bot.send_message(chat_id=uid, text="\u26d4 Tu acceso al bot ha sido *revocado*.", parse_mode="Markdown")
        except:
            pass
    except ValueError:
        await update.message.reply_text("\u274c ID inv\u00e1lido.")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = "<b>\ud83d\udcda Comandos disponibles</b>\n\n<b>/start</b> \u2014 Iniciar / Solicitar acceso\n<b>/cc CEDULA</b> \u2014 Buscar por c\u00e9dula\n<b>/nombres NOMBRE AP1 AP2</b> \u2014 Buscar por nombre\n<b>/help</b> \u2014 Ver esta ayuda\n"
    if es_admin(user_id):
        msg += "\n<b>\ud83d\udc51 Comandos Admin:</b>\n<b>/usuarios</b> \u2014 Ver usuarios aprobados\n<b>/revocar ID</b> \u2014 Revocar acceso a un usuario\n"
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_cc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not esta_aprobado(user_id):
        await update.message.reply_text("\ud83d\udd10 Sin acceso. Usa /start para solicitar acceso.")
        return
    if not context.args:
        await update.message.reply_text("\u274c Uso: `/cc CEDULA`", parse_mode="Markdown")
        return
    cedula = context.args[0].strip()
    await update.message.reply_text("\ud83d\udd0d Consultando...")
    msg = None
    con = None
    # 1. Buscar en ANI
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("SELECT * FROM ani WHERE ANINuip=%s LIMIT 1", (cedula,))
            r = cur.fetchone()
        if r:
            lugar = db.get_municipio(r.get('ANILugNacimiento', ''))
            msg = (
                f"\u2705 *Datos del Ciudadano*\n\n"
                f"\ud83d\udccb `{v(r.get('ANINuip'))}`\n"
                f"\ud83d\udc64 {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))} {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))}\n"
                f"\ud83d\udc68 Padre: {v(r.get('ANINombresPadre'))}\n"
                f"\ud83d\udc69 Madre: {v(r.get('ANINombresMadre'))}\n"
                f"\ud83d\udcc5 Nac: {v(r.get('ANIFchNacimiento'))} | Exp: {v(r.get('ANIFchExpedicion'))}\n"
                f"\u26a7 {v(r.get('ANISexo'))} | \ud83d\udccf {v(r.get('ANIEstatura'))} | \ud83e\ude78 {v(r.get('GRSId'))}\n"
                f"\ud83d\udccd {v(r.get('ANIDireccion'))}\n"
                f"\ud83d\udcde {v(r.get('ANITelefono'))}\n"
            )
            if lugar:
                msg += f"\ud83c\udfe0 Naci\u00f3 en: *{lugar}*\n"
    except Exception as e:
        logger.warning(f"cmd_cc ANI: {e}")
    finally:
        if con:
            con.close()
    # 2. Si ANI no encontr\u00f3 nada \u2192 cedulasri / bd / cach\u00e9 RAM
    if not msg:
        res = _buscar_cedula_extra(cedula)
        msg = _fmt_extra(cedula, res) if res else f"\u26a0\ufe0f No se encontr\u00f3 la c\u00e9dula `{cedula}`."
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_nombres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not esta_aprobado(user_id):
        await update.message.reply_text("\ud83d\udd10 Sin acceso. Usa /start para solicitar acceso.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("\u274c Uso: `/nombres NOMBRE AP1 AP2`", parse_mode="Markdown")
        return
    nombre1, ap1, ap2 = context.args[0].upper(), context.args[1].upper(), context.args[2].upper()
    nombre2 = context.args[3].upper() if len(context.args) > 3 else None
    await update.message.reply_text("\ud83d\udd0d Buscando...")
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
            msg = f"\u2705 *{len(resultados)} resultado(s)*\n\n"
            for r in resultados[:10]:
                msg += f"\ud83d\udccb `{v(r.get('ANINuip'))}` \u2014 {v(r.get('ANIApellido1'))} {v(r.get('ANIApellido2'))} {v(r.get('ANINombre1'))} {v(r.get('ANINombre2'))}\n\ud83d\udcc5 {v(r.get('ANIFchNacimiento'))}\n{'\u2500'*22}\n"
            if len(resultados) > 10:
                msg += f"_...y {len(resultados)-10} m\u00e1s._"
        else:
            msg = "\u26a0\ufe0f Sin resultados."
    except Exception as e:
        msg = f"\u274c Error: `{e}`"
    finally:
        if con: con.close()
    await update.message.reply_text(msg, parse_mode="Markdown")

async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not esta_aprobado(user_id):
        await update.message.reply_text("\ud83d\udd10 Sin acceso. Usa /start para solicitar acceso.")
        return ConversationHandler.END
    texto = update.message.text
    if texto == "\ud83d\udd0d Buscar por C\u00e9dula":
        context.user_data['modo'] = 'cedula'
        await update.message.reply_text("\ud83d\udcc4 Ingresa el n\u00famero de c\u00e9dula:", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "\ud83d\udc64 Buscar por Nombre":
        await update.message.reply_text("\ud83d\udc64 Ingresa el *primer nombre*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_NOMBRE
    elif texto == "\ud83c\udfe0 N\u00facleo Familiar":
        context.user_data['modo'] = 'nucleo'
        await update.message.reply_text("\ud83c\udfe0 Ingresa la *c\u00e9dula*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "\ud83d\udce1 Consulta SISBEN":
        await update.message.reply_text("\ud83d\udce1 Selecciona el tipo de documento:", parse_mode="Markdown", reply_markup=TECLADO_TIPO_DOC)
        return SISBEN_TIPO_DOC
    elif texto == "\ud83d\udcde Datos de Contacto":
        context.user_data['modo'] = 'contacto'
        await update.message.reply_text("\ud83d\udcde Ingresa la *c\u00e9dula*:", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
        return ESPERANDO_CEDULA
    elif texto == "\ud83d\udef0\ufe0f Gestionar GPS":
        await update.message.reply_text("\ud83d\udef0\ufe0f *Gesti\u00f3n GPS*", parse_mode="Markdown", reply_markup=TECLADO_GPS)
        return MENU_GPS
    elif texto == "\ud83d\udda5\ufe0f Panel Web":
        if DASHBOARD_URL:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("\ud83d\udda5\ufe0f Abrir Panel", web_app=WebAppInfo(url=DASHBOARD_URL))]])
            await update.message.reply_text("\ud83d\udda5\ufe0f *Panel de Control*", parse_mode="Markdown", reply_markup=keyboard)
        else:
            await update.message.reply_text("\u26a0\ufe0f Panel web no configurado.")
        return MENU_PRINCIPAL
    elif texto == "\ud83d\udeaa Salir":
        await update.message.reply_text("\ud83d\udc4b Hasta luego!", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    await update.message.reply_text("Selecciona una opci\u00f3n:", reply_markup=TECLADO_MENU)
    return MENU_PRINCIPAL

async def buscar_cedula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cedula = update.message.text.strip()
    modo   = context.user_data.get('modo', 'cedula')
    if not cedula.isdigit():
        await update.message.reply_text("\u274c Solo n\u00fameros. Intenta de nuevo:")
        return ESPERANDO_CEDULA
    await update.message.reply_text("\ud83d\udd0d Consultando...")
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
                msg = "\u26a0\ufe0f No se encontr\u00f3 n\u00facleo familiar."
            else:
                with con.cursor() as cur:
                    cur.execute("SELECT apellido_a,apellido_b,nombre_a,nombre_b,doc_num,fec_nac,puntaje,nivel,zona,localidad,direccion,telefono FROM sisben_n WHERE ficha=%s ORDER BY persona", (row['ficha'],))
                    ints = cur.fetchall()
                con.close()
                if not ints:
                    msg = "\u26a0\ufe0f N\u00facleo vac\u00edo."
                else:
                    msg = f"\ud83c\udfe0 *N\u00facleo Familiar* \u2014 {len(ints)} integrante(s)\n\n"
                    for r in ints:
                        msg += f"\ud83d\udc64 *{v(r.get('apellido_a'))} {v(r.get('apellido_b'))} {v(r.get('nombre_a'))} {v(r.get('nombre_b'))}*\n"
                        msg += f"\ud83d\udccb `{v(r.get('doc_num'))}` | \ud83d\udcc5 {v(r.get('fec_nac'))}\n"
                        if v(r.get('puntaje')): msg += f"\ud83d\udcca Puntaje: *{v(r.get('puntaje'))}* Nivel: *{v(r.get('nivel'))}*\n"
                        if v(r.get('localidad')): msg += f"\ud83d\udccd {v(r.get('localidad'))}\n"
                        if v(r.get('telefono')):  msg += f"\ud83d\udcde {v(r.get('telefono'))}\n"
                        msg += f"{'\u2500'*22}\n"
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
                msg = f"\ud83d\udcde *Datos de Contacto* `{cedula}`\n\n"
                if r1:
                    msg += f"\ud83d\udc64 *{v(r1.get('APELLIDO1'))} {v(r1.get('APELLIDO2'))}* \u2014 {v(r1.get('NOMBRE'))}\n"
                    if r1.get('CEL1'):      msg += f"\ud83d\udcf1 {v(r1.get('CEL1'))}\n"
                    if r1.get('CEL2'):      msg += f"\ud83d\udcf1 {v(r1.get('CEL2'))}\n"
                    if r1.get('TELEFONO'):  msg += f"\ud83d\udcde {v(r1.get('TELEFONO'))}\n"
                    if r1.get('DIRECCION'): msg += f"\ud83c\udfe0 {v(r1.get('DIRECCION'))}\n"
                    if r1.get('CIUDAD'):    msg += f"\ud83c\udf06 {v(r1.get('CIUDAD'))}\n"
                if r2:
                    msg += f"\n{'\u2500'*22}\n\ud83d\udc64 {v(r2.get('papellido'))} {v(r2.get('sapellido'))} {v(r2.get('nombres'))}\n"
                    if r2.get('celular'):   msg += f"\ud83d\udcf1 {v(r2.get('celular'))}\n"
                    if r2.get('direccion'): msg += f"\ud83c\udfe0 {v(r2.get('direccion'))}\n"
                    if r2.get('ciudad'):    msg += f"\ud83c\udf06 {v(r2.get('ciudad'))}\n"