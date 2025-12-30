import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date, timedelta
import pandas as pd
import pytz
import io
import calendar

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(
    page_title="Gestión Clínica Carmen Fontes",
    page_icon="🦷",
    layout="wide" # Layout ancho para el panel de admin
)

# Intentar cargar el logo
try:
    st.image("logoccf.png", width=200)
except:
    st.write("🦷 Clínica Carmen Fontes") # Texto alternativo si no carga el logo

TZ_VALENCIA = pytz.timezone('Europe/Madrid')

# --- CONSTANTES ---
# ⚠️ IMPORTANTE: Actualizar estos festivos cada año. Ejemplo 2024 Valencia.
FESTIVOS_VALENCIA = [
    date(2024, 1, 1), date(2024, 1, 6), date(2024, 3, 19), date(2024, 3, 29),
    date(2024, 4, 1), date(2024, 5, 1), date(2024, 6, 24), date(2024, 8, 15),
    date(2024, 10, 9), date(2024, 11, 1), date(2024, 12, 6), date(2024, 12, 25)
]

TIPOS_AUSENCIA = {
    "vacaciones_nopl": "🏖️ Vacaciones No Planificadas",
    "asuntos_propios": "🏠 Asuntos Propios",
    "olvido": "🤦 Registro Olvidado",
    "trabajo": "💼 Trabajo Normal"
}

ESTADOS_COLOR = {
    "pendiente": "⚠️ Pendiente",
    "aprobado": "✅ Aprobado",
    "rechazado": "❌ Rechazado"
}

# --- CONEXIÓN SUPABASE ---
try:
    url = st.secrets["SUPABASE"]["url"]
    key = st.secrets["SUPABASE"]["key"]
    supabase: Client = create_client(url, key)
except:
    st.error("⚠️ Error de conexión: Revisa los Secrets.")
    st.stop()

# --- FUNCIONES AUXILIARES ---

def es_laborable(fecha: date):
    """Devuelve True si es de Lunes a Viernes y NO es festivo"""
    if fecha.weekday() >= 5: # 5=Sábado, 6=Domingo
        return False
    if fecha in FESTIVOS_VALENCIA:
        return False
    return True

def obtener_empleado(nombre, pin):
    response = supabase.table('empleados').select("*").eq('nombre', nombre).eq('pin_secreto', pin).execute()
    return response.data[0] if response.data else None

def obtener_lista_empleados_activos():
    usuarios = supabase.table('empleados').select("id, nombre").eq('activo', True).execute()
    return usuarios.data if usuarios.data else []

# --- FUNCIONES DE FICHAJE (EMPLEADO) ---

def registrar_fichaje_normal(empleado_id, tipo, id_fichaje=None):
    ahora = datetime.now(TZ_VALENCIA)
    hora = ahora.strftime('%H:%M:%S')
    fecha = ahora.strftime('%Y-%m-%d')
    
    if tipo == "ENTRADA":
        # Por defecto, un fichaje normal es 'pendiente' hasta que la jefa lo revise
        data = {"empleado_id": empleado_id, "fecha": fecha, "hora_entrada": hora, "tipo_registro": "trabajo", "estado": "pendiente"}
        supabase.table('fichajes').insert(data).execute()
        st.toast(f"✅ Entrada registrada a las {hora}. Pendiente de aprobación.")
    elif tipo == "SALIDA":
        supabase.table('fichajes').update({"hora_salida": hora}).eq('id', id_fichaje).execute()
        st.toast(f"👋 Salida registrada a las {hora}.")

# --- FUNCIONES DE ADMIN ---

def nuevo_empleado(nombre, telefono, pin):
    data = {"nombre": nombre, "telefono": telefono, "pin_secreto": pin}
    supabase.table('empleados').insert(data).execute()

def crear_registro_ausencia(empleado_id, fecha_ausencia, motivo):
    """El admin crea un registro para un día que faltaba"""
    data = {
        "empleado_id": empleado_id,
        "fecha": fecha_ausencia.strftime('%Y-%m-%d'),
        # No ponemos horas de entrada/salida porque es una ausencia justificada
        "tipo_registro": motivo,
        "estado": "pendiente", # Se crea como pendiente para revisarlo luego
        "notas_admin": "Registro de ausencia creado por Administración."
    }
    supabase.table('fichajes').insert(data).execute()

def actualizar_estado_fichaje(fichaje_id, nuevo_estado, notas, nuevo_tipo=None):
    data = {"estado": nuevo_estado, "notas_admin": notas}
    if nuevo_tipo:
        data["tipo_registro"] = nuevo_tipo
    
    supabase.table('fichajes').update(data).eq('id', fichaje_id).execute()


# ==============================================
# INTERFAZ PRINCIPAL
# ==============================================

