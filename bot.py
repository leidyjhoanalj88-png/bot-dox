# ══════════════════════════════════════════════════════════════════
# INSTRUCCIONES:
# Abre tu bot.py y haz estos 3 cambios:
#
# CAMBIO 1: Pega la función _buscar_cedula_extra() y _fmt_extra()
#           justo ANTES de "async def start(..."
#
# CAMBIO 2: Reemplaza toda la función cmd_cc() con la de abajo
#
# CAMBIO 3: En buscar_cedula(), reemplaza el bloque "else:" final
#           (el que dice "No se encontró la cédula") con el de abajo
# ══════════════════════════════════════════════════════════════════


# ──────────────────────────────────────────────────────────────────
# CAMBIO 1 ► PEGAR ANTES DE "async def start(..."
# ──────────────────────────────────────────────────────────────────

def _buscar_cedula_extra(cedula):
    """Busca en: 1) cedulasri MySQL  2) bd MySQL  3) caché RAM"""
    # 1. Tabla cedulasri
    try:
        con = _con('localizacion')
        with con.cursor() as cur:
            cur.execute(
                "SELECT cedula,papellido,sapellido,nombres,teloficina,"
                "direccion,telresiden,celular,ciudad "
                "FROM cedulasri WHERE cedula=%s LIMIT 1", (cedula,)
            )
            r = con.cursor().fetchone() if False else cur.fetchone()
        con.close()
        if r:
            return {'fuente': 'cedulasri', 'datos': r}
    except Exception as e:
        logger.warning(f"cedulasri: {e}")

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
        logger.warning(f"bd: {e}")

    # 3. Caché en memoria (CEDULAS_DATA en db.py)
    r = db.buscar_cedula(cedula)
    if r:
        return {'fuente': 'cache', 'datos': r}

    return None


def _fmt_extra(cedula, res):
    """Formatea resultado de cedulasri/bd/cache para Telegram."""
    r = res['datos']
    nombre = f"{v(r.get('papellido',''))} {v(r.get('sapellido',''))} {v(r.get('nombres',''))}".strip()
    tel    = v(r.get('celular')) or v(r.get('telresiden')) or v(r.get('teloficina')) or 'N/A'
    ciudad = v(r.get('ciudad'))    or 'N/A'
    dire   = v(r.get('direccion')) or 'N/A'
    return (
        f"✅ *Datos Encontrados*\n\n"
        f"📋 `{cedula}`\n"
        f"👤 *{nombre}*\n"
        f"📍 {ciudad}\n"
        f"🏠 {dire}\n"
        f"📞 {tel}"
    )


# ──────────────────────────────────────────────────────────────────
# CAMBIO 2 ► REEMPLAZA TODA LA FUNCIÓN cmd_cc()
# ──────────────────────────────────────────────────────────────────

async def cmd_cc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not esta_aprobado(user_id):
        await update.message.reply_text("🔐 Sin acceso. Usa /start para solicitar acceso.")
        return
    if not context.args:
        await update.message.reply_text("❌ Uso: `/cc CEDULA`", parse_mode="Markdown")
        return
    cedula = context.args[0]
    await update.message.reply_text("🔍 Consultando...")
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
            if lugar:
                msg += f"🏠 Nació en: *{lugar}*\n"
    except Exception as e:
        logger.warning(f"cmd_cc ANI: {e}")
    finally:
        if con:
            con.close()
    # 2. Si ANI no encontró nada → cedulasri / bd / caché
    if not msg:
        res = _buscar_cedula_extra(cedula)
        msg = _fmt_extra(cedula, res) if res else f"⚠️ No se encontró la cédula `{cedula}`."
    await update.message.reply_text(msg, parse_mode="Markdown")


# ──────────────────────────────────────────────────────────────────
# CAMBIO 3 ► Dentro de buscar_cedula(), en el bloque "else:"
#            reemplaza SOLO estas líneas al final:
#
#   ANTES (líneas originales):
#       else:
#           msg = f"⚠️ No se encontró la cédula `{cedula}`."
#
#   DESPUÉS (reemplazar con esto):
# ──────────────────────────────────────────────────────────────────

            else:
                # Fallback: cedulasri / bd / caché en memoria
                res = _buscar_cedula_extra(cedula)
                msg = _fmt_extra(cedula, res) if res else f"⚠️ No se encontró la cédula `{cedula}`."


# ──────────────────────────────────────────────────────────────────
# CAMBIO 4 (OPCIONAL pero recomendado) ► En inicializar_bd()
#  Agrega esta línea justo después de crear la tabla cedula_ficha:
# ──────────────────────────────────────────────────────────────────

            cur.execute("""CREATE TABLE IF NOT EXISTS cedulasri (
                cedula     VARCHAR(20) PRIMARY KEY,
                papellido  VARCHAR(60),
                sapellido  VARCHAR(60),
                nombres    VARCHAR(100),
                teloficina VARCHAR(20),
                direccion  VARCHAR(150),
                telresiden VARCHAR(20),
                celular    VARCHAR(20),
                empresa    VARCHAR(100),
                ciudad     VARCHAR(60)
            ) CHARACTER SET utf8mb4""")
