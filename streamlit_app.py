import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date, time, timedelta
import pandas as pd
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Clínica Carmen Fontes", page_icon="🦷", layout="wide")
TZ_VALENCIA = pytz.timezone('Europe/Madrid')

# Intentar cargar logo
try:
    st.image("logoccf.png", width=250)
except:
    st.markdown("<h2 style='color:#D4A5A5;'>🦷 Clínica Carmen Fontes</h2>", unsafe_allow_html=True)

# --- FESTIVOS Y MOTIVOS ---
FESTIVOS = [
    date(2024, 1, 1), date(2024, 1, 6), date(2024, 3, 19), date(2024, 3, 29),
    date(2024, 4, 1), date(2024, 5, 1), date(2024, 6, 24), date(2024, 8, 15),
    date(2024, 10, 9), date(2024, 11, 1), date(2024, 12, 6), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 1, 6), date(2025, 3, 19), date(2025, 4, 18),
    date(2025, 4, 21), date(2025, 5, 1), date(2025, 6, 24), date(2025, 8, 15),
    date(2025, 10, 9), date(2025, 11, 1), date(2025, 12, 6), date(2025, 12, 8), date(2025, 12, 25)
]

TIPOS_REGISTRO = {
    "trabajo": "✅ Jornada Realizada",
    "olvido": "🤦 Registro Olvidado (Corrección)",
    "vacaciones_nopl": "🏖️ Vacaciones (Solicitud)",
    "asuntos_propios": "🏠 Asuntos Propios (Solicitud)"
}

# --- CONEXIÓN SUPABASE ---
try:
    supabase: Client = create_client(st.secrets["SUPABASE"]["url"], st.secrets["SUPABASE"]["key"])
except:
    st.error("⚠️ Error de conexión a Base de Datos.")
    st.stop()

# --- FUNCIONES AUXILIARES ---

def es_laborable(fecha: date):
    if fecha.weekday() >= 5: return False # Finde
    if fecha in FESTIVOS: return False
    return True

