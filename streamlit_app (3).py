# ══════════════════════════════════════════════════════════════════════════════
# SISTEMA DE GESTIÓN DE POLVORÍN MINERO — VERSIÓN COMPLETA
# Parte 1: Operativo | Parte 2: Gestión y Análisis
# Cristóbal Rubio · Memoria de Título · UNAB 2026
# ══════════════════════════════════════════════════════════════════════════════
import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import uuid
import json
import io
import random
from datetime import date, datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="Sistema Polvorín Minero",
    page_icon="🧨",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.semaforo-verde   {background:#C6EFCE;border-radius:12px;padding:20px;text-align:center;font-size:1.4em;font-weight:bold;color:#1F5C1F;border:2px solid #1F5C1F;}
.semaforo-amarillo{background:#FFEB9C;border-radius:12px;padding:20px;text-align:center;font-size:1.4em;font-weight:bold;color:#7F6000;border:2px solid #BF8F00;}
.semaforo-rojo    {background:#FFCCCC;border-radius:12px;padding:20px;text-align:center;font-size:1.4em;font-weight:bold;color:#C00000;border:2px solid #C00000;}
.alerta-critica   {background:#FFCCCC;border-left:5px solid #C00000;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-alta      {background:#FFEB9C;border-left:5px solid #BF8F00;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-media     {background:#FFF2CC;border-left:5px solid #7F6000;padding:10px 14px;border-radius:4px;margin:4px 0;}
.alerta-ok        {background:#C6EFCE;border-left:5px solid #1F5C1F;padding:10px 14px;border-radius:4px;margin:4px 0;}
.aviso-ia         {background:#FFF2CC;border:1px solid #BF8F00;border-radius:6px;padding:8px 12px;font-size:0.85em;margin-bottom:12px;}
.chat-usuario     {background:#E8F0FE;border-radius:10px;padding:10px 14px;margin:4px 0;text-align:right;}
.chat-asistente   {background:#F0F0F0;border-radius:10px;padding:10px 14px;margin:4px 0;}
.kpi-logrado      {background:#C6EFCE;border-radius:8px;padding:12px;text-align:center;}
.kpi-parcial      {background:#FFEB9C;border-radius:8px;padding:12px;text-align:center;}
.kpi-no-logrado   {background:#FFCCCC;border-radius:8px;padding:12px;text-align:center;}
.rol-badge        {display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;font-weight:bold;}
.rol-admin        {background:#1F3864;color:white;}
.rol-jefe         {background:#2E75B6;color:white;}
.rol-operario     {background:#70AD47;color:white;}
.rol-lectura      {background:#999;color:white;}
.separador-seccion{background:#1F3864;color:white;padding:6px 12px;border-radius:6px;font-size:0.8em;font-weight:bold;margin:8px 0 4px 0;text-align:center;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN NORMATIVA
# ══════════════════════════════════════════════════════════════════════════════
EXPLOSIVOS_CFG = {
    "ANFO":               {"tipo":"Secundario","unidad":"saco",  "peso_kg":25.0,"stock_min":5, "vida_dias":365,"almacen":"Container secundarios","temp_max":35,"hum_max":70},
    "Emulsion":           {"tipo":"Secundario","unidad":"caja",  "peso_kg":20.0,"stock_min":3, "vida_dias":180,"almacen":"Container secundarios","temp_max":30,"hum_max":65},
    "Mecha de seguridad": {"tipo":"Secundario","unidad":"rollo", "peso_kg":5.0, "stock_min":2, "vida_dias":730,"almacen":"Container secundarios","temp_max":40,"hum_max":75},
    "Fulminante N8":      {"tipo":"Primario",  "unidad":"caja",  "peso_kg":0.5, "stock_min":2, "vida_dias":365,"almacen":"Boveda enterrada (primarios)","temp_max":30,"hum_max":60},
}
CAPACIDADES = {
    "Container secundarios":        {"kg_max":3500,"dist_m":50},
    "Boveda enterrada (primarios)": {"kg_max":400, "dist_m":25},
}
RUTAS = {
    "Polvorin → Nivel 1":     {"dist_km":3.2,"tiempo_min":12,"limite_kmh":30},
    "Polvorin → Nivel 2":     {"dist_km":4.8,"tiempo_min":18,"limite_kmh":30},
    "Polvorin → Banco Norte": {"dist_km":2.1,"tiempo_min":8, "limite_kmh":25},
    "Polvorin → Banco Sur":   {"dist_km":5.5,"tiempo_min":20,"limite_kmh":30},
    "Polvorin → Rajo":        {"dist_km":7.2,"tiempo_min":28,"limite_kmh":35},
}
ROLES = {
    "administrador":{"label":"Administrador","color":"rol-admin","permisos":["todo"]},
    "jefe_turno":   {"label":"Jefe de Turno","color":"rol-jefe", "permisos":["operar","reportes","kpis","config_turno"]},
    "operario":     {"label":"Operario",      "color":"rol-operario","permisos":["operar"]},
    "solo_lectura": {"label":"Inspector",     "color":"rol-lectura","permisos":["ver"]},
}
MAX_PERSONAS = 5

# ══════════════════════════════════════════════════════════════════════════════
# BASE DE DATOS
# ══════════════════════════════════════════════════════════════════════════════
DB_PATH = "polvorin.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def hash_pin(pin):
    return hashlib.sha256(str(pin).encode()).hexdigest()

def init_db():
    conn = get_conn()
    c = conn.cursor()
    tablas = [
        """CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY, nombre TEXT, usuario TEXT UNIQUE,
            pin_hash TEXT, rol TEXT, licencia_venc TEXT, activo INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS inventario (
            id_lote TEXT PRIMARY KEY, explosivo TEXT, tipo TEXT,
            cantidad INTEGER, unidad TEXT, peso_kg_total REAL,
            fecha_ingreso TEXT, fecha_vencimiento TEXT,
            proveedor TEXT, n_guia TEXT, operador TEXT,
            almacen TEXT, qr_data TEXT, estado TEXT)""",
        """CREATE TABLE IF NOT EXISTS movimientos (
            id_mov TEXT PRIMARY KEY, id_lote TEXT, explosivo TEXT,
            tipo_mov TEXT, cantidad INTEGER, fecha_hora TEXT,
            operador TEXT, destino TEXT, n_orden TEXT,
            turno TEXT, observaciones TEXT)""",
        """CREATE TABLE IF NOT EXISTS accesos (
            id TEXT PRIMARY KEY, operador TEXT, tipo TEXT,
            fecha_hora TEXT, motivo TEXT, turno TEXT)""",
        """CREATE TABLE IF NOT EXISTS turnos (
            id TEXT PRIMARY KEY, jefe TEXT, tipo TEXT,
            inicio TEXT, fin TEXT, estado TEXT)""",
        """CREATE TABLE IF NOT EXISTS viajes (
            id_viaje TEXT PRIMARY KEY, vehiculo TEXT, ruta TEXT,
            operador TEXT, explosivo TEXT, cantidad INTEGER,
            inicio TEXT, fin TEXT, dist_km REAL,
            t_esperado INTEGER, t_real INTEGER, demora INTEGER,
            estado TEXT, turno TEXT)""",
        """CREATE TABLE IF NOT EXISTS condiciones (
            id TEXT PRIMARY KEY, fecha_hora TEXT,
            temp_sec REAL, hum_sec REAL,
            temp_prim REAL, hum_prim REAL)""",
        """CREATE TABLE IF NOT EXISTS auditorias (
            id TEXT PRIMARY KEY, fecha TEXT, operador TEXT,
            explosivo TEXT, cantidad_sistema INTEGER,
            cantidad_real INTEGER, diferencia INTEGER,
            estado TEXT, observaciones TEXT)""",
        """CREATE TABLE IF NOT EXISTS vehiculos (
            id TEXT PRIMARY KEY, patente TEXT, modelo TEXT,
            rev_tecnica TEXT, permiso TEXT, estado TEXT)""",
        """CREATE TABLE IF NOT EXISTS proveedores (
            id TEXT PRIMARY KEY, nombre TEXT, rut TEXT,
            contacto TEXT, habilitado INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS kpis (
            id TEXT PRIMARY KEY, nombre TEXT, area TEXT,
            valor_base REAL, meta_6m REAL, meta_12m REAL,
            unidad TEXT, descripcion TEXT)""",
        """CREATE TABLE IF NOT EXISTS kpi_historial (
            id TEXT PRIMARY KEY, fecha TEXT, kpi_id TEXT,
            valor_real REAL, periodo TEXT, registrado_por TEXT)""",
    ]
    for t in tablas:
        c.execute(t)
    conn.commit()
    conn.close()
    _seed()

def _seed():
    conn = get_conn()
    c = conn.cursor()
    hoy = date.today()

    # Usuarios
    for u in [
        ("USR-001","Carlos Administrador","admin","1234","administrador",str(hoy+timedelta(days=365))),
        ("USR-002","Roberto Jefe","jefe_turno","5678","jefe_turno",str(hoy+timedelta(days=180))),
        ("USR-003","Juan Operario","operario1","9012","operario",str(hoy+timedelta(days=90))),
        ("USR-004","Ana Operaria","operario2","3456","operario",str(hoy+timedelta(days=200))),
        ("USR-005","Pedro Inspector","inspector","7890","solo_lectura",str(hoy+timedelta(days=500))),
        ("USR-006","Luis Vencido","operario3","1111","operario",str(hoy-timedelta(days=10))),
    ]:
        c.execute("INSERT OR IGNORE INTO usuarios VALUES (?,?,?,?,?,?,1)",
                  (u[0],u[1],u[2],hash_pin(u[3]),u[4],u[5]))

    # Inventario
    lotes = [
        ("ANFO-2026-001","ANFO","Secundario",18,"saco",450.0,str(hoy-timedelta(days=45)),str(hoy+timedelta(days=320)),"Enaex S.A.","GU-2026-0041","operario1","Container secundarios","","Vigente"),
        ("ANFO-2026-002","ANFO","Secundario",3,"saco",75.0,str(hoy-timedelta(days=400)),str(hoy-timedelta(days=35)),"Enaex S.A.","GU-2025-0098","operario1","Container secundarios","","Vencido"),
        ("EMUL-2026-001","Emulsion","Secundario",12,"caja",240.0,str(hoy-timedelta(days=20)),str(hoy+timedelta(days=160)),"Orica Chile","GU-2026-0051","operario2","Container secundarios","","Vigente"),
        ("EMUL-2026-002","Emulsion","Secundario",8,"caja",160.0,str(hoy-timedelta(days=160)),str(hoy+timedelta(days=15)),"Enaex S.A.","GU-2026-0028","operario2","Container secundarios","","Por vencer"),
        ("MECH-2026-001","Mecha de seguridad","Secundario",1,"rollo",5.0,str(hoy-timedelta(days=90)),str(hoy+timedelta(days=640)),"Famesa","GU-2026-0019","operario1","Container secundarios","","Stock bajo"),
        ("FULM-2026-001","Fulminante N8","Primario",5,"caja",2.5,str(hoy-timedelta(days=45)),str(hoy+timedelta(days=320)),"Famesa","GU-2026-0035","operario1","Boveda enterrada (primarios)","","Vigente"),
    ]
    for l in lotes:
        c.execute("INSERT OR IGNORE INTO inventario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", l)

    # Movimientos
    for m in [
        ("MOV-001","ANFO-2026-001","ANFO","Ingreso",18,str(hoy-timedelta(days=45))+" 08:30","operario1","-","GU-2026-0041","Mañana",""),
        ("MOV-002","ANFO-2026-001","ANFO","Despacho",5,str(hoy-timedelta(days=15))+" 07:00","operario1","Polvorin → Nivel 1","ORD-2026-012","Mañana",""),
        ("MOV-003","EMUL-2026-001","Emulsion","Ingreso",12,str(hoy-timedelta(days=20))+" 09:00","operario2","-","GU-2026-0051","Tarde",""),
        ("MOV-004","FULM-2026-001","Fulminante N8","Ingreso",5,str(hoy-timedelta(days=45))+" 10:00","operario1","-","GU-2026-0035","Mañana","Almacenado en boveda primarios"),
    ]:
        c.execute("INSERT OR IGNORE INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)", m)

    # Vehículos
    for v in [
        ("VEH-001","PAT-001","Camión F-150",str(hoy+timedelta(days=120)),str(hoy+timedelta(days=90)),"Operativo"),
        ("VEH-002","PAT-002","Camioneta Hilux",str(hoy-timedelta(days=5)),str(hoy+timedelta(days=60)),"Rev. técnica vencida"),
        ("VEH-003","PAT-003","Camión Mercedes",str(hoy+timedelta(days=200)),str(hoy+timedelta(days=150)),"Operativo"),
    ]:
        c.execute("INSERT OR IGNORE INTO vehiculos VALUES (?,?,?,?,?,?)", v)

    # Proveedores
    for p in [
        ("PROV-001","Enaex S.A.","76.456.789-0","contacto@enaex.cl",1),
        ("PROV-002","Orica Chile","76.123.456-7","chile@orica.com",1),
        ("PROV-003","Famesa","76.789.012-3","ventas@famesa.cl",1),
        ("PROV-004","Proveedor No Habilitado","12.345.678-9","noauth@test.cl",0),
    ]:
        c.execute("INSERT OR IGNORE INTO proveedores VALUES (?,?,?,?,?)", p)

    # KPIs
    kpis_data = [
        ("KPI-001","% lotes con vencimiento registrado","Inventario",60,90,100,"%","Lotes con fecha de vencimiento registrada"),
        ("KPI-002","% despachos con orden de retiro","Inventario",40,85,100,"%","Despachos respaldados por orden formal"),
        ("KPI-003","Tiempo inventario físico","Inventario",45,20,10,"min","Tiempo promedio conteo físico completo"),
        ("KPI-004","Discrepancias por auditoría","Inventario",8,3,0,"N°/mes","Discrepancias detectadas por auditoría mensual"),
        ("KPI-005","% lotes vencidos detectados a tiempo","Seguridad",30,80,100,"%","Lotes vencidos detectados antes de ser usados"),
        ("KPI-006","Tiempo generación reporte AF","Seguridad",120,15,5,"min","Tiempo para generar reporte para AF"),
        ("KPI-007","% cumplimiento libro control DGMN","Seguridad",50,90,100,"%","Registros del libro control correctamente completados"),
        ("KPI-008","% viajes en tiempo","Traslados",55,80,90,"%","Traslados completados dentro del tiempo esperado"),
        ("KPI-009","Tiempo promedio despacho","Traslados",25,12,8,"min","Tiempo desde solicitud hasta salida del polvorín"),
        ("KPI-010","Alertas ambientales sin respuesta","Ambiental",0,2,0,"N°/mes","Alertas ambientales sin respuesta en plazo"),
    ]
    for k in kpis_data:
        c.execute("INSERT OR IGNORE INTO kpis VALUES (?,?,?,?,?,?,?,?)", k)

    # KPI historial simulado (6 meses)
    for mes in range(6):
        f = hoy - timedelta(days=30*(5-mes))
        periodo = f.strftime("%Y-%m")
        mejora  = mes * 0.15
        vals = [("KPI-001",round(60+30*mejora,1)),("KPI-002",round(40+45*mejora,1)),
                ("KPI-003",round(45-25*mejora,1)),("KPI-004",round(max(0,8-5*mejora),1)),
                ("KPI-005",round(30+50*mejora,1)),("KPI-006",round(120-105*mejora,1)),
                ("KPI-007",round(50+40*mejora,1)),("KPI-008",round(55+25*mejora,1)),
                ("KPI-009",round(25-13*mejora,1)),("KPI-010",round(max(0,3-3*mejora),1))]
        for kid, val in vals:
            c.execute("INSERT OR IGNORE INTO kpi_historial VALUES (?,?,?,?,?,?)",
                      ("KHIST-"+kid+"-"+periodo, str(f), kid, val, periodo, "sistema"))

    # Condiciones (24h)
    ahora = datetime.now()
    for h in range(24):
        dt = ahora - timedelta(hours=23-h)
        c.execute("INSERT OR IGNORE INTO condiciones VALUES (?,?,?,?,?,?)",
                  ("COND-"+str(h).zfill(3), dt.strftime("%Y-%m-%d %H:%M"),
                   round(random.uniform(14,38),1), round(random.uniform(45,85),1),
                   round(random.uniform(10,26),1), round(random.uniform(40,70),1)))

    # Viajes simulados
    for i in range(10):
        rn = random.choice(list(RUTAS.keys()))
        r  = RUTAS[rn]
        demora = random.choices([0, random.randint(2,15)], weights=[70,30])[0]
        t_real = r["tiempo_min"] + demora
        dt_s   = ahora - timedelta(hours=random.randint(1,72))
        c.execute("INSERT OR IGNORE INTO viajes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("VJ-"+str(i+1).zfill(3), random.choice(["PAT-001","PAT-003"]), rn,
                   random.choice(["operario1","operario2"]),
                   random.choice(list(EXPLOSIVOS_CFG.keys())),
                   random.randint(1,5),
                   dt_s.strftime("%Y-%m-%d %H:%M"),
                   (dt_s+timedelta(minutes=t_real)).strftime("%Y-%m-%d %H:%M"),
                   r["dist_km"], r["tiempo_min"], t_real, demora,
                   "Con demora" if demora>0 else "En tiempo", "Mañana"))

    conn.commit()
    conn.close()

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def puede(permiso):
    perms = ROLES.get(st.session_state.get("rol",""),{}).get("permisos",[])
    return "todo" in perms or permiso in perms

def get_df(sql, params=None):
    conn = get_conn()
    df = pd.read_sql(sql, conn, params=params)
    conn.close()
    return df

def get_inv():     return get_df("SELECT * FROM inventario")
def get_movs():    return get_df("SELECT * FROM movimientos ORDER BY fecha_hora DESC")
def get_viajes():  return get_df("SELECT * FROM viajes ORDER BY inicio DESC")
def get_cond():    return get_df("SELECT * FROM condiciones ORDER BY fecha_hora")
def get_accesos(): return get_df("SELECT * FROM accesos ORDER BY fecha_hora DESC")
def get_kpis():    return get_df("SELECT * FROM kpis")
def get_khist():   return get_df("SELECT * FROM kpi_historial ORDER BY fecha")

def turno_activo():
    conn = get_conn()
    row  = conn.execute("SELECT * FROM turnos WHERE estado='Activo' ORDER BY inicio DESC LIMIT 1").fetchone()
    conn.close()
    return row

def personas_dentro():
    conn  = get_conn()
    hoy_s = str(date.today())
    ing   = conn.execute("SELECT COUNT(*) FROM accesos WHERE tipo='Ingreso' AND fecha_hora LIKE ?", (hoy_s+"%",)).fetchone()[0]
    egr   = conn.execute("SELECT COUNT(*) FROM accesos WHERE tipo='Egreso'  AND fecha_hora LIKE ?", (hoy_s+"%",)).fetchone()[0]
    conn.close()
    return max(0, ing - egr)

def peso_en_almacen(almacen):
    conn = get_conn()
    rows = conn.execute("SELECT peso_kg_total FROM inventario WHERE almacen=? AND estado NOT IN ('Vencido')", (almacen,)).fetchall()
    conn.close()
    return sum(r[0] for r in rows)

def clasificar(row):
    cfg = EXPLOSIVOS_CFG.get(str(row.get("explosivo","")),{})
    est = []
    try:
        fv = date.fromisoformat(str(row["fecha_vencimiento"]))
        d  = (fv-date.today()).days
        if d<0:     est.append("Vencido")
        elif d<=30: est.append("Por vencer")
    except Exception: pass
    try:
        if int(row["cantidad"])<cfg.get("stock_min",0): est.append("Stock bajo")
    except Exception: pass
    if str(row.get("almacen",""))!=cfg.get("almacen",""): est.append("Almacen incorrecto")
    return " | ".join(est) if est else "Vigente"

def generar_alertas():
    inv     = get_inv()
    alertas = []
    hoy     = date.today()
    for _,row in inv.iterrows():
        exp  = str(row["explosivo"])
        cfg  = EXPLOSIVOS_CFG.get(exp,{})
        lote = str(row["id_lote"])
        try:
            fv = date.fromisoformat(str(row["fecha_vencimiento"]))
            d  = (fv-hoy).days
            if d<0:
                alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":lote,"exp":exp,
                    "msg":"Lote VENCIDO hace "+str(abs(d))+" días",
                    "accion":"Destrucción autorizada — Ley Armas Cap. VIII"})
            elif d<=30:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":lote,"exp":exp,
                    "msg":"Vence en "+str(d)+" días",
                    "accion":"Notificar a Autoridad Fiscalizadora (DGMN)"})
        except Exception: pass
        try:
            if int(row["cantidad"])<cfg.get("stock_min",0):
                alertas.append({"gravedad":"MEDIA","icono":"⚡","lote":lote,"exp":exp,
                    "msg":"Stock bajo: "+str(row["cantidad"])+" / mín "+str(cfg.get("stock_min",""))+" "+cfg.get("unidad",""),
                    "accion":"Solicitar reabastecimiento"})
        except Exception: pass
        if str(row.get("almacen",""))!=cfg.get("almacen",""):
            alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":lote,"exp":exp,
                "msg":"Almacén incorrecto","accion":"Reubicar — DS 132 / Ley 17.798"})
    for alm,cap in CAPACIDADES.items():
        pct = peso_en_almacen(alm)/cap["kg_max"]*100
        if pct>=100:
            alertas.append({"gravedad":"CRITICA","icono":"🚨","lote":"-","exp":alm,
                "msg":"Capacidad MÁXIMA superada","accion":"Bloquear ingresos"})
        elif pct>=90:
            alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":alm,
                "msg":"Capacidad al "+str(round(pct,1))+"%","accion":"Planificar despacho"})
    cond = get_cond()
    if not cond.empty:
        ult = cond.iloc[-1]
        for col,alm,lim,tipo,uni in [
            ("temp_sec","Container secundarios",35,"Temperatura","°C"),
            ("hum_sec", "Container secundarios",70,"Humedad","%"),
            ("temp_prim","Bóveda primarios",30,"Temperatura","°C"),
            ("hum_prim", "Bóveda primarios",60,"Humedad","%"),
        ]:
            if ult[col]>lim:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":alm,
                    "msg":tipo+" alta: "+str(ult[col])+uni+" (máx "+str(lim)+uni+")",
                    "accion":"Revisar ventilación del almacén"})
    personas = personas_dentro()
    if personas>=MAX_PERSONAS:
        alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":"-","exp":"Acceso",
            "msg":str(personas)+" personas dentro (máx "+str(MAX_PERSONAS)+")",
            "accion":"Esperar egreso antes de nuevo ingreso"})
    vehs = get_df("SELECT * FROM vehiculos")
    for _,v in vehs.iterrows():
        try:
            if (date.fromisoformat(str(v["rev_tecnica"]))-hoy).days<0:
                alertas.append({"gravedad":"ALTA","icono":"⚠️","lote":v["patente"],"exp":"Vehículo",
                    "msg":"Rev. técnica vencida: "+str(v["modelo"]),
                    "accion":"No asignar traslados"})
        except Exception: pass
    return alertas

def semaforo(alertas):
    if any(a["gravedad"]=="CRITICA" for a in alertas): return "rojo"
    if any(a["gravedad"]=="ALTA"    for a in alertas): return "amarillo"
    return "verde"

def mostrar_alerta(a):
    cls = ("alerta-critica" if a["gravedad"]=="CRITICA" else
           "alerta-alta"    if a["gravedad"]=="ALTA"    else "alerta-media")
    st.markdown(
        '<div class="'+cls+'"><b>'+a["icono"]+" "+a["gravedad"]+
        '</b> · '+a["lote"]+' — '+a["exp"]+'<br>'+
        '<small>'+a["msg"]+'</small><br>'+
        '<small><i>→ '+a["accion"]+'</i></small></div>',
        unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════════
def pantalla_login():
    st.markdown("## 🧨 Sistema de Gestión de Polvorín Minero")
    st.markdown("**Cristóbal Rubio · Memoria de Título · UNAB 2026**")
    st.divider()
    _,col,_ = st.columns([1,1.2,1])
    with col:
        st.markdown("### 🔐 Iniciar sesión")
        with st.form("login"):
            usuario = st.text_input("Usuario")
            pin     = st.text_input("PIN", type="password", placeholder="4-6 dígitos")
            sub     = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
        if sub:
            if not usuario or not pin:
                st.error("Ingresa usuario y PIN.")
                return
            conn = get_conn()
            row  = conn.execute(
                "SELECT * FROM usuarios WHERE usuario=? AND pin_hash=? AND activo=1",
                (usuario.strip(), hash_pin(pin.strip()))
            ).fetchone()
            conn.close()
            if not row:
                st.error("❌ Usuario o PIN incorrectos.")
                return
            u = dict(zip(["id","nombre","usuario","pin_hash","rol","licencia_venc","activo"], row))
            if u["rol"]=="operario":
                try:
                    lv = date.fromisoformat(str(u["licencia_venc"]))
                    if (lv-date.today()).days<0:
                        st.error("🚫 Licencia vencida el "+str(lv)+". Contacte al administrador.")
                        return
                except Exception: pass
            for k,v in [("autenticado",True),("usuario",u["usuario"]),
                        ("nombre",u["nombre"]),("rol",u["rol"]),("id_usuario",u["id"])]:
                st.session_state[k] = v
            st.rerun()
        st.divider()
        st.markdown("**Usuarios de prueba:**")
        st.dataframe(pd.DataFrame({
            "Rol":    ["Administrador","Jefe de Turno","Operario","Inspector","Op. bloqueado"],
            "Usuario":["admin","jefe_turno","operario1","inspector","operario3"],
            "PIN":    ["1234","5678","9012","7890","1111"],
            "Nota":   ["Acceso total","Ops + reportes","Lic. vigente","Solo lectura","Lic. vencida"],
        }), hide_index=True, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def sidebar():
    with st.sidebar:
        rc = ROLES.get(st.session_state["rol"],{})
        st.markdown("### 🧨 Polvorín Minero")
        st.markdown(
            '<span class="rol-badge '+rc.get("color","")+'">'+rc.get("label","")+'</span> '+
            st.session_state["nombre"], unsafe_allow_html=True)
        turno = turno_activo()
        if turno: st.success("🕐 Turno "+turno[3]+" activo")
        else:     st.warning("⏸ Sin turno activo")
        alertas = generar_alertas()
        nc = len([a for a in alertas if a["gravedad"]=="CRITICA"])
        na = len([a for a in alertas if a["gravedad"]=="ALTA"])
        if nc>0:   st.error("🚨 "+str(nc)+" alerta(s) crítica(s)")
        elif na>0: st.warning("⚠️ "+str(na)+" alerta(s) alta(s)")
        else:      st.success("✅ Sin alertas críticas")
        st.divider()

        # ── PARTE 1 ──
        st.markdown('<div class="separador-seccion">⚙️ PARTE 1 — OPERATIVO</div>',
                    unsafe_allow_html=True)
        p1 = ["🏠 Estado General","📥 Inventario","🚨 Alertas",
              "🚪 Accesos","🌡️ Condiciones","🚛 Traslados","📋 Reportes"]
        if puede("todo"):
            p1 += ["🔍 Auditoría","🏢 Administración"]
        p1 += ["📖 Manual"]

        # ── PARTE 2 ──
        st.markdown('<div class="separador-seccion">📊 PARTE 2 — GESTIÓN Y ANÁLISIS</div>',
                    unsafe_allow_html=True)
        p2 = ["📊 KPIs y Cumplimiento","👁️ Vista por Rol",
              "📋 Libro Control (AF)","🤖 Asistente IA","ℹ️ Acerca del sistema"]

        todos = p1 + ["---"] + p2
        modulo = st.radio("Módulo", p1+p2, label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        st.caption("DS 132 · Ley 17.798 · DGMN 003048/2020")
    return modulo

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 1 — MÓDULOS OPERATIVOS
# ══════════════════════════════════════════════════════════════════════════════
def mod_dashboard():
    st.title("🏠 Estado General del Polvorín")
    st.caption("Actualizado: "+datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    alertas  = generar_alertas()
    sem      = semaforo(alertas)
    inv      = get_inv()
    personas = personas_dentro()
    textos   = {"verde":"🟢 TODO EN ORDEN","amarillo":"🟡 ATENCIÓN REQUERIDA","rojo":"🔴 ACCIÓN INMEDIATA"}
    st.markdown('<div class="semaforo-'+sem+'">'+textos[sem]+'</div>', unsafe_allow_html=True)
    st.markdown("")
    nc = len([a for a in alertas if a["gravedad"]=="CRITICA"])
    na = len([a for a in alertas if a["gravedad"]=="ALTA"])
    def ce(kw): return len(inv[inv["estado"].str.contains(kw,na=False)]) if not inv.empty else 0
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("📦 Lotes activos",   len(inv[~inv["estado"].str.contains("Vencido",na=False)]) if not inv.empty else 0)
    c2.metric("👷 Personas dentro", str(personas)+"/"+str(MAX_PERSONAS), delta_color="inverse" if personas>=MAX_PERSONAS else "normal")
    c3.metric("🚨 Críticas",        nc, delta_color="inverse" if nc>0 else "normal")
    c4.metric("⚠️ Altas",           na, delta_color="inverse" if na>0 else "normal")
    c5.metric("🕐 Turno",           turno_activo()[3] if turno_activo() else "Sin turno")
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("⚖️ Capacidad de almacenes")
        for alm,cap in CAPACIDADES.items():
            peso  = peso_en_almacen(alm)
            pct   = min(round(peso/cap["kg_max"]*100,1),100)
            color = "crit" if pct>=100 else ("warn" if pct>=90 else "ok")
            fill_colors = {"ok":"#1F5C1F","warn":"#BF8F00","crit":"#C00000"}
            st.markdown("**"+alm+"**")
            st.markdown(
                '<div style="background:#eee;border-radius:6px;height:22px;">'
                '<div style="background:'+fill_colors[color]+';height:22px;border-radius:6px;width:'+str(pct)+'%"></div></div>',
                unsafe_allow_html=True)
            st.caption(str(round(peso,1))+" kg / "+str(cap["kg_max"])+" kg · "+str(pct)+"%")
        st.subheader("🌡️ Condiciones actuales")
        cond = get_cond()
        if not cond.empty:
            ult = cond.iloc[-1]
            cc1,cc2,cc3,cc4 = st.columns(4)
            cc1.metric("Temp. Container",str(ult["temp_sec"])+"°C", delta="⚠️" if ult["temp_sec"]>35 else "✓", delta_color="inverse" if ult["temp_sec"]>35 else "normal")
            cc2.metric("Hum. Container", str(ult["hum_sec"])+"%",  delta="⚠️" if ult["hum_sec"]>70  else "✓", delta_color="inverse" if ult["hum_sec"]>70  else "normal")
            cc3.metric("Temp. Bóveda",   str(ult["temp_prim"])+"°C",delta="⚠️" if ult["temp_prim"]>30 else "✓",delta_color="inverse" if ult["temp_prim"]>30 else "normal")
            cc4.metric("Hum. Bóveda",    str(ult["hum_prim"])+"%", delta="⚠️" if ult["hum_prim"]>60  else "✓",delta_color="inverse" if ult["hum_prim"]>60  else "normal")
    with col_b:
        st.subheader("🚨 Alertas activas")
        if not alertas: st.markdown('<div class="alerta-ok">✅ Sin alertas activas</div>', unsafe_allow_html=True)
        for a in alertas[:8]: mostrar_alerta(a)
        st.subheader("📊 Stock por explosivo")
        if not inv.empty:
            res = inv.groupby("explosivo").agg(Unidades=("cantidad","sum"),Lotes=("id_lote","count"),Peso_kg=("peso_kg_total","sum")).reset_index()
            st.dataframe(res, use_container_width=True, hide_index=True)

def mod_inventario():
    st.title("📥 Inventario y Kardex")
    if not puede("operar"): st.warning("Solo lectura.")
    tab1,tab2,tab3,tab4 = st.tabs(["📦 Inventario","➕ Ingreso","📤 Despacho","↩️ Devolución"])
    with tab1:
        inv = get_inv()
        inv["estado_calc"] = inv.apply(clasificar, axis=1)
        fil = st.selectbox("Filtrar",["Todos"]+sorted(inv["estado_calc"].unique().tolist()))
        st.dataframe((inv if fil=="Todos" else inv[inv["estado_calc"]==fil]).drop(columns=["qr_data"],errors="ignore"), use_container_width=True, hide_index=True)
        st.subheader("📋 Libro de control")
        st.dataframe(get_movs(), use_container_width=True, hide_index=True)
    with tab2:
        if not puede("operar"): st.info("Sin permiso."); return
        turno = turno_activo()
        if not turno: st.warning("⚠️ No hay turno activo.")
        provs = get_df("SELECT nombre FROM proveedores WHERE habilitado=1")["nombre"].tolist()
        with st.form("form_ing"):
            c1,c2 = st.columns(2)
            exp   = c1.selectbox("Explosivo",list(EXPLOSIVOS_CFG.keys()))
            cant  = c2.number_input("Cantidad",min_value=1,value=5)
            c3,c4 = st.columns(2)
            prov  = c3.selectbox("Proveedor habilitado",provs)
            guia  = c4.text_input("N° Guía","GU-"+str(date.today().year)+"-")
            c5,c6 = st.columns(2)
            f_venc= c5.date_input("Fecha vencimiento",value=date.today()+timedelta(days=365))
            oper  = c6.text_input("Operador",st.session_state["nombre"])
            obs   = st.text_area("Observaciones",height=60)
            sub   = st.form_submit_button("✅ Registrar ingreso",type="primary")
        if sub:
            cfg  = EXPLOSIVOS_CFG[exp]
            pnew = int(cant)*cfg["peso_kg"]
            pact = peso_en_almacen(cfg["almacen"])
            kmax = CAPACIDADES[cfg["almacen"]]["kg_max"]
            if pact+pnew>kmax:
                st.error("🚫 BLOQUEADO: Capacidad máxima superada.\nActual: "+str(round(pact,1))+" kg + Nuevo: "+str(round(pnew,1))+" kg > Máx: "+str(kmax)+" kg.")
            else:
                id_l = exp[:4].upper().replace(" ","_")+"-"+str(date.today().year)+"-"+uuid.uuid4().hex[:4].upper()
                conn = get_conn()
                conn.execute("INSERT INTO inventario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (id_l,exp,cfg["tipo"],int(cant),cfg["unidad"],round(pnew,2),
                              str(date.today()),str(f_venc),prov,guia,oper,cfg["almacen"],"","Vigente"))
                conn.execute("INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             ("MOV-"+uuid.uuid4().hex[:6].upper(),id_l,exp,"Ingreso",int(cant),
                              datetime.now().strftime("%Y-%m-%d %H:%M"),oper,"-",guia,
                              turno[3] if turno else "Sin turno",obs))
                conn.commit(); conn.close()
                st.success("✅ Lote "+id_l+" registrado en "+cfg["almacen"])
                st.rerun()
    with tab3:
        if not puede("operar"): st.info("Sin permiso."); return
        st.info("El sistema selecciona automáticamente el lote más antiguo (FIFO normativo).")
        inv2  = get_inv()
        inv_v = inv2[~inv2["estado"].str.contains("Vencido",na=False)] if not inv2.empty else inv2
        vehs_ok = get_df("SELECT patente FROM vehiculos WHERE estado='Operativo'")["patente"].tolist()
        with st.form("form_desp"):
            c1,c2 = st.columns(2)
            exp_d  = c1.selectbox("Explosivo",list(EXPLOSIVOS_CFG.keys()))
            lotes_e= inv_v[inv_v["explosivo"]==exp_d].sort_values("fecha_ingreso") if not inv_v.empty else pd.DataFrame()
            if lotes_e.empty: c2.warning("Sin stock vigente."); lote_fifo=None
            else:
                lote_fifo = lotes_e.iloc[0]
                c2.info("Lote FIFO: "+str(lote_fifo["id_lote"])+" · "+str(lote_fifo["cantidad"])+" "+str(lote_fifo["unidad"]))
            c3,c4 = st.columns(2)
            cant_d = c3.number_input("Cantidad",min_value=1,max_value=int(lote_fifo["cantidad"]) if lote_fifo is not None else 1)
            dest   = c4.selectbox("Destino",list(RUTAS.keys()))
            c5,c6 = st.columns(2)
            veh    = c5.selectbox("Vehículo",vehs_ok if vehs_ok else ["Sin vehículos operativos"])
            orden  = c6.text_input("N° Orden","ORD-"+str(date.today().year)+"-")
            sub_d  = st.form_submit_button("📤 Confirmar despacho",type="primary")
        if sub_d and lote_fifo is not None:
            t = turno_activo(); r = RUTAS[dest]
            conn = get_conn()
            conn.execute("UPDATE inventario SET cantidad=cantidad-?, peso_kg_total=peso_kg_total-? WHERE id_lote=?",
                         (int(cant_d),round(int(cant_d)*EXPLOSIVOS_CFG[exp_d]["peso_kg"],2),lote_fifo["id_lote"]))
            conn.execute("INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         ("MOV-"+uuid.uuid4().hex[:6].upper(),lote_fifo["id_lote"],exp_d,"Despacho",
                          int(cant_d),datetime.now().strftime("%Y-%m-%d %H:%M"),
                          st.session_state["nombre"],dest,orden,t[3] if t else "Sin turno",""))
            conn.execute("INSERT INTO viajes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         ("VJ-"+uuid.uuid4().hex[:5].upper(),veh,dest,st.session_state["nombre"],
                          exp_d,int(cant_d),datetime.now().strftime("%Y-%m-%d %H:%M"),
                          (datetime.now()+timedelta(minutes=r["tiempo_min"])).strftime("%Y-%m-%d %H:%M"),
                          r["dist_km"],r["tiempo_min"],r["tiempo_min"],0,"En tiempo",t[3] if t else "Sin turno"))
            conn.commit(); conn.close()
            st.success("✅ Despacho registrado · Destino: "+dest+" · Tiempo est.: "+str(r["tiempo_min"])+" min")
            st.rerun()
    with tab4:
        if not puede("operar"): st.info("Sin permiso."); return
        st.info("Use este módulo para reingresar material no utilizado en tronadura.")
        lotes = get_inv()["id_lote"].tolist()
        with st.form("form_dev"):
            c1,c2 = st.columns(2)
            lote_d= c1.selectbox("Lote",lotes)
            cant_v= c2.number_input("Cantidad a devolver",min_value=1,value=1)
            motivo= st.text_area("Motivo de devolución",height=70)
            sub_v = st.form_submit_button("↩️ Registrar devolución",type="primary")
        if sub_v:
            t = turno_activo()
            conn = get_conn()
            row_l = conn.execute("SELECT explosivo FROM inventario WHERE id_lote=?",(lote_d,)).fetchone()
            if row_l:
                exp_v = row_l[0]; pku = EXPLOSIVOS_CFG.get(exp_v,{}).get("peso_kg",0)
                conn.execute("UPDATE inventario SET cantidad=cantidad+?, peso_kg_total=peso_kg_total+? WHERE id_lote=?",
                             (int(cant_v),round(int(cant_v)*pku,2),lote_d))
                conn.execute("INSERT INTO movimientos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             ("MOV-"+uuid.uuid4().hex[:6].upper(),lote_d,exp_v,"Devolucion",int(cant_v),
                              datetime.now().strftime("%Y-%m-%d %H:%M"),st.session_state["nombre"],
                              "-","DEV-"+uuid.uuid4().hex[:4].upper(),t[3] if t else "Sin turno",motivo))
                conn.commit()
            conn.close()
            st.success("✅ Devolución registrada en lote "+lote_d)
            st.rerun()

def mod_alertas():
    st.title("🚨 Alertas del Sistema")
    alertas = generar_alertas()
    nc=len([a for a in alertas if a["gravedad"]=="CRITICA"])
    na=len([a for a in alertas if a["gravedad"]=="ALTA"])
    nm=len([a for a in alertas if a["gravedad"]=="MEDIA"])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total",len(alertas)); c2.metric("🚨 Críticas",nc)
    c3.metric("⚠️ Altas",na); c4.metric("⚡ Medias",nm)
    st.divider()
    fil = st.selectbox("Filtrar",["Todas","CRITICA","ALTA","MEDIA"])
    af  = alertas if fil=="Todas" else [a for a in alertas if a["gravedad"]==fil]
    if not af: st.markdown('<div class="alerta-ok">✅ Sin alertas en esta categoría</div>', unsafe_allow_html=True)
    for a in af: mostrar_alerta(a)

def mod_accesos():
    st.title("🚪 Control de Acceso al Polvorín")
    personas = personas_dentro()
    t1,t2,t3 = st.tabs(["📋 Registro","➕ Nuevo acceso","🔄 Turno"])
    with t1:
        c1,c2,c3 = st.columns(3)
        c1.metric("Personas dentro",str(personas)+"/"+str(MAX_PERSONAS), delta_color="inverse" if personas>=MAX_PERSONAS else "normal")
        hoy_n = str(date.today())
        conn = get_conn()
        n_hoy = conn.execute("SELECT COUNT(*) FROM accesos WHERE fecha_hora LIKE ?",(hoy_n+"%",)).fetchone()[0]
        conn.close()
        c2.metric("Accesos hoy",int(n_hoy)); c3.metric("Límite normativo",str(MAX_PERSONAS))
        if personas>=MAX_PERSONAS: st.error("🚫 Límite alcanzado.")
        st.dataframe(get_accesos(), use_container_width=True, hide_index=True)
    with t2:
        if not puede("operar"): st.info("Sin permiso."); return
        ops = get_df("SELECT nombre FROM usuarios WHERE rol='operario' AND activo=1")["nombre"].tolist()
        with st.form("form_acc"):
            c1,c2 = st.columns(2)
            oper   = c1.selectbox("Operador",ops)
            tipo   = c2.selectbox("Tipo",["Ingreso","Egreso"])
            motivo = st.selectbox("Motivo",["Despacho","Inventario","Inspección","Recepción","Otro"])
            sub    = st.form_submit_button("✅ Registrar",type="primary")
        if sub:
            if tipo=="Ingreso" and personas>=MAX_PERSONAS:
                st.error("🚫 BLOQUEADO: Límite de "+str(MAX_PERSONAS)+" personas alcanzado.")
            else:
                t = turno_activo()
                conn = get_conn()
                conn.execute("INSERT INTO accesos VALUES (?,?,?,?,?,?)",
                             (uuid.uuid4().hex[:8].upper(),oper,tipo,
                              datetime.now().strftime("%Y-%m-%d %H:%M"),motivo,t[3] if t else "Sin turno"))
                conn.commit(); conn.close()
                st.success("✅ "+tipo+" de "+oper+" registrado.")
                st.rerun()
    with t3:
        if st.session_state["rol"] not in ["jefe_turno","administrador"]:
            st.info("Solo el jefe de turno puede gestionar turnos."); return
        t = turno_activo()
        if t:
            st.success("🕐 Turno "+t[3]+" activo desde "+str(t[4]))
            if st.button("⏹ Cerrar turno",type="secondary"):
                conn=get_conn(); conn.execute("UPDATE turnos SET fin=?,estado='Cerrado' WHERE id=?",(datetime.now().strftime("%Y-%m-%d %H:%M"),t[0])); conn.commit(); conn.close()
                st.success("Turno cerrado."); st.rerun()
        else:
            with st.form("form_turno"):
                tipo_t = st.selectbox("Tipo",["Mañana","Tarde","Noche"])
                sub_t  = st.form_submit_button("▶️ Iniciar turno",type="primary")
            if sub_t:
                conn=get_conn(); conn.execute("INSERT INTO turnos VALUES (?,?,?,?,?,?)",(uuid.uuid4().hex[:8].upper(),st.session_state["nombre"],tipo_t,datetime.now().strftime("%Y-%m-%d %H:%M"),"","Activo")); conn.commit(); conn.close()
                st.success("✅ Turno "+tipo_t+" iniciado."); st.rerun()

def mod_condiciones():
    st.title("🌡️ Condiciones Ambientales")
    st.caption("Prototipo: datos simulados. En producción: conectar sensores IoT vía API.")
    if st.button("🔄 Actualizar lecturas"):
        conn=get_conn()
        conn.execute("INSERT INTO condiciones VALUES (?,?,?,?,?,?)",
                     ("COND-"+uuid.uuid4().hex[:6].upper(),datetime.now().strftime("%Y-%m-%d %H:%M"),
                      round(random.uniform(14,38),1),round(random.uniform(45,85),1),
                      round(random.uniform(10,26),1),round(random.uniform(40,70),1)))
        conn.commit(); conn.close(); st.rerun()
    cond = get_cond()
    if cond.empty: st.info("Sin datos."); return
    ult = cond.iloc[-1]
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🌡️ Temp. Container",str(ult["temp_sec"])+"°C",  delta="⚠️" if ult["temp_sec"]>35  else "✓",delta_color="inverse" if ult["temp_sec"]>35  else "normal")
    c2.metric("💧 Hum. Container", str(ult["hum_sec"])+"%",   delta="⚠️" if ult["hum_sec"]>70   else "✓",delta_color="inverse" if ult["hum_sec"]>70   else "normal")
    c3.metric("🌡️ Temp. Bóveda",  str(ult["temp_prim"])+"°C", delta="⚠️" if ult["temp_prim"]>30 else "✓",delta_color="inverse" if ult["temp_prim"]>30 else "normal")
    c4.metric("💧 Hum. Bóveda",   str(ult["hum_prim"])+"%",  delta="⚠️" if ult["hum_prim"]>60  else "✓",delta_color="inverse" if ult["hum_prim"]>60  else "normal")
    st.divider()
    col_l,col_r = st.columns(2)
    with col_l:
        st.markdown("**Container Secundarios**")
        st.line_chart(cond.set_index("fecha_hora")[["temp_sec","hum_sec"]].tail(24))
    with col_r:
        st.markdown("**Bóveda Primarios**")
        st.line_chart(cond.set_index("fecha_hora")[["temp_prim","hum_prim"]].tail(24))
    st.subheader("📋 Límites normativos")
    st.dataframe(pd.DataFrame([{"Explosivo":k,"Temp.máx(°C)":v["temp_max"],"Hum.máx(%)":v["hum_max"],"Almacén":v["almacen"]} for k,v in EXPLOSIVOS_CFG.items()]), use_container_width=True, hide_index=True)

def mod_traslados():
    st.title("🚛 Flota y Traslados")
    viajes = get_viajes()
    t1,t2,t3 = st.tabs(["📋 Viajes","🚗 Vehículos","📊 Optimización"])
    with t1:
        c1,c2,c3 = st.columns(3)
        c1.metric("Total",len(viajes))
        c2.metric("En tiempo",  len(viajes[viajes["estado"]=="En tiempo"])  if not viajes.empty else 0)
        c3.metric("Con demora", len(viajes[viajes["estado"]=="Con demora"]) if not viajes.empty else 0,delta_color="inverse")
        fil = st.selectbox("Filtrar",["Todos","En tiempo","Con demora"])
        st.dataframe(viajes if fil=="Todos" else viajes[viajes["estado"]==fil], use_container_width=True, hide_index=True)
    with t2:
        vehs = get_df("SELECT * FROM vehiculos")
        st.dataframe(vehs, use_container_width=True, hide_index=True)
        if puede("todo"):
            with st.form("form_veh"):
                pat    = st.selectbox("Patente",vehs["patente"].tolist())
                nrt    = st.date_input("Nueva rev. técnica",value=date.today()+timedelta(days=365))
                sub_v  = st.form_submit_button("Actualizar")
            if sub_v:
                conn=get_conn(); conn.execute("UPDATE vehiculos SET rev_tecnica=?,estado='Operativo' WHERE patente=?",(str(nrt),pat)); conn.commit(); conn.close()
                st.success("✅ Revisión técnica actualizada."); st.rerun()
    with t3:
        if viajes.empty: st.info("Sin datos."); return
        rows=[]
        for rn,r in RUTAS.items():
            vr=viajes[viajes["ruta"]==rn]
            tp=vr["t_real"].mean() if not vr.empty else r["tiempo_min"]
            dp=vr["demora"].mean()  if not vr.empty else 0
            ok=len(vr[vr["estado"]=="En tiempo"])/len(vr)*100 if not vr.empty else 100
            rows.append({"Ruta":rn,"Dist.(km)":r["dist_km"],"T.esp.(min)":r["tiempo_min"],"T.prom.(min)":round(tp,1),"Demora(min)":round(dp,1),"% en tiempo":str(round(ok,0))+"%"})
        df_opt=pd.DataFrame(rows)
        st.dataframe(df_opt, use_container_width=True, hide_index=True)
        idx_min=df_opt["Demora(min)"].idxmin(); idx_max=df_opt["Demora(min)"].idxmax()
        st.success("✅ Ruta más eficiente: "+df_opt.loc[idx_min,"Ruta"])
        st.warning("⚠️ Ruta con mayor demora: "+df_opt.loc[idx_max,"Ruta"])

def mod_reportes():
    import openpyxl
    from openpyxl.styles import PatternFill,Font,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    st.title("📋 Reportes")
    st.info("Reportes listos para la Autoridad Fiscalizadora (DGMN/SERNAGEOMIN).")
    tipo   = st.selectbox("Tipo",["Reporte mensual completo","Discrepancias","Movimientos","Condiciones","Flota"])
    periodo= st.date_input("Período",value=date.today())
    if st.button("📥 Generar Excel",type="primary"):
        inv=get_inv(); inv["estado_calc"]=inv.apply(clasificar,axis=1)
        movs=get_movs(); viajes=get_viajes(); cond=get_cond(); alertas=generar_alertas()
        output=io.BytesIO(); wb=openpyxl.Workbook()
        HF=PatternFill("solid",fgColor="1F3864"); FF=Font(bold=True,color="FFFFFF",size=10)
        BD=Border(left=Side(style="thin"),right=Side(style="thin"),top=Side(style="thin"),bottom=Side(style="thin"))
        FILL={"CRITICA":PatternFill("solid",fgColor="FFCCCC"),"ALTA":PatternFill("solid",fgColor="FFEB9C"),"VIGENTE":PatternFill("solid",fgColor="C6EFCE"),"VENCIDO":PatternFill("solid",fgColor="FFCCCC")}
        def esc(ws,df,titulo):
            ws.append([titulo]); ws.cell(1,1).font=Font(bold=True,size=13,color="1F3864")
            ws.append(["Generado: "+datetime.now().strftime("%Y-%m-%d %H:%M")]); ws.append([]); ws.append(list(df.columns))
            for ci,_ in enumerate(df.columns,1):
                c=ws.cell(4,ci); c.fill=HF; c.font=FF; c.border=BD; c.alignment=Alignment(horizontal="center",wrap_text=True)
            for ri,row in enumerate(df.itertuples(index=False),5):
                for ci,val in enumerate(row,1):
                    c=ws.cell(ri,ci,value=str(val) if val is not None else ""); c.border=BD; c.alignment=Alignment(wrap_text=True,vertical="center")
                    vs=str(val).upper()
                    for k2,f in FILL.items():
                        if k2 in vs: c.fill=f; break
            for col in ws.columns:
                ml=max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width=min(ml+4,40)
        ws1=wb.active; ws1.title="Inventario"; esc(ws1,inv.drop(columns=["qr_data"],errors="ignore"),"INVENTARIO — "+str(periodo))
        if tipo in ["Reporte mensual completo","Movimientos"]: ws2=wb.create_sheet("Movimientos"); esc(ws2,movs,"MOVIMIENTOS — "+str(periodo))
        if tipo in ["Reporte mensual completo","Discrepancias"]:
            ws3=wb.create_sheet("Alertas"); df_a=pd.DataFrame(alertas) if alertas else pd.DataFrame(columns=["gravedad","lote","exp","msg","accion"]); esc(ws3,df_a,"ALERTAS — "+str(periodo))
        if tipo in ["Reporte mensual completo","Condiciones"]: ws4=wb.create_sheet("Condiciones"); esc(ws4,cond,"CONDICIONES — "+str(periodo))
        if tipo in ["Reporte mensual completo","Flota"]: ws5=wb.create_sheet("Flota"); esc(ws5,viajes,"FLOTA — "+str(periodo))
        wb.save(output); output.seek(0)
        st.download_button(label="📥 Descargar "+tipo,data=output,file_name="reporte_polvorin_"+str(periodo)+".xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.success("✅ Reporte generado.")

def mod_auditoria():
    st.title("🔍 Auditoría Física")
    st.info("Conteo físico mensual. El sistema compara con el registro digital y detecta discrepancias.")
    conn=get_conn()
    try: aud=pd.read_sql("SELECT * FROM auditorias ORDER BY fecha DESC",conn)
    except Exception: aud=pd.DataFrame()
    conn.close()
    t1,t2=st.tabs(["📋 Historial","➕ Nuevo conteo"])
    with t1:
        if aud.empty: st.info("Sin auditorías registradas.")
        else: st.dataframe(aud, use_container_width=True, hide_index=True)
    with t2:
        if not puede("todo"): st.info("Solo el administrador puede realizar auditorías."); return
        inv=get_inv()
        with st.form("form_aud"):
            conteos={}
            for exp in EXPLOSIVOS_CFG:
                stock=int(inv[inv["explosivo"]==exp]["cantidad"].sum()) if not inv.empty else 0
                conteos[exp]=st.number_input(exp+" (sistema: "+str(stock)+" "+EXPLOSIVOS_CFG[exp]["unidad"]+")",min_value=0,value=stock)
            obs_a=st.text_area("Observaciones",height=60)
            sub_a=st.form_submit_button("✅ Confirmar conteo",type="primary")
        if sub_a:
            conn=get_conn()
            for exp,cnt_r in conteos.items():
                stock=int(inv[inv["explosivo"]==exp]["cantidad"].sum()) if not inv.empty else 0
                diff=cnt_r-stock
                est="Aprobada" if diff==0 else ("Discrepancia leve" if abs(diff)<=2 else "Discrepancia crítica")
                conn.execute("INSERT INTO auditorias VALUES (?,?,?,?,?,?,?,?,?)",
                             (uuid.uuid4().hex[:8].upper(),str(date.today()),st.session_state["nombre"],exp,stock,cnt_r,diff,est,obs_a))
            conn.commit(); conn.close()
            st.success("✅ Auditoría registrada."); st.rerun()

def mod_admin():
    st.title("🏢 Administración del Sistema")
    if not puede("todo"): st.error("Acceso restringido al administrador."); return
    t1,t2,t3,t4=st.tabs(["👷 Usuarios","🏢 Proveedores","⚙️ Configuración","🔑 Credenciales"])
    with t1:
        users=get_df("SELECT id,nombre,usuario,rol,licencia_venc,activo FROM usuarios")
        st.dataframe(users, use_container_width=True, hide_index=True)
        st.subheader("Actualizar licencia")
        with st.form("form_lic"):
            uid=st.selectbox("Usuario",users["usuario"].tolist())
            nlic=st.date_input("Nueva fecha licencia",value=date.today()+timedelta(days=365))
            sub_l=st.form_submit_button("Actualizar")
        if sub_l:
            conn=get_conn(); conn.execute("UPDATE usuarios SET licencia_venc=? WHERE usuario=?",(str(nlic),uid)); conn.commit(); conn.close()
            st.success("✅ Licencia actualizada."); st.rerun()
        st.subheader("Crear usuario")
        with st.form("form_usr"):
            c1,c2=st.columns(2); n_nom=c1.text_input("Nombre"); n_usr=c2.text_input("Usuario")
            c3,c4=st.columns(2); n_pin=c3.text_input("PIN",type="password"); n_rol=c4.selectbox("Rol",["operario","jefe_turno","solo_lectura"])
            n_lic=st.date_input("Vencimiento licencia",value=date.today()+timedelta(days=365))
            sub_u=st.form_submit_button("Crear")
        if sub_u:
            conn=get_conn(); conn.execute("INSERT INTO usuarios VALUES (?,?,?,?,?,?,1)",("USR-"+uuid.uuid4().hex[:6].upper(),n_nom,n_usr,hash_pin(n_pin),n_rol,str(n_lic))); conn.commit(); conn.close()
            st.success("✅ Usuario creado."); st.rerun()
    with t2:
        provs=get_df("SELECT * FROM proveedores"); st.dataframe(provs, use_container_width=True, hide_index=True)
        with st.form("form_prov"):
            c1,c2=st.columns(2); p_nom=c1.text_input("Nombre"); p_rut=c2.text_input("RUT"); p_c=st.text_input("Contacto")
            sub_p=st.form_submit_button("Agregar")
        if sub_p:
            conn=get_conn(); conn.execute("INSERT INTO proveedores VALUES (?,?,?,?,1)",("PROV-"+uuid.uuid4().hex[:6].upper(),p_nom,p_rut,p_c)); conn.commit(); conn.close()
            st.success("✅ Proveedor agregado."); st.rerun()
    with t3:
        st.dataframe(pd.DataFrame([{"Explosivo":k,"Tipo":v["tipo"],"Unidad":v["unidad"],"Peso/ud(kg)":v["peso_kg"],"Stock mín":v["stock_min"],"Vida útil(d)":v["vida_dias"],"Almacén":v["almacen"],"Temp.máx(°C)":v["temp_max"],"Hum.máx(%)":v["hum_max"]} for k,v in EXPLOSIVOS_CFG.items()]), use_container_width=True, hide_index=True)
        st.subheader("Capacidades máximas (S = 1,5 · ∛W)")
        st.dataframe(pd.DataFrame([{"Almacén":k,"Kg máx":v["kg_max"],"Dist.seg.(m)":v["dist_m"],"Alerta 90%(kg)":round(v["kg_max"]*0.9,1)} for k,v in CAPACIDADES.items()]), use_container_width=True, hide_index=True)
    with t4:
        st.warning("⚠️ Solo visible para el administrador. Cambiar en producción.")
        st.dataframe(pd.DataFrame({"Rol":["Administrador","Jefe Turno","Operario","Inspector","Op.bloqueado"],"Usuario":["admin","jefe_turno","operario1","inspector","operario3"],"PIN":["1234","5678","9012","7890","1111"],"Nota":["Acceso total","Ops+reportes","Lic.vigente","Solo lectura","Lic.vencida"]}), hide_index=True, use_container_width=True)

def mod_manual():
    st.title("📖 Manual de Usuario")
    t1,t2,t3=st.tabs(["🚀 Guía rápida","📚 Tutoriales","📘 Glosario"])
    with t1:
        for titulo,pasos in [
            ("📥 Registrar ingreso",["1. Inventario → Ingreso","2. Seleccionar explosivo y cantidad","3. Elegir proveedor habilitado y N° guía","4. Confirmar fecha de vencimiento","5. El sistema verifica capacidad y registra"]),
            ("📤 Despachar explosivos",["1. Inventario → Despacho","2. Seleccionar tipo de explosivo","3. El sistema elige automáticamente el lote más antiguo (FIFO)","4. Ingresar destino, vehículo y N° orden","5. El sistema registra el viaje y actualiza el inventario"]),
            ("🚪 Registrar acceso al polvorín",["1. Accesos → Nuevo acceso","2. Seleccionar operador y tipo (Ingreso/Egreso)","3. El sistema verifica el límite de 5 personas","4. Confirmar y registrar"]),
            ("📋 Generar reporte para la AF",["1. Reportes → Seleccionar tipo y período","2. Clic en Generar Excel","3. Descargar y entregar a la Autoridad Fiscalizadora"]),
        ]:
            with st.expander(titulo):
                for p in pasos: st.markdown("- "+p)
    with t2:
        for titulo,desc in [
            ("🔐 Autenticación","Cada usuario accede con usuario y PIN. Los operarios deben tener licencia vigente. Si vence, el sistema bloquea el acceso hasta que el administrador la actualice."),
            ("⚖️ Capacidad máxima","El sistema calcula en tiempo real los kg en cada almacén. Al 90% emite alerta amarilla. Al 100% bloquea nuevos ingresos. Fórmula: S = 1,5 × ∛W (DS 132)."),
            ("📦 FIFO normativo","Al despachar, el sistema selecciona automáticamente el lote más antiguo. Evita que material vencido quede almacenado. No se puede saltar el orden."),
            ("🚨 Alertas automáticas","Se generan sin intervención del operario. Críticas (rojo) = acción inmediata. Altas (amarillo) = acción urgente. Medias (anaranjado) = seguimiento."),
            ("🔍 Auditoría física","Mensualmente el administrador realiza un conteo físico. El sistema compara con el registro digital y genera el informe de discrepancias automáticamente."),
        ]:
            with st.expander(titulo): st.markdown(desc)
    with t3:
        for term,defin in [
            ("ANFO","Mezcla de Nitrato de Amonio y Petróleo (94%/6%). Explosivo secundario de uso masivo en tronadura."),
            ("Emulsión","Explosivo industrial de alta potencia y resistencia al agua. Usado en condiciones adversas."),
            ("Fulminante N8","Detonador primario. Inicia la detonación de los explosivos secundarios."),
            ("FIFO","First In, First Out — Primero que entra, primero que sale. Rotación obligatoria de inventario."),
            ("Lote","Conjunto de explosivos del mismo tipo ingresado en una misma recepción, con código único."),
            ("Guía de despacho","Documento del proveedor que acompaña cada entrega. Debe coincidir con lo recibido."),
            ("AF / Autoridad Fiscalizadora","DGMN o SERNAGEOMIN según corresponda. Supervisa y autoriza el uso de explosivos."),
            ("Libro de control","Registro obligatorio de todos los movimientos. Debe presentarse mensualmente a la AF."),
            ("Manipulador de explosivos","Persona certificada por Sernageomin para operar con explosivos. Licencia obligatoria vigente."),
            ("DS 132","Decreto Supremo N°132 de Sernageomin. Reglamento de Seguridad Minera."),
        ]:
            with st.expander("📘 "+term): st.markdown(defin)

# ══════════════════════════════════════════════════════════════════════════════
# PARTE 2 — MÓDULOS DE GESTIÓN Y ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════════
def mod_kpis():
    st.title("📊 KPIs y Curva de Cumplimiento")
    st.info("Comparación entre línea base (sin sistema), valor actual, meta 6 meses y meta 12 meses.")
    kpis = get_kpis(); hist = get_khist()
    if kpis.empty: st.warning("Sin KPIs configurados."); return
    ultimo_mes = hist["periodo"].max() if not hist.empty else ""
    hist_ult   = hist[hist["periodo"]==ultimo_mes] if ultimo_mes else pd.DataFrame()
    logrados=0; parciales=0; no_logrados=0
    for _,k in kpis.iterrows():
        row_h = hist_ult[hist_ult["kpi_id"]==k["id"]] if not hist_ult.empty else pd.DataFrame()
        val   = row_h["valor_real"].iloc[0] if not row_h.empty else k["valor_base"]
        es_min= k["unidad"]=="min"
        if (es_min and val<=k["meta_6m"]) or (not es_min and val>=k["meta_6m"]): logrados+=1
        elif (es_min and val<k["valor_base"]) or (not es_min and val>k["valor_base"]): parciales+=1
        else: no_logrados+=1
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Total KPIs",len(kpis)); c2.metric("✅ Logrados",logrados)
    c3.metric("⚡ En progreso",parciales); c4.metric("❌ Sin mejora",no_logrados)
    st.divider()
    for area in kpis["area"].unique():
        st.subheader("📌 Área: "+area)
        for _,k in kpis[kpis["area"]==area].iterrows():
            hist_k   = hist[hist["kpi_id"]==k["id"]].copy()
            val_actual= hist_k["valor_real"].iloc[-1] if not hist_k.empty else k["valor_base"]
            es_min   = k["unidad"]=="min"
            logrado  = (val_actual<=k["meta_6m"] if es_min else val_actual>=k["meta_6m"])
            parcial  = (val_actual<k["valor_base"] if es_min else val_actual>k["valor_base"])
            cls_est  = "kpi-logrado" if logrado else ("kpi-parcial" if parcial else "kpi-no-logrado")
            txt_est  = ("✅ META ALCANZADA" if logrado else "⚡ EN PROGRESO" if parcial else "❌ SIN MEJORA")
            with st.expander(k["nombre"]+" — "+txt_est):
                st.caption(k["descripcion"])
                cm,cg=st.columns([1,2])
                with cm:
                    st.markdown('<div class="'+cls_est+'"><div style="font-size:1.6em;font-weight:bold;">'+str(round(val_actual,1))+" "+k["unidad"]+'</div><div style="font-size:0.85em;">Valor actual</div></div>', unsafe_allow_html=True)
                    st.markdown("")
                    cc1,cc2,cc3=st.columns(3)
                    cc1.metric("📍 Base",str(k["valor_base"])+" "+k["unidad"])
                    cc2.metric("🎯 6m",str(k["meta_6m"])+" "+k["unidad"])
                    cc3.metric("🏆 12m",str(k["meta_12m"])+" "+k["unidad"])
                with cg:
                    if not hist_k.empty:
                        chart_df=hist_k.set_index("periodo")[["valor_real"]].copy()
                        chart_df.columns=[k["nombre"]]; chart_df["Línea base"]=k["valor_base"]; chart_df["Meta 6m"]=k["meta_6m"]
                        st.line_chart(chart_df, use_container_width=True)
    st.divider()
    if puede("kpis") or puede("todo"):
        st.subheader("➕ Registrar medición real")
        with st.form("form_kpi"):
            c1,c2,c3=st.columns(3)
            kpi_sel=c1.selectbox("KPI",kpis["nombre"].tolist())
            val_r  =c2.number_input("Valor medido",min_value=0.0,value=0.0,step=0.1)
            periodo=c3.text_input("Período (AAAA-MM)",value=date.today().strftime("%Y-%m"))
            sub_k  =st.form_submit_button("✅ Registrar",type="primary")
        if sub_k:
            kid=kpis[kpis["nombre"]==kpi_sel]["id"].iloc[0]
            conn=get_conn(); conn.execute("INSERT OR REPLACE INTO kpi_historial VALUES (?,?,?,?,?,?)",("KHIST-"+kid+"-"+periodo+"-R",str(date.today()),kid,val_r,periodo,st.session_state["nombre"])); conn.commit(); conn.close()
            st.success("✅ Medición registrada."); st.rerun()

def mod_vista_rol():
    st.title("👁️ Vista por Rol")
    rol=st.session_state.get("rol","")
    inv=get_inv()
    if rol in ["administrador","jefe_turno"]:
        st.markdown("### Vista Jefe / Administrador")
        tab1,tab2,tab3,tab4=st.tabs(["📊 Resumen turno","📦 Inventario","🚛 Traslados","🔍 Auditorías"])
        with tab1:
            movs=get_movs(); viajes=get_viajes(); hoy=str(date.today())
            movs_h=movs[movs["fecha_hora"].str.startswith(hoy)] if not movs.empty else movs
            vj_h  =viajes[viajes["inicio"].str.startswith(hoy)] if not viajes.empty else viajes
            c1,c2,c3,c4=st.columns(4)
            c1.metric("Movimientos hoy",len(movs_h))
            c2.metric("Ingresos",len(movs_h[movs_h["tipo_mov"]=="Ingreso"]) if not movs_h.empty else 0)
            c3.metric("Despachos",len(movs_h[movs_h["tipo_mov"]=="Despacho"]) if not movs_h.empty else 0)
            c4.metric("Viajes hoy",len(vj_h))
            if not movs.empty:
                movs2=movs.copy(); movs2["fecha"]=movs2["fecha_hora"].str[:10]
                movs30=movs2[movs2["fecha"]>=str(date.today()-timedelta(days=30))]
                if not movs30.empty:
                    st.subheader("Movimientos por tipo (últimos 30 días)")
                    tabla_m=movs30.groupby(["fecha","tipo_mov"]).size().unstack(fill_value=0)
                    st.line_chart(tabla_m, use_container_width=True)
        with tab2:
            if not inv.empty:
                inv_c=inv.copy(); inv_c["estado_calc"]=inv_c.apply(clasificar,axis=1)
                st.dataframe(inv_c.drop(columns=["qr_data"],errors="ignore"), use_container_width=True, hide_index=True)
        with tab3:
            vj2=get_viajes()
            if vj2.empty: st.info("Sin viajes.")
            else:
                st.dataframe(vj2, use_container_width=True, hide_index=True)
                if "ruta" in vj2.columns and "t_real" in vj2.columns:
                    opt=vj2.groupby("ruta").agg(T_prom=("t_real","mean"),Demora=("demora","mean"),Total=("id_viaje","count")).round(1).reset_index()
                    st.dataframe(opt, use_container_width=True, hide_index=True)
        with tab4:
            conn=get_conn()
            try: aud=pd.read_sql("SELECT * FROM auditorias ORDER BY fecha DESC",conn)
            except Exception: aud=pd.DataFrame()
            conn.close()
            if aud.empty: st.info("Sin auditorías.")
            else:
                st.dataframe(aud, use_container_width=True, hide_index=True)
                if "diferencia" in aud.columns:
                    disc_g=aud.groupby("explosivo")["diferencia"].sum().reset_index(); disc_g.columns=["Explosivo","Diferencia total"]
                    st.bar_chart(disc_g.set_index("Explosivo"))
    else:
        st.markdown("### Vista Operario")
        movs=get_movs(); hoy=str(date.today()); nom=st.session_state.get("nombre","")
        mis_m=movs[(movs["fecha_hora"].str.startswith(hoy))&(movs["operador"]==nom)] if not movs.empty else movs
        acc=get_accesos(); mis_a=acc[(acc["fecha_hora"].str.startswith(hoy))&(acc["operador"]==nom)] if not acc.empty else acc
        c1,c2,c3=st.columns(3)
        c1.metric("Mis movimientos hoy",len(mis_m))
        c2.metric("Mis ingresos",len(mis_a[mis_a["tipo"]=="Ingreso"]) if not mis_a.empty else 0)
        c3.metric("Mis egresos",len(mis_a[mis_a["tipo"]=="Egreso"])   if not mis_a.empty else 0)
        st.subheader("Mis operaciones de hoy")
        if mis_m.empty: st.info("Sin operaciones hoy.")
        else: st.dataframe(mis_m, use_container_width=True, hide_index=True)
        st.subheader("📦 Stock disponible para despacho")
        if not inv.empty:
            inv_c=inv.copy(); inv_c["estado_calc"]=inv_c.apply(clasificar,axis=1)
            st.dataframe(inv_c[inv_c["estado_calc"]=="Vigente"][["id_lote","explosivo","cantidad","unidad","fecha_vencimiento","almacen"]], use_container_width=True, hide_index=True)

def mod_libro_control():
    import openpyxl
    from openpyxl.styles import PatternFill,Font,Alignment,Border,Side
    from openpyxl.utils import get_column_letter
    st.title("📋 Libro de Control — Exportación Oficial AF")
    st.info("Genera el libro de control mensual en formato para la Autoridad Fiscalizadora (DGMN/SERNAGEOMIN).")
    c1,c2=st.columns(2)
    mes_sel =c1.selectbox("Mes",["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"],index=date.today().month-1)
    anio_sel=c2.number_input("Año",min_value=2024,max_value=2030,value=date.today().year)
    if st.button("📥 Generar Libro Control Excel",type="primary"):
        movs=get_movs(); inv=get_inv(); acc=get_accesos()
        output=io.BytesIO(); wb=openpyxl.Workbook()
        HF=PatternFill("solid",fgColor="1F3864"); FF=Font(bold=True,color="FFFFFF",size=10)
        BD=Border(left=Side(style="thin"),right=Side(style="thin"),top=Side(style="thin"),bottom=Side(style="thin"))
        FILL={"INGRESO":PatternFill("solid",fgColor="C6EFCE"),"DESPACHO":PatternFill("solid",fgColor="BDD7EE"),"DEVOLUCION":PatternFill("solid",fgColor="FFF2CC"),"VENCIDO":PatternFill("solid",fgColor="FFCCCC")}
        def esc_af(ws,df,titulo,sub=""):
            ws.merge_cells("A1:K1"); ws["A1"]=titulo; ws["A1"].font=Font(bold=True,size=14,color="1F3864"); ws["A1"].alignment=Alignment(horizontal="center")
            ws.merge_cells("A2:K2"); ws["A2"]=sub or "Período: "+mes_sel+" "+str(anio_sel)+" | Generado: "+datetime.now().strftime("%Y-%m-%d %H:%M"); ws["A2"].font=Font(italic=True,size=10,color="595959"); ws["A2"].alignment=Alignment(horizontal="center")
            ws.merge_cells("A3:K3"); ws["A3"]="Normativa: DS N°132 SERNAGEOMIN · Ley N°17.798 · Resolución DGMN N°003048/2020"; ws["A3"].font=Font(italic=True,size=9,color="808080"); ws["A3"].alignment=Alignment(horizontal="center")
            ws.append([]); ws.append(list(df.columns))
            for ci,_ in enumerate(df.columns,1):
                c=ws.cell(5,ci); c.fill=HF; c.font=FF; c.border=BD; c.alignment=Alignment(horizontal="center",wrap_text=True)
            for ri,row in enumerate(df.itertuples(index=False),6):
                for ci,val in enumerate(row,1):
                    c=ws.cell(ri,ci,value=str(val) if val is not None else ""); c.border=BD; c.alignment=Alignment(wrap_text=True,vertical="center")
                    vs=str(val).upper()
                    for k2,f in FILL.items():
                        if k2 in vs: c.fill=f; break
            for col in ws.columns:
                ml=max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[get_column_letter(col[0].column)].width=min(ml+4,40)
            ws.row_dimensions[1].height=25; ws.row_dimensions[5].height=20
        ws1=wb.active; ws1.title="Libro de Movimientos"
        mov_c=["id_mov","id_lote","explosivo","tipo_mov","cantidad","fecha_hora","operador","destino","n_orden","turno","observaciones"]
        esc_af(ws1,movs[[c for c in mov_c if c in movs.columns]] if not movs.empty else movs,"LIBRO DE CONTROL DE EXPLOSIVOS — "+mes_sel.upper()+" "+str(anio_sel),"Faena hipotética · Consumidor Habitual · Ley N°17.798")
        ws2=wb.create_sheet("Inventario al Cierre"); esc_af(ws2,inv.drop(columns=["qr_data"],errors="ignore"),"INVENTARIO AL CIERRE DEL PERÍODO","Estado al "+str(date.today()))
        ws3=wb.create_sheet("Control de Accesos")
        acc_c=["id","operador","tipo","fecha_hora","motivo","turno"]
        esc_af(ws3,acc[[c for c in acc_c if c in acc.columns]] if not acc.empty else acc,"REGISTRO DE ACCESOS AL POLVORÍN","Control de personal — máx. 5 personas simultáneas (DS 132)")
        ws4=wb.create_sheet("Resumen Ejecutivo")
        def ce(kw): return len(inv[inv["estado"].str.upper().str.contains(kw,na=False)]) if not inv.empty and "estado" in inv.columns else 0
        for fi,fila in enumerate([
            ["RESUMEN EJECUTIVO — LIBRO DE CONTROL MENSUAL",""],["Período",mes_sel+" "+str(anio_sel)],
            ["Fecha",datetime.now().strftime("%Y-%m-%d %H:%M")],["Generado por",st.session_state.get("nombre","")],["",""],
            ["INVENTARIO",""],["Total lotes",len(inv)],["Peso total (kg)",round(inv["peso_kg_total"].sum() if not inv.empty else 0,2)],
            ["Vigentes",ce("VIGENTE")],["Vencidos",ce("VENCIDO")],["",""],
            ["MOVIMIENTOS",""],["Total",len(movs)],
            ["Ingresos",len(movs[movs["tipo_mov"]=="Ingreso"]) if not movs.empty else 0],
            ["Despachos",len(movs[movs["tipo_mov"]=="Despacho"]) if not movs.empty else 0],
            ["Devoluciones",len(movs[movs["tipo_mov"]=="Devolucion"]) if not movs.empty else 0],["",""],
            ["ACCESOS",""],["Total accesos",len(acc)],["",""],
            ["NORMATIVA",""],["DS N°132 SERNAGEOMIN","Reglamento de Seguridad Minera"],
            ["Ley N°17.798","Control de Armas y Explosivos"],["Resolución DGMN N°003048/2020","Almacenamiento productos Ley 17.798"],
        ],1):
            ws4.append(fila)
            if fi==1: ws4["A1"].font=Font(bold=True,size=14,color="1F3864")
        ws4.column_dimensions["A"].width=38; ws4.column_dimensions["B"].width=50
        ws4.append(["",""]); ws4.append(["",""]); ws4.append(["Firma: ___________________________",""])
        ws4.append(["Nombre: "+st.session_state.get("nombre",""),""]); ws4.append(["Cargo: Encargado de Polvorín",""]); ws4.append(["Fecha: "+str(date.today()),""])
        wb.save(output); output.seek(0)
        nombre_a="libro_control_"+mes_sel+"_"+str(anio_sel)+".xlsx"
        st.download_button(label="📥 Descargar Libro Control — "+mes_sel+" "+str(anio_sel),data=output,file_name=nombre_a,mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.success("✅ Libro de control generado · 4 hojas: Movimientos, Inventario, Accesos, Resumen.")

def mod_asistente_ia():
    st.title("🤖 Asistente IA — Apoyo Operativo")
    st.markdown('<div class="aviso-ia">⚠️ <b>Aviso:</b> Este asistente entrega solo orientación de apoyo. Toda decisión operativa, de seguridad o normativa debe ser tomada por el operador responsable certificado. No reemplaza el criterio del manipulador de explosivos ni la autoridad de la AF.</div>', unsafe_allow_html=True)
    if "chat_ia" not in st.session_state: st.session_state["chat_ia"]=[]
    SISTEMA="""Eres un asistente de apoyo para operadores de polvorines mineros en Chile.
Tu rol es orientar sobre operaciones, normativa y uso del sistema de gestión de polvorín.
Normativa: DS N°132 SERNAGEOMIN (2002), Ley N°17.798 (2007), Resolución DGMN N°003048 (2020).
Explosivos: ANFO (secundario, saco 25kg), Emulsión (secundario, caja 20kg), Mecha de seguridad (secundario, rollo 5kg), Fulminante N8 (primario, caja 0.5kg).
Capacidades: Container secundarios=3.500kg (dist.50m), Bóveda primarios=400kg (dist.25m). Fórmula: W=(S/1.5)³.
Máx. personas simultáneas: 5. FIFO obligatorio. Licencia manipulador vigente obligatoria.
Responde en español, claro y breve. Siempre recuerda que toda decisión la toma el operador responsable."""
    RESPUESTAS_BASE={
        ("vencido","vencida","destruir","destrucción"):"Según la Ley 17.798 (Cap. VIII), un lote vencido debe ser destruido por combustión, explosión o detonación controlada, autorizada por la AF. El manipulador debe dejar constancia en un acta.",
        ("personas","ingresar","simultáneas","cuántas"):"El límite es 5 personas simultáneas dentro del polvorín (DS 132). El sistema bloquea nuevos ingresos al alcanzar ese límite. Ninguna persona debe permanecer sola dentro.",
        ("fifo","primero","antiguo","rotación"):"FIFO significa que el lote más antiguo se despacha primero. El sistema lo aplica automáticamente. Evita que material vencido quede almacenado.",
        ("capacidad","máxima","peso","kg","almacen"):"Fórmula: W=(S/1,5)³. Container secundarios=3.500kg (S=50m), Bóveda primarios=400kg (S=25m). El sistema alerta al 90% y bloquea al 100%.",
        ("af","autoridad","fiscalizadora","notificar","dgmn"):"Notifique a la AF ante: lotes próximos a vencer (<30 días), destrucción de explosivos vencidos, discrepancias en inventario, y entrega del libro de control mensual.",
        ("devolución","devolver","sobra","no usado"):"Use Inventario → Devolución. Ingrese el lote, la cantidad y el motivo. Queda registrado en el libro de control como 'Devolucion'.",
        ("temperatura","calor","ventilación","ambiental"):"Si la temperatura supera el límite (35°C container, 30°C bóveda), active la ventilación y notifique al jefe de turno. Ref: DS 132.",
        ("juntos","separados","primarios","secundarios","incompatibilidad"):"Los fulminantes NUNCA deben estar junto a ANFO, emulsión o mecha. Deben estar en recintos separados: bóveda para primarios, container para secundarios. Ref: DS 132 y Ley 17.798.",
    }
    def get_respuesta_base(preg):
        pl=preg.lower()
        for claves,resp in RESPUESTAS_BASE.items():
            if any(c in pl for c in claves):
                return resp+"\n\n*⚠️ Respuesta de referencia. Consulte al jefe de turno para decisiones operativas.*"
        return "No tengo información específica sobre esa consulta. Consulte el Manual o al jefe de turno.\n\n*⚠️ Toda decisión debe tomarla el operador responsable.*"
    def llamar_api(pregunta):
        try:
            import urllib.request
            mensajes=[]
            for msg in st.session_state["chat_ia"][-6:]:
                mensajes.append({"role":"user" if msg["rol"]=="usuario" else "assistant","content":msg["texto"]})
            mensajes.append({"role":"user","content":pregunta})
            payload=json.dumps({"model":"claude-sonnet-4-6","max_tokens":600,"system":SISTEMA,"messages":mensajes}).encode("utf-8")
            req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=payload,headers={"Content-Type":"application/json","anthropic-version":"2023-06-01"},method="POST")
            with urllib.request.urlopen(req,timeout=15) as resp:
                data=json.loads(resp.read().decode("utf-8"))
                texto=data.get("content",[{}])[0].get("text","Sin respuesta.")
                return texto+"\n\n*⚠️ Solo orientación. Toda decisión debe tomarla el operador responsable.*"
        except Exception:
            return get_respuesta_base(pregunta)
    col1,col2=st.columns([2.5,1])
    with col2:
        st.markdown("**💡 Preguntas frecuentes:**")
        for pq in ["¿Qué hago con un lote vencido?","¿Cuántas personas pueden ingresar?","¿Cómo funciona el FIFO?","¿Qué es la capacidad máxima?","¿Cuándo notificar a la AF?","¿Cómo registrar una devolución?","¿Qué explosivos no pueden ir juntos?"]:
            if st.button(pq,use_container_width=True,key="pq_"+pq[:15]):
                st.session_state["chat_ia"].append({"rol":"usuario","texto":pq})
                with st.spinner("Consultando..."): resp=llamar_api(pq)
                st.session_state["chat_ia"].append({"rol":"asistente","texto":resp}); st.rerun()
        st.divider()
        if st.button("🗑️ Limpiar conversación",use_container_width=True): st.session_state["chat_ia"]=[]; st.rerun()
    with col1:
        if not st.session_state["chat_ia"]:
            st.markdown('<div class="chat-asistente">👋 Hola. Soy el asistente de apoyo del sistema de polvorín. ¿En qué te puedo ayudar?</div>', unsafe_allow_html=True)
        for msg in st.session_state["chat_ia"]:
            if msg["rol"]=="usuario": st.markdown('<div class="chat-usuario">👷 <b>Tú:</b> '+msg["texto"]+'</div>', unsafe_allow_html=True)
            else: st.markdown('<div class="chat-asistente">🤖 <b>Asistente:</b> '+msg["texto"]+'</div>', unsafe_allow_html=True)
        st.markdown("")
        with st.form("form_ia",clear_on_submit=True):
            preg=st.text_area("Tu pregunta:",height=80,placeholder="Ej: ¿Qué debo hacer si la temperatura supera los 35°C?")
            sub_ia=st.form_submit_button("Enviar →",type="primary",use_container_width=True)
        if sub_ia and preg.strip():
            st.session_state["chat_ia"].append({"rol":"usuario","texto":preg.strip()})
            with st.spinner("Consultando..."): resp=llamar_api(preg.strip())
            st.session_state["chat_ia"].append({"rol":"asistente","texto":resp}); st.rerun()

def mod_acerca():
    st.title("ℹ️ Acerca del Sistema")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("""
### Sistema de Gestión de Polvorín Minero — v2.0
**Autor:** Cristóbal Rubio
**Institución:** Universidad Andrés Bello
**Carrera:** Ingeniería en Minería Subterránea
**Profesor guía:** Manuel Reyes · **Año:** 2026

---
### Normativa base
- DS N°132 SERNAGEOMIN (2002)
- Ley N°17.798 (2007) — Control de Armas
- Resolución DGMN N°003048 (2020)
- Ley N°17.798 Cap. VIII — Destrucción explosivos

---
### Estado actual
- **Versión:** Prototipo funcional
- **Datos:** Simulados (caso hipotético)
- **GPS:** Hipotético — arquitectura lista para GPS real
- **Sensores:** Simulados — lista para IoT real
- **Asistente IA:** API Claude (requiere internet, fallback offline)
""")
    with c2:
        st.markdown("""
### Módulos — Parte 1 (Operativo)
🔐 Autenticación con PIN y licencia · 🏠 Estado general con semáforo · 📥 Inventario con FIFO
🚨 Alertas automáticas · 🚪 Control de acceso · 🌡️ Condiciones ambientales
🚛 Flota y traslados · 📋 Reportes Excel · 🔍 Auditoría física · 🏢 Administración · 📖 Manual

### Módulos — Parte 2 (Gestión y Análisis)
📊 KPIs con curva de cumplimiento mensual · 👁️ Vista diferenciada por rol
📋 Libro de control formato AF · 🤖 Asistente IA con API Claude

---
### Trabajo futuro
- Conexión a sensores IoT reales
- GPS en vehículos de traslado
- Autenticación biométrica
- Sincronización en red local de faena
- Encriptación de base de datos
- App móvil para tablet en terreno
""")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
init_db()

if not st.session_state.get("autenticado"):
    pantalla_login()
else:
    modulo = sidebar()
    # Parte 1
    if   "Estado General" in modulo: mod_dashboard()
    elif "Inventario"     in modulo: mod_inventario()
    elif "Alertas"        in modulo: mod_alertas()
    elif "Accesos"        in modulo: mod_accesos()
    elif "Condiciones"    in modulo: mod_condiciones()
    elif "Traslados"      in modulo: mod_traslados()
    elif "Reportes"       in modulo: mod_reportes()
    elif "Auditoría"      in modulo: mod_auditoria()
    elif "Administración" in modulo: mod_admin()
    elif "Manual"         in modulo: mod_manual()
    # Parte 2
    elif "KPIs"           in modulo: mod_kpis()
    elif "Vista por Rol"  in modulo: mod_vista_rol()
    elif "Libro Control"  in modulo: mod_libro_control()
    elif "Asistente IA"   in modulo: mod_asistente_ia()
    elif "Acerca"         in modulo: mod_acerca()
