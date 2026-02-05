import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date, time, timedelta
import pandas as pd
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import calendar
import io  # Necesario para crear el archivo Excel

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Clínica Carmen Fontes", page_icon="🦷", layout="wide")
TZ_VALENCIA = pytz.timezone('Europe/Madrid')

# --- LOGO CENTRADO Y GRANDE ---
# Usamos columnas para centrarlo visualmente
c_logo1, c_logo2, c_logo3 = st.columns([1, 2, 1])
with c_logo2:
    try:
        # width=500 hace que se vea mucho más grande
        st.image("logoccf.png", width=500)
    except:
        st.markdown("<h1 style='text-align: center; color:#D4A5A5;'>🦷 Clínica Carmen Fontes</h1>", unsafe_allow_html=True)

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
    "asuntos_propios": "🏠 Asuntos Propios (Solicitud)",
    "no_trabajado": "⛔ No Trabajado / Clínica Cerrada"
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
                if day > hoy:
                     html += f"<td>{day_content}<div class='status-plan'>🗓️ Planificado</div></td>"
                else:
                     html += f"<td>{day_content}<div class='status-ok'>✅ Registrado</div></td>"
            elif day in dias_faltantes:
                html += f"<td style='background-color: #FFEBEE;'>{day_content}<div class='status-missing'>⚠️ FALTA</div></td>"
            else:
                html += f"<td>{day_content}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html

# --- LOGIN ---
usuarios = supabase.table('empleados').select("*").eq('activo', True).order('nombre').execute()
if not usuarios.data: st.stop()
mapa_usuarios = {u['nombre']: u for u in usuarios.data}

if 'usuario' not in st.session_state:
    st.markdown("<h3 style='text-align:center;'>👋 Acceso Registro Horario</h3>", unsafe_allow_html=True)
    
    # Columnas centradas para el login
    c_log1, c_log2, c_log3 = st.columns([1, 2, 1])
    
    with c_log2:
        # El selectbox de streamlit YA es un autocompletar. Si escriben "L", salen las Lorenas.
        # Ordenamos la lista para que sea más fácil buscar visualmente también.
        lista_nombres_ordenada = sorted(list(mapa_usuarios.keys()))
        nombre = st.selectbox("Selecciona o escribe tu nombre:", [""] + lista_nombres_ordenada)
        pin = st.text_input("PIN de acceso:", type="password")
        
        if st.button("Entrar 🔓", type="primary", use_container_width=True):
            if nombre and pin:
                if mapa_usuarios[nombre]['pin_secreto'] == pin:
                    st.session_state['usuario'] = mapa_usuarios[nombre]
                    st.rerun()
                else:
                    st.error("🚫 PIN Incorrecto")
            else:
                st.warning("Selecciona usuario e introduce PIN")