# Cargar lista de nombres para el login
lista_emps = obtener_lista_empleados_activos()
nombres_login = [u['nombre'] for u in lista_emps] if lista_emps else []

if 'usuario' not in st.session_state:
    # --- PANTALLA DE LOGIN ESTILIZADA ---
    st.markdown("<h1 style='text-align: center; color: #D4A5A5;'>Bienvenida al Portal del Empleado</h1>", unsafe_allow_html=True)
    st.write("") # Espacio
    
    col_spacer1, col_login, col_spacer2 = st.columns([1, 2, 1])
    with col_login:
        st.markdown("""
            <div style='background-color: #FCEEEE; padding: 30px; border-radius: 15px; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);'>
            """, unsafe_allow_html=True)
        usuario_selec = st.selectbox("Selecciona tu nombre", [""] + nombres_login) # Opción vacía inicial
        pin_input = st.text_input("Tu PIN secreto", type="password")
        st.write("")
        if st.button("Acceder al Sistema 🔐", use_container_width=True, type="primary"):
            if usuario_selec and pin_input:
                emp = obtener_empleado(usuario_selec, pin_input)
                if emp:
                    st.session_state['usuario'] = emp
                    st.rerun()
                else:
                    st.error("Nombre o PIN incorrectos.")
            else:
                st.warning("Por favor, introduce usuario y PIN.")
        st.markdown("</div>", unsafe_allow_html=True)

