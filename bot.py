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
from database import Database  # \u2190 INTEGRACI\u00d3N MUNICIPIOS

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

# \u2500\u2500\u2500 ESTADOS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
(MENU_PRINCIPAL, ESPERANDO_CEDULA,
 ESPERANDO_NOMBRE, ESPERANDO_APELLIDO, MENU_GPS,
 GPS_CC, GPS_NAME, GPS_DIR, GPS_CEL,
 SISBEN_TIPO_DOC, SISBEN_NUM_DOC) = range(11)

# \u2500\u2500\u2500 USUARIOS APROBADOS EN MEMORIA \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
USUARIOS_APROBADOS = set()

# \u2500\u2500\u2500 INSTANCIA DB MUNICIPIOS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
db = Database()  # \u2190 INSTANCIA GLOBAL

# \u2500\u2500\u2500 TECLADOS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
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

# \u2500\u2500\u2500 HELPERS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def _con(db_name=None):
    config = dict(DB_CONFIG)
    if db_name:
        config['database'] = db_name
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

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  INICIO \u2014 Solicitud de acceso
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id  = update.effective_user.id
    username = update.effective_user.username or "sin_usuario"
    nombre   = update.effective_user.first_name or "Usuario"

    if es_admin(user_id):
        await update.message.reply_text(
            f"\ud83d\udc51 *Bienvenido Admin!*\n\nSelecciona una opci\u00f3n:",
            parse_mode="Markdown", reply_markup=TECLADO_MENU
        )
        return MENU_PRINCIPAL

    if esta_aprobado(user_id):
        await update.message.reply_text(
            f"\u2705 *Bienvenido, {nombre}!*\n\nSelecciona una opci\u00f3n:",
            parse_mode="Markdown", reply_markup=TECLADO_MENU
        )
        return MENU_PRINCIPAL

    await update.message.reply_text(
        f"\ud83d\udc4b Hola *{nombre}*!\n\n"
        f"\u23f3 Tu solicitud de acceso fue enviada al administrador.\n"
        f"Espera la aprobaci\u00f3n para continuar.",
        parse_mode="Markdown"
    )

    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("\u2705 Aprobar", callback_data=f"aprobar_{user_id}"),
                    InlineKeyboardButton("\u274c Rechazar", callback_data=f"rechazar_{user_id}")
                ]
            ])
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"\ud83d\udd14 *Nueva solicitud de acceso*\n\n"
                    f"\ud83d\udc64 Nombre: *{nombre}*\n"
                    f"\ud83c\udd94 ID: `{user_id}`\n"
                    f"\ud83d\udcdb Usuario: @{username}"
                ),
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error notificando admin {admin_id}: {e}")

    return ConversationHandler.END


# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  CALLBACK \u2014 Admin aprueba o rechaza
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
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
            await context.bot.send_message(
                chat_id=uid,
                text="\u2705 *\u00a1Acceso aprobado!*\n\nUsa /start para entrar al bot.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error notificando usuario {uid}: {e}")

    elif accion == "rechazar":
        USUARIOS_APROBADOS.discard(uid)
        await query.edit_message_text(f"\u274c Usuario `{uid}` *rechazado*.", parse_mode="Markdown")
        try:
            await context.bot.send_message(
                chat_id=uid,
                text="\u274c Tu solicitud de acceso fue *rechazada*.\n\nContacta al administrador.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error notificando usuario {uid}: {e}")

    await query.answer()


# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  COMANDOS ADMIN
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
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


# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  COMANDOS GENERALES
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = (
        "<b>\ud83d\udcda Comandos disponibles</b>\n\n"
        "<b>/start</b> \u2014 Iniciar / Solicitar acceso\n"
        "<b>/cc CEDULA</b> \u2014 Buscar por c\u00e9dula\n"
        "<b>/nombres NOMBRE AP1 AP2</b> \u2014 Buscar por nombre\n"
        "<b>/help</b> \u2014 Ver esta ayuda\n"
    )
    if es_admin(user_id):
        msg += (
            "\n<b>\ud83d\udc51 Comandos Admin:</b>\n"
            "<b>/usuarios</b> \u2014 Ver usuarios aprobados\n"
            "<b>/revocar ID</b> \u2014 Revocar acceso a un usuario\n"
        )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_cc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not esta_aprobado(user_id):
        await update.message.reply_text("\ud83d\udd10 Sin acceso. Usa /start para solicitar acceso.")
        return
    if not context.args:
        await update.message.reply_text("\u274c Uso: `/cc CEDULA`", parse_mode="Markdown")
        return
    cedula = context.args[0]
    await update.message.reply_text("\ud83d\udd0d Consultando...")
    con = None
    try:
        con = _con('ani')
        with con.cursor() as cur:
            cur.execute("SELECT * FROM ani WHERE ANINuip=%s LIMIT 1", (cedula,))
            r = cur.fetchone()
        if r:
            # \u2500\u2500\u2500 MUNICIPIO DE NACIMIENTO \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
            lugar = db.get_municipio(v(r.get('ANILugNacimiento', '')))
            lugar_str = f"\ud83c\udfe0 Naci\u00f3 en: *{lugar}*\n" if lugar else ""
            # \u2500\u2500