else:
    user = st.session_state['usuario']
    
    # ==============================================================================
    # ⚙️ PERFIL ADMIN
    # ==============================================================================
    if user['nombre'] == 'Administrador':
        st.info("⚙️ Modo Administradora")
        tab1, tab2, tab3 = st.tabs(["👥 Equipo", "📩 Aprobaciones", "📊 Informes y Auditoría"])
        
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
        
        with tab3: # Excel Auditoría
            st.subheader("🗓️ Exportación por Rango de Fechas")
            
            # Selectores de fecha para auditoría
            col_d1, col_d2 = st.columns(2)
            fecha_inicio = col_d1.date_input("Fecha Inicio", value=date.today().replace(day=1))
            fecha_fin = col_d2.date_input("Fecha Fin", value=date.today())
            
            if st.button("🔍 Buscar y Generar Excel"):
                # Consulta filtrada por rango
                response = supabase.table('fichajes').select("*, empleados(nombre)")\
                    .gte('fecha', str(fecha_inicio))\
                    .lte('fecha', str(fecha_fin))\
                    .order('fecha', desc=True)\
                    .execute()
                
                df = pd.DataFrame(response.data)
                
                if not df.empty:
                    df['nombre_empleado'] = df['empleados'].apply(lambda x: x['nombre'] if x else 'Desconocido')
                    df = df.drop(columns=['empleados'])
                    columnas_ordenadas = ['fecha', 'nombre_empleado', 'hora_entrada', 'hora_salida', 'horas_descanso', 'tipo_registro', 'estado', 'notas_admin']
                    cols_finales = [c for c in columnas_ordenadas if c in df.columns]
                    df_final = df[cols_finales]

                    st.success(f"Se han encontrado {len(df)} registros.")
                    st.dataframe(df_final.head()) 

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_final.to_excel(writer, index=False, sheet_name='Informe')
                    
                    st.download_button(
                        label=f"📥 Descargar Excel ({fecha_inicio} a {fecha_fin})",
                        data=buffer.getvalue(),
                        file_name=f"Informe_Fichajes_{fecha_inicio}_{fecha_fin}.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.warning("No se encontraron registros en ese rango de fechas.")

        if st.button("Salir"): del st.session_state['usuario']; st.rerun()

    # ==============================================================================
    # 🦷 PERFIL EMPLEADA (Visual y Simplificado)
    # ==============================================================================
    else:
        st.markdown(f"### Hola, {user['nombre']} 👋")
        
        hoy = datetime.now(TZ_VALENCIA).date()
        
        # --- NUEVO: SELECTOR DE MES PARA VER EL PASADO ---
        c_nav1, c_nav2 = st.columns([1, 3])
        fecha_visualizar = c_nav1.date_input("📅 Cambiar Mes a Visualizar:", value=hoy)
        
        mes_target = fecha_visualizar.month
        year_target = fecha_visualizar.year
        
        _, num_dias = calendar.monthrange(year_target, mes_target)
        inicio_mes = date(year_target, mes_target, 1)
        fin_mes = date(year_target, mes_target, num_dias)
        
        # Consultamos el mes SELECCIONADO (puede ser pasado)
        registros_db = supabase.table('fichajes').select("fecha, estado").eq('empleado_id', user['id']).gte('fecha', inicio_mes).lte('fecha', fin_mes).execute()
        fechas_fichadas = {datetime.strptime(r['fecha'], '%Y-%m-%d').date() for r in registros_db.data}
        
        # Calculamos faltas del mes seleccionado
        dias_faltantes = []
        
        # Si estamos viendo el mes actual, calculamos faltas hasta ayer
        # Si estamos viendo un mes pasado, calculamos faltas hasta el final de ese mes
        if mes_target == hoy.month and year_target == hoy.year:
            dia_limite = hoy.day # Hasta ayer
        elif date(year_target, mes_target, 1) > hoy:
             dia_limite = 1 # Futuro, no hay faltas
        else:
             dia_limite = num_dias + 1 # Mes pasado completo
        
        for d in range(1, dia_limite):
            fecha_iter = date(year_target, mes_target, d)
            if es_laborable(fecha_iter) and fecha_iter not in fechas_fichadas:
                dias_faltantes.append(fecha_iter)
        
        st.markdown(generar_calendario_html(year_target, mes_target, fechas_fichadas, dias_faltantes), unsafe_allow_html=True)
        st.write("") 
        
        # ---------------------------------------------------------
        # A: REGISTRAR HOY O CORREGIR PASADO
        # ---------------------------------------------------------
        st.markdown("### 📝 Registrar Jornada / Corregir Pasado")
        
        with st.container():
            # Las opciones de corrección ahora dependen del mes que estemos visualizando + hoy
            opciones_fecha = [hoy] + dias_faltantes
            # Eliminamos duplicados si hoy está en faltas por error y ordenamos
            opciones_fecha = sorted(list(set(opciones_fecha)), reverse=True)
            
            def formatear_fecha(d):
                if d == hoy: return f"📅 HOY ({d.strftime('%d/%m')})"
                return f"🔴 REGULARIZAR: {d.strftime('%d/%m/%Y')}"

            c_fecha, c_motivo = st.columns([2, 1])
            fecha_selec = c_fecha.selectbox("Selecciona día a registrar:", opciones_fecha, format_func=formatear_fecha)
            
            col1, col2, col3 = st.columns(3)
            h_entrada = col1.time_input("Entrada", value=time(10, 0))
            h_salida = col2.time_input("Salida", value=time(20, 0))
            h_comida = col3.number_input("Horas Comida", value=1.0, step=0.5)
            
            # --- CASO 1: CORREGIR DÍA PASADO ---
            if fecha_selec != hoy:
                st.warning(f"Estás corrigiendo un día pasado ({fecha_selec}). Requiere aprobación.")
                motivo = c_motivo.selectbox("Motivo:", ["olvido", "asuntos_propios", "no_trabajado"], format_func=lambda x: TIPOS_REGISTRO.get(x, x))
                
                if st.button("💾 Enviar Solicitud", use_container_width=True, type="primary"):
                    existe = supabase.table('fichajes').select("*").eq('empleado_id', user['id']).eq('fecha', str(fecha_selec)).execute()
                    if existe.data:
                        st.error("Ya existe registro para este día.")
                    else:
                        if motivo == "no_trabajado":
                             h_in_db, h_out_db, h_desc_db = "00:00", "00:00", 0
                        else:
                             h_in_db, h_out_db, h_desc_db = str(h_entrada), str(h_salida), h_comida

                        data = {
                            "empleado_id": user['id'], "fecha": str(fecha_selec), 
                            "hora_entrada": h_in_db, "hora_salida": h_out_db, 
                            "horas_descanso": h_desc_db, "tipo_registro": motivo, "estado": "pendiente"
                        }
                        supabase.table('fichajes').insert(data).execute()
                        enviar_alerta_email(user['nombre'], str(fecha_selec), motivo, h_in_db, h_out_db, es_futuro=False)
                        st.success("Guardado.")
                        st.rerun()

            # --- CASO 2: REGISTRAR HOY ---
            else:
                st.caption("Introduce horas trabajadas o indica que hoy NO se trabaja.")
                c_save, c_nowork = st.columns(2)
                
                if c_save.button("💾 Guardar Jornada Trabajada", use_container_width=True, type="primary"):
                    existe = supabase.table('fichajes').select("*").eq('empleado_id', user['id']).eq('fecha', str(fecha_selec)).execute()
                    if existe.data:
                        st.error("Ya has fichado hoy.")
                    else:
                        data = {
                            "empleado_id": user['id'], "fecha": str(fecha_selec), 
                            "hora_entrada": str(h_entrada), "hora_salida": str(h_salida), 
                            "horas_descanso": h_comida, "tipo_registro": "trabajo", "estado": "aprobado"
                        }
                        supabase.table('fichajes').insert(data).execute()
                        st.success("Jornada registrada.")
                        st.rerun()
                
                if c_nowork.button("⛔ Hoy NO se trabaja / Cerrado", use_container_width=True):
                    existe = supabase.table('fichajes').select("*").eq('empleado_id', user['id']).eq('fecha', str(fecha_selec)).execute()
                    if existe.data:
                        st.error("Ya has fichado hoy.")
                    else:
                        data = {
                            "empleado_id": user['id'], "fecha": str(fecha_selec), 
                            "hora_entrada": "00:00", "hora_salida": "00:00", 
                            "horas_descanso": 0, "tipo_registro": "no_trabajado", "estado": "aprobado"
                        }
                        supabase.table('fichajes').insert(data).execute()
                        st.success("Registrado como No Trabajado.")
                        st.rerun()

        # ---------------------------------------------------------
        # B: PLANIFICAR FUTURO
        # ---------------------------------------------------------
        st.write("")
        with st.expander("✈️ Planificar Vacaciones o Periodos Largos"):
            st.info("Selecciona el día de inicio y el día de fin. Se crearán solicitudes para todos los días laborables intermedios.")
            
            with st.form("futuro_form_rango"):
                col_f1, col_f2 = st.columns(2)
                rango_fechas = col_f1.date_input("Selecciona Periodo (Inicio - Fin)", value=[], min_value=hoy + timedelta(days=1))
                motivo_futuro = col_f2.selectbox("Tipo:", ["vacaciones_nopl", "asuntos_propios", "no_trabajado"], format_func=lambda x: TIPOS_REGISTRO.get(x, x))
                nota = st.text_input("Nota (Opcional)", placeholder="Ej: Viaje familiar")
                
                if st.form_submit_button("📅 Solicitar Periodo"):
                    if len(rango_fechas) != 2:
                        st.warning("Por favor, selecciona una fecha de INICIO y una fecha de FIN en el calendario.")
                    else:
                        inicio, fin = rango_fechas
                        delta = fin - inicio
                        dias_creados = 0
                        
                        for i in range(delta.days + 1):
                            dia_actual = inicio + timedelta(days=i)
                            if es_laborable(dia_actual):
                                existe = supabase.table('fichajes').select("id").eq('empleado_id', user['id']).eq('fecha', str(dia_actual)).execute()
                                if not existe.data:
                                    data = {
                                        "empleado_id": user['id'], "fecha": str(dia_actual), 
                                        "tipo_registro": motivo_futuro, "estado": "pendiente",
                                        "notas_admin": f"Periodo: {inicio.strftime('%d/%m')} - {fin.strftime('%d/%m')}. {nota}",
                                        "hora_entrada": "00:00", "hora_salida": "00:00", "horas_descanso": 0
                                    }
                                    supabase.table('fichajes').insert(data).execute()
                                    dias_creados += 1
                        
                        if dias_creados > 0:
                            periodo_str = f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}"
                            enviar_alerta_email(user['nombre'], periodo_str, motivo_futuro, "00:00", "00:00", es_futuro=True, es_rango=True)
                            st.success(f"Solicitud enviada para {dias_creados} días laborables.")
                            st.rerun()
                        else:
                            st.warning("No se ha creado ningún registro.")

        st.divider()
        if st.button("Cerrar Sesión"):
            del st.session_state['usuario']
            st.rerun()