else:
    # --- USUARIO LOGUEADO ---
    emp = st.session_state['usuario']
    
    # ========================================================
    # 👩‍💼 MODO JEFA (ADMINISTRADOR)
    # ========================================================
    if emp['nombre'] == 'Administrador':
        st.markdown("<div style='background-color: #D4A5A5; padding: 10px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>⚙️ MODO ADMINISTRADORA ACTIVO</div>", unsafe_allow_html=True)
        
        tab_equipo, tab_calendario, tab_aprobaciones, tab_informes = st.tabs([
            "👥 Equipo", 
            "📅 Detector de Ausencias (Calendario)", 
            "✅ Aprobaciones Pendientes",
            "📊 Informes Excel"
        ])
        
        # --- TAB 1: GESTIÓN EQUIPO (Igual que antes) ---
        with tab_equipo:
            st.subheader("Dar de alta nuevo empleado")
            with st.form("nuevo_emp"):
                col_a, col_b = st.columns(2)
                new_name = col_a.text_input("Nombre y Apellidos")
                new_tel = col_b.text_input("Teléfono")
                new_pin = st.text_input("Asignar PIN Secreto", type="password")
                if st.form_submit_button("Guardar Empleado 💾"):
                    if new_name and new_pin:
                        nuevo_empleado(new_name, new_tel, new_pin)
                        st.success(f"Empleado {new_name} creado.")
                        st.rerun()

        # --- TAB 2: DETECTOR DE AUSENCIAS (CALENDARIO VISUAL) ---
        with tab_calendario:
            st.subheader("📅 Control de días sin registrar")
            st.info("Selecciona un empleado y un mes para buscar días laborables que se les ha olvidado fichar y están en ROJO.")
            
            col_cal1, col_cal2, col_cal3 = st.columns(3)
            emp_cal_selec = col_cal1.selectbox("1. Seleccionar Empleado", lista_emps, format_func=lambda x: x['nombre'])
            mes_selec = col_cal2.selectbox("2. Mes", range(1, 13), index=datetime.now().month - 1)
            anyo_selec = col_cal3.number_input("3. Año", value=datetime.now().year, step=1)
            
            if emp_cal_selec and st.button("🔍 Analizar Mes"):
                # 1. Obtener todos los fichajes de ese empleado en ese mes/año
                start_date_str = f"{anyo_selec}-{mes_selec:02d}-01"
                # Truco para obtener el último día del mes
                last_day = calendar.monthrange(anyo_selec, mes_selec)[1]
                end_date_str = f"{anyo_selec}-{mes_selec:02d}-{last_day}"

                fichajes_mes = supabase.table('fichajes')\
                    .select("fecha, tipo_registro, estado")\
                    .eq('empleado_id', emp_cal_selec['id'])\
                    .gte('fecha', start_date_str)\
                    .lte('fecha', end_date_str)\
                    .execute()
                
                fechas_fichadas = {f['fecha']: f for f in fichajes_mes.data}

                # 2. Generar calendario y detectar huecos
                st.write("---")
                cal = calendar.Calendar()
                
                # Iteramos por las semanas del mes
                for week in cal.monthdatescalendar(anyo_selec, mes_selec):
                    cols = st.columns(7)
                    for i, dia in enumerate(week):
                        # Solo nos interesan los días del mes seleccionado (monthdatescalendar incluye días del mes anterior/siguiente para completar semana)
                        if dia.month == mes_selec:
                            with cols[i]:
                                fecha_str = dia.strftime("%Y-%m-%d")
                                
                                # LÓGICA DE COLORES DEL CALENDARIO
                                if not es_laborable(dia):
                                    # Fin de semana o festivo (Gris)
                                    st.markdown(f"<div style='background-color: #E0E0E0; padding: 10px; border-radius: 5px; text-align: center; opacity: 0.6;'>{dia.day}<br><small>Festivo/Finde</small></div>", unsafe_allow_html=True)
                                
                                elif fecha_str in fechas_fichadas:
                                    # Hay fichaje (Verde si aprobado, Naranja si pendiente)
                                    info_fichaje = fechas_fichadas[fecha_str]
                                    color_bg = "#C8E6C9" if info_fichaje['estado'] == 'aprobado' else "#FFE0B2"
                                    icono_estado = "✅" if info_fichaje['estado'] == 'aprobado' else "⏳"
                                    tipo_corto = TIPOS_AUSENCIA.get(info_fichaje['tipo_registro'], "???").split(" ")[0]
                                    st.markdown(f"<div style='background-color: {color_bg}; padding: 10px; border-radius: 5px; text-align: center;'>{dia.day}<br>{icono_estado} {tipo_corto}</div>", unsafe_allow_html=True)
                                
                                else:
                                    # 🔴🔴🔴 DÍA LABORABLE SIN FICHAJE 🔴🔴🔴
                                    st.markdown(f"<div style='background-color: #FFCDD2; padding: 10px; border-radius: 5px; text-align: center; border: 2px solid #E57373;'><strong>{dia.day}</strong><br>⚠️ FALTA</div>", unsafe_allow_html=True)
                                    # Botón para arreglarlo
                                    with st.popover("Arreglar"):
                                        st.write(f"Crear registro para el día {dia.day}")
                                        motivo_ausencia = st.selectbox("Motivo", options=["vacaciones_nopl", "asuntos_propios", "olvido"], format_func=lambda x: TIPOS_AUSENCIA[x], key=f"motivo_{fecha_str}")
                                        if st.button("Registrar Ausencia", key=f"btn_{fecha_str}"):
                                            crear_registro_ausencia(emp_cal_selec['id'], dia, motivo_ausencia)
                                            st.toast("Registro creado. Ahora aparecerá en 'Aprobaciones Pendientes'.")
                                            st.rerun()
                        else:
                             # Días de otros meses (vacío)
                             with cols[i]:
                                 st.write("")


        # --- TAB 3: APROBACIONES PENDIENTES ---
        with tab_aprobaciones:
            st.subheader("✅ Revisión de Registros Pendientes")
            # 1. Cargar fichajes pendientes con datos del empleado cruzados
            pendientes = supabase.table('fichajes')\
                .select("*, empleados(nombre)")\
                .eq('estado', 'pendiente')\
                .order('fecha', desc=True)\
                .execute()
            
            if not pendientes.data:
                st.success("¡Todo al día! No hay registros pendientes de aprobar.")
            else:
                st.write(f"Hay {len(pendientes.data)} registros esperando tu revisión.")
                
                for p in pendientes.data:
                    nombre_emp = p['empleados']['nombre'] if p['empleados'] else "Desconocido"
                    tipo_bonito = TIPOS_AUSENCIA.get(p['tipo_registro'], p['tipo_registro'])
                    
                    with st.expander(f"📅 {p['fecha']} | 👤 {nombre_emp} | {tipo_bonito}", expanded=True):
                        col_info, col_accion = st.columns([2, 3])
                        with col_info:
                            st.write(f"**Horario:** {p['hora_entrada'] or '--'} - {p['hora_salida'] or '--'}")
                            st.write(f"**Tipo:** {tipo_bonito}")
                            if p['notas_admin']: st.caption(f"Nota previa: {p['notas_admin']}")

                        with col_accion:
                            with st.form(key=f"form_aprobar_{p['id']}"):
                                st.write("Acción a realizar:")
                                nueva_nota = st.text_area("Añadir nota o comentario (se guardará en BBDD):", value=p.get('comentarios') or "")
                                col_apr, col_rech, col_cambio = st.columns(3)
                                
                                aprobar = col_apr.form_submit_button("✅ Aprobar")
                                rechazar = col_rech.form_submit_button("❌ Rechazar")
                                # Opción avanzada: cambiar el motivo y aprobar
                                nuevo_motivo_cambio = col_cambio.selectbox("Cambiar motivo y aprobar", [""] + list(TIPOS_AUSENCIA.keys()), format_func=lambda x: TIPOS_AUSENCIA.get(x, "Seleccionar si aplica"))
                                cambiar_aprobar = col_cambio.form_submit_button("🔄 Cambiar y Aprobar")

                                if aprobar:
                                    actualizar_estado_fichaje(p['id'], "aprobado", nueva_nota)
                                    st.success("Aprobado.")
                                    st.rerun()
                                elif rechazar:
                                    actualizar_estado_fichaje(p['id'], "rechazado", nueva_nota)
                                    st.error("Rechazado.")
                                    st.rerun()
                                elif cambiar_aprobar and nuevo_motivo_cambio:
                                    actualizar_estado_fichaje(p['id'], "aprobado", nueva_nota, nuevo_tipo=nuevo_motivo_cambio)
                                    st.success(f"Cambiado a {nuevo_motivo_cambio} y aprobado.")
                                    st.rerun()


        # --- TAB 4: INFORMES (Lo que ya tenías, actualizado con estado) ---
        with tab_informes:
            st.subheader("Descarga de datos")
            fichajes_all = supabase.table('fichajes').select("*, empleados(nombre)").order('fecha', desc=True).execute()
            
            if fichajes_all.data:
                df = pd.DataFrame(fichajes_all.data)
                # Aplanar la columna de objeto empleado para sacar el nombre
                df['nombre_empleado'] = df['empleados'].apply(lambda x: x['nombre'] if x else 'Desconocido')
                df.drop(columns=['empleados'], inplace=True)

                # Formatear para mostrar
                df_display = df[['fecha', 'nombre_empleado', 'tipo_registro', 'hora_entrada', 'hora_salida', 'estado', 'notas_admin']].copy()
                df_display['tipo_registro'] = df_display['tipo_registro'].map(TIPOS_AUSENCIA)
                
                # Colorear la tabla según estado usando Pandas Styler
                def color_estado(val):
                    color = '#C8E6C9' if val == 'aprobado' else '#FFCDD2' if val == 'rechazado' else '#FFE0B2'
                    return f'background-color: {color}'
                
                st.dataframe(df_display.style.applymap(color_estado, subset=['estado']), use_container_width=True)
                
                # Botón Excel
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='FichajesDetallados')
                
                st.download_button(
                    label="📥 Descargar Excel Completo para Gestoría",
                    data=buffer.getvalue(),
                    file_name=f"fichajes_clinica_completo_{datetime.now().date()}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.info("No hay datos.")

        st.divider()
        if st.button("Cerrar Sesión Administradora 🔒", type="secondary"):
            del st.session_state['usuario']
            st.rerun()

    # ========================================================
    # 🦷 MODO EMPLEADO NORMAL (Fichaje Sencillo)
    # ========================================================
    else:
        st.markdown(f"""
        <div style='background-color: #FCEEEE; padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
            <h2 style='color: #D4A5A5; margin:0;'>Hola, {emp['nombre']} 👋</h2>
        </div>
        """, unsafe_allow_html=True)
        
        hoy = datetime.now(TZ_VALENCIA).strftime('%Y-%m-%d')
        
        # Buscar fichaje de hoy
        log = supabase.table('fichajes').select("*").eq('empleado_id', emp['id']).eq('fecha', hoy).execute()
        datos_hoy = log.data
        
        col_espacio1, col_fichar, col_espacio2 = st.columns([1, 2, 1])
        
        with col_fichar:
            if not datos_hoy:
                # No ha fichado nada -> Botón Entrada
                st.info("No hay registros de hoy. ¡Que tengas buen turno!")
                if st.button("🟢 REGISTRAR ENTRADA AHORA", use_container_width=True, type="primary"):
                    registrar_fichaje_normal(emp['id'], "ENTRADA")
                    st.balloons()
                    del st.session_state['usuario'] # Logout automático
                    st.rerun()
                    
            else:
                # Ya hay registro -> Ver estado
                ficha = datos_hoy[0]
                
                # Mostrar estado del fichaje de hoy
                estado_str = ESTADOS_COLOR.get(ficha.get('estado', 'pendiente'), "Pendiente")
                st.caption(f"Estado de tu registro de hoy: {estado_str}")
                
                if ficha['hora_salida'] is None:
                    st.markdown(f"<div style='padding: 15px; background-color: #E3F2FD; border-radius: 10px; text-align:center;'>Entrada registrada a las: <strong>{ficha['hora_entrada']}</strong></div>", unsafe_allow_html=True)
                    st.write("")
                    if st.button("🔴 REGISTRAR SALIDA Y FINALIZAR", use_container_width=True):
                        registrar_fichaje_normal(emp['id'], "SALIDA", ficha['id'])
                        st.success("¡Jornada terminada! Gracias.")
                        del st.session_state['usuario']
                        st.rerun()
                else:
                    st.success(f"✅ Jornada de hoy completada: {ficha['hora_entrada']} - {ficha['hora_salida']}")
                    st.caption("Tu registro está pendiente de revisión por administración.")
                    if st.button("Cerrar Sesión"):
                        del st.session_state['usuario']
                        st.rerun()