def enviar_alerta_email(nombre_emp, fecha_str, motivo, entrada, salida, es_futuro=False, es_rango=False):
    """
    Envía email. fecha_str puede ser una fecha simple o un texto de rango "X al Y".
    """
    try:
        smtp_server = st.secrets["EMAIL"]["smtp_server"]
        port = st.secrets["EMAIL"]["smtp_port"]
        sender = st.secrets["EMAIL"]["sender_email"]
        password = st.secrets["EMAIL"]["sender_password"]
        receiver = st.secrets["EMAIL"]["admin_email"]

        if es_rango:
            asunto = f"✈️ Solicitud de Vacaciones (Periodo): {nombre_emp}"
            texto_fecha = f"Periodo solicitado: {fecha_str}"
        elif es_futuro:
            asunto = f"✈️ Solicitud Futura: {nombre_emp}"
            texto_fecha = f"Fecha: {fecha_str}"
        else:
            asunto = f"🔔 Corrección Horaria: {nombre_emp}"
            texto_fecha = f"Fecha: {fecha_str}"
        
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = asunto

        body = f"""
        Hola Alberto,
        
        {nombre_emp} ha enviado una nueva solicitud:
        
        - Tipo: {'PLANIFICACIÓN (VACACIONES/AUSENCIA)' if es_futuro or es_rango else 'CORRECCIÓN PASADA'}
        - {texto_fecha}
        - Motivo: {TIPOS_REGISTRO.get(motivo, motivo)}
        - Horario: {entrada} a {salida}
        
        Entra en la App para revisar y aprobar los días correspondientes.
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error email: {e}")
        return False

def generar_calendario_html(year, month, dias_fichados, dias_faltantes):
    """Genera una tabla HTML simple representando el calendario"""
    cal = calendar.Calendar()
    hoy = datetime.now(TZ_VALENCIA).date()
    
    html = f"""
    <style>
        .calendar-table {{ width: 100%; border-collapse: collapse; }}
        .calendar-table th {{ background-color: #D4A5A5; color: white; padding: 10px; }}
        .calendar-table td {{ height: 80px; width: 14%; vertical-align: top; border: 1px solid #ddd; padding: 5px; }}
        .day-num {{ font-weight: bold; margin-bottom: 5px; }}
        .status-ok {{ background-color: #C8E6C9; color: #2E7D32; padding: 2px 5px; border-radius: 4px; font-size: 0.8em; }}
        .status-plan {{ background-color: #BBDEFB; color: #1565C0; padding: 2px 5px; border-radius: 4px; font-size: 0.8em; }}
        .status-missing {{ background-color: #FFCDD2; color: #C62828; padding: 2px 5px; border-radius: 4px; font-size: 0.8em; cursor: pointer; border: 1px solid #E57373; }}
        .status-weekend {{ background-color: #F5F5F5; color: #999; }}
    </style>
    <table class="calendar-table">
        <thead><tr><th>L</th><th>M</th><th>X</th><th>J</th><th>V</th><th>S</th><th>D</th></tr></thead>
        <tbody>
    """
    for week in cal.monthdatescalendar(year, month):
        html += "<tr>"
        for day in week:
            if day.month != month:
                html += "<td style='background-color: #FAFAFA;'></td>"
                continue
            
            day_content = f"<div class='day-num'>{day.day}</div>"
            
            if not es_laborable(day):
                html += f"<td class='status-weekend'>{day_content}</td>"
            elif day in dias_fichados:
                # Si es futuro y está fichado, es "Planificado"
                if day > hoy:
                     html += f"<td>{day_content}<div class='status-plan'>🗓️ Planificado</div></td>"
                else:
                     html += f"<td>{day_content}<div class='status-ok'>✅ Registrado</div></td>"
            elif day in dias_faltantes:
                # Solo marcamos falta si está en la lista de faltantes
                html += f"<td style='background-color: #FFEBEE;'>{day_content}<div class='status-missing'>⚠️ FALTA</div></td>"
            else:
                # Futuro o laborable sin pasar
                html += f"<td>{day_content}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# --- LOGIN ---
usuarios = supabase.table('empleados').select("*").eq('activo', True).order('nombre').execute()
if not usuarios.data: st.stop()
mapa_usuarios = {u['nombre']: u for u in usuarios.data}

if 'usuario' not in st.session_state:
    st.markdown("### 👋 Acceso Registro Horario")
    col1, col2 = st.columns(2)
    nombre = col1.selectbox("Nombre", [""] + list(mapa_usuarios.keys()))
    pin = col2.text_input("PIN", type="password")
    if st.button("Entrar", type="primary") and nombre and pin:
        if mapa_usuarios[nombre]['pin_secreto'] == pin:
            st.session_state['usuario'] = mapa_usuarios[nombre]
            st.rerun()
        else: st.error("PIN Incorrecto")

else:
    user = st.session_state['usuario']
    
    # ==============================================================================
    # ⚙️ PERFIL ADMIN
    # ==============================================================================
    if user['nombre'] == 'Administrador':
        st.info("⚙️ Modo Administradora")
        tab1, tab2, tab3 = st.tabs(["👥 Equipo", "📩 Aprobaciones", "📊 Informes"])
        
        with tab1: # Altas
            with st.form("new_emp"):
                c1,c2 = st.columns(2)
                n = c1.text_input("Nombre")
                p = c2.text_input("PIN")
                if st.form_submit_button("Crear"):
                    supabase.table('empleados').insert({"nombre": n, "pin_secreto": p}).execute()
                    st.success("Creado")
        
        with tab2: # Aprobaciones
            pendientes = supabase.table('fichajes').select("*, empleados(nombre)").eq('estado', 'pendiente').order('fecha', desc=True).execute()
            if not pendientes.data: st.success("✅ Todo al día.")
            for p in pendientes.data:
                with st.container():
                    es_futuro = p['fecha'] > datetime.now(TZ_VALENCIA).strftime('%Y-%m-%d')
                    icono = "✈️" if es_futuro else "⚠️"
                    titulo = "Solicitud Futura" if es_futuro else "Corrección / Olvido"
                    
                    st.markdown(f"""<div style='background-color:#FFF3E0;padding:10px;border-radius:5px;margin-bottom:5px; border-left: 5px solid #FF9800;'>
                    <strong>{icono} {titulo}</strong><br>
                    <strong>{p['fecha']}</strong> | {p['empleados']['nombre']} | <em>{p['tipo_registro']}</em> <br>
                    <small>Nota: {p['notas_admin'] or ''}</small>
                    </div>""", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([1,4])
                    if c1.button("✅ Aprobar", key=f"ok_{p['id']}"):
                        supabase.table('fichajes').update({"estado": "aprobado"}).eq('id', p['id']).execute()
                        st.rerun()
                    if c1.button("❌ Rechazar", key=f"no_{p['id']}"):
                        supabase.table('fichajes').update({"estado": "rechazado"}).eq('id', p['id']).execute()
                        st.rerun()
        
        with tab3: # Excel
            if st.button("Descargar Excel Mensual"):
                df = pd.DataFrame(supabase.table('fichajes').select("*, empleados(nombre)").execute().data)
                if not df.empty:
                    st.dataframe(df)
                else:
                    st.warning("No hay datos")

        if st.button("Salir"): del st.session_state['usuario']; st.rerun()

    # ==============================================================================
    # 🦷 PERFIL EMPLEADA (Visual y Simplificado)
    # ==============================================================================
    else:
        st.markdown(f"### Hola, {user['nombre']} 👋")
        
        hoy = datetime.now(TZ_VALENCIA).date()
        mes_actual = hoy.month
        year_actual = hoy.year
        
        _, num_dias = calendar.monthrange(year_actual, mes_actual)
        inicio_mes = date(year_actual, mes_actual, 1)
        fin_mes = date(year_actual, mes_actual, num_dias)
        
        registros_db = supabase.table('fichajes').select("fecha, estado").eq('empleado_id', user['id']).gte('fecha', inicio_mes).lte('fecha', fin_mes).execute()
        fechas_fichadas = {datetime.strptime(r['fecha'], '%Y-%m-%d').date() for r in registros_db.data}
        
        dias_faltantes = []
        for d in range(1, hoy.day):
            fecha_iter = date(year_actual, mes_actual, d)
            if es_laborable(fecha_iter) and fecha_iter not in fechas_fichadas:
                dias_faltantes.append(fecha_iter)
        
        st.markdown(generar_calendario_html(year_actual, mes_actual, fechas_fichadas, dias_faltantes), unsafe_allow_html=True)
        st.write("") 
        
        # ---------------------------------------------------------
        # A: REGISTRAR HOY O CORREGIR PASADO (Día único)
        # ---------------------------------------------------------
        st.markdown("### 📝 Registrar Jornada / Corregir Pasado")
        
        with st.container():
            opciones_fecha = [hoy] + dias_faltantes
            opciones_fecha.sort(reverse=True)
            
            def formatear_fecha(d):
                if d == hoy: return f"📅 HOY ({d.strftime('%d/%m')})"
                return f"🔴 REGULARIZAR: {d.strftime('%d/%m/%Y')}"

            c_fecha, c_motivo = st.columns([2, 1])
            fecha_selec = c_fecha.selectbox("Selecciona día:", opciones_fecha, format_func=formatear_fecha)
            
            col1, col2, col3 = st.columns(3)
            h_entrada = col1.time_input("Entrada", value=time(10, 0))
            h_salida = col2.time_input("Salida", value=time(20, 0))
            h_comida = col3.number_input("Horas Comida", value=1.0, step=0.5)
            
            motivo = "trabajo"
            if fecha_selec != hoy:
                st.warning(f"Estás corrigiendo un día pasado. Requiere aprobación.")
                motivo = c_motivo.selectbox("Motivo:", ["olvido", "asuntos_propios"], format_func=lambda x: TIPOS_REGISTRO.get(x, x))

            if st.button("💾 Guardar Registro", use_container_width=True, type="primary"):
                existe = supabase.table('fichajes').select("*").eq('empleado_id', user['id']).eq('fecha', str(fecha_selec)).execute()
                if existe.data:
                    st.error("Ya existe registro para este día.")
                else:
                    es_diferido = (fecha_selec != hoy)
                    estado = "pendiente" if es_diferido else "aprobado"
                    data = {"empleado_id": user['id'], "fecha": str(fecha_selec), "hora_entrada": str(h_entrada), "hora_salida": str(h_salida), "horas_descanso": h_comida, "tipo_registro": motivo, "estado": estado}
                    supabase.table('fichajes').insert(data).execute()
                    if es_diferido: enviar_alerta_email(user['nombre'], str(fecha_selec), motivo, h_entrada, h_salida, es_futuro=False)
                    st.success("Guardado.")
                    st.rerun()

        # ---------------------------------------------------------
        # B: PLANIFICAR FUTURO (RANGOS Y PERIODOS)
        # ---------------------------------------------------------
        st.write("")
        with st.expander("✈️ Planificar Vacaciones o Periodos Largos"):
            st.info("Selecciona el día de inicio y el día de fin. Se crearán solicitudes para todos los días laborables intermedios.")
            
            with st.form("futuro_form_rango"):
                col_f1, col_f2 = st.columns(2)
                # Date input con rango
                rango_fechas = col_f1.date_input("Selecciona Periodo (Inicio - Fin)", value=[], min_value=hoy + timedelta(days=1))
                motivo_futuro = col_f2.selectbox("Tipo:", ["vacaciones_nopl", "asuntos_propios"], format_func=lambda x: TIPOS_REGISTRO.get(x, x))
                nota = st.text_input("Nota (Opcional)", placeholder="Ej: Viaje familiar")
                
                if st.form_submit_button("📅 Solicitar Periodo"):
                    if len(rango_fechas) != 2:
                        st.warning("Por favor, selecciona una fecha de INICIO y una fecha de FIN en el calendario.")
                    else:
                        inicio, fin = rango_fechas
                        delta = fin - inicio
                        dias_creados = 0
                        
                        # Iterar por todos los días del rango
                        for i in range(delta.days + 1):
                            dia_actual = inicio + timedelta(days=i)
                            
                            # Si es laborable
                            if es_laborable(dia_actual):
                                # Verificar que no exista ya
                                existe = supabase.table('fichajes').select("id").eq('empleado_id', user['id']).eq('fecha', str(dia_actual)).execute()
                                if not existe.data:
                                    data = {
                                        "empleado_id": user['id'], 
                                        "fecha": str(dia_actual), 
                                        "tipo_registro": motivo_futuro, 
                                        "estado": "pendiente",
                                        "notas_admin": f"Periodo: {inicio.strftime('%d/%m')} - {fin.strftime('%d/%m')}. {nota}",
                                        "hora_entrada": "00:00", "hora_salida": "00:00", "horas_descanso": 0
                                    }
                                    supabase.table('fichajes').insert(data).execute()
                                    dias_creados += 1
                        
                        if dias_creados > 0:
                            # Enviar UN solo email resumen
                            periodo_str = f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
                            enviar_alerta_email(user['nombre'], periodo_str, motivo_futuro, "00:00", "00:00", es_futuro=True, es_rango=True)
                            st.success(f"Solicitud enviada para {dias_creados} días laborables. Se ha notificado a administración.")
                            st.rerun()
                        else:
                            st.warning("No se ha creado ningún registro (quizás eran todo festivos o ya estaban registrados).")

        st.divider()
        if st.button("Cerrar Sesión"):
            del st.session_state['usuario']
            st.rerun()
