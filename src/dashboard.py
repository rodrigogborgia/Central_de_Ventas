import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
from .auth import get_sheets_service
from .monitor import run_monitor, get_last_run_time

# Config
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
config_path = os.path.join(data_dir, 'config.json')

with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

spreadsheet_id = config['spreadsheet_id']
sheet_name = config.get('sheet_name', 'Hoja 1')

TEAM_LOGO_URL = 'https://rosariocentral.com/wp-content/uploads/2021/08/Central_Escudo.png'


def load_sales_data():
    service = get_sheets_service()
    range_name = f"{sheet_name}!A1:H"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        majorDimension='ROWS'
    ).execute()
    rows = result.get('values', [])
    if not rows or len(rows) < 2:
        return pd.DataFrame(columns=['ID_Lead', 'Prospecto', 'Ultimo_Contacto', 'Estado', 'Monto_ARS', 'Probabilidad', 'Dias_Inactivo', 'Ultimo_Thread_ID'])

    header = rows[0]
    data = rows[1:]
    df = pd.DataFrame(data, columns=header)

    # Normalizar
    df['Monto_ARS'] = pd.to_numeric(df.get('Monto_ARS', 0), errors='coerce').fillna(0)
    df['Probabilidad'] = pd.to_numeric(df.get('Probabilidad', 0), errors='coerce').fillna(0)
    df['Ultimo_Contacto'] = pd.to_datetime(df.get('Ultimo_Contacto', ''), errors='coerce')

    if 'Dias_Inactivo' in df.columns:
        df['Dias_Inactivo'] = pd.to_numeric(df['Dias_Inactivo'], errors='coerce').fillna((datetime.now() - df['Ultimo_Contacto']).dt.days)
    else:
        df['Dias_Inactivo'] = (datetime.now() - df['Ultimo_Contacto']).dt.days

    return df


def get_business_advice(df):
    # Placeholder para Gemini API. Si no está, retornamos consejos estáticos.
    if df.empty:
        return 'Aún no hay leads en el pipeline. Enfoca el próximo outreach en 5 empresas clave.', 'Haz seguimiento personalizado por WhatsApp en 24h.'

    stuck = df.sort_values('Dias_Inactivo', ascending=False).head(1)
    lead_name = stuck.iloc[0]['Prospecto'] if not stuck.empty else 'N/A'
    advice = f'Lead más estancado: {lead_name}. Revisa último thread y genera una propuesta con fecha concreta.'
    tactical = 'Envía un email breve con resumen de beneficios y CTA claro; menciona que tienes 3 slots de reunión esta semana.'
    return advice, tactical


def main():
    st.set_page_config(page_title='Central de Ventas', page_icon='🚀', layout='wide')

    st.markdown(
        f"""
        <style>
            .reportview-container {{ background: #002b5c; color: #f1f1f1; }}
            .sidebar .sidebar-content {{ background: #001f44; }}
            .stButton>button {{ background-color: #ffcc00; color: #002b5c; font-weight: bold; }}
            .stDataFrame table {{ background-color: #ffffff; color: #000000; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        st.image(TEAM_LOGO_URL, width=120)
    with col2:
        st.title('Central de Ventas (Rosario Central style)')
        st.subheader('Pipeline y Seguimiento Automático')

    # Ejecutar monitor al inicio de la sesión (una vez al día) y botón de refrescar manual
    if st.button('Buscar nuevos emails / Refrescar'):
        monitor_state = run_monitor(force=True)
    else:
        monitor_state = run_monitor(force=False)

    last_run = get_last_run_time()
    if last_run:
        st.info(f"Última búsqueda de nuevo contenido: {last_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        st.warning('Aún no se ha ejecutado el monitor de bandeja.')

    if monitor_state is not None and monitor_state.get('status') == 'ran':
        st.success(f"Monitor ejecutado: {monitor_state.get('new_leads', 0)} leads nuevos, {monitor_state.get('updated_leads', 0)} actualizados")
    elif monitor_state is not None and monitor_state.get('status') == 'skipped':
        st.info('Escaneo diario no necesario (ya corrido en las últimas 24h).')

    df = load_sales_data()

    st.markdown('### Resumen General')
    pipeline_total = df['Monto_ARS'].sum()
    won = df[df['Estado'].str.lower() == 'ganado']
    lost = df[df['Estado'].str.lower() == 'perdido']
    win_ratio = (len(won) / max(1, (len(won) + len(lost)))) * 100

    st.metric('Pipeline Total (ARS)', f"${pipeline_total:,.0f}")
    st.metric('Leads Totales', len(df), help='Total de registros en el pipeline')
    st.metric('Win/Loss Ratio', f"{win_ratio:.1f}%")

    st.markdown('### Leads Activos por Fase')
    if df.empty:
        st.warning('No hay datos en la hoja. Ejecuta el monitor de salida para empezar a capturar leads.')
    else:
        fase_counts = df['Estado'].fillna('Sin Estado').value_counts().reset_index()
        fase_counts.columns = ['Fase', 'Cantidad']
        st.table(fase_counts)

        st.markdown('### Leads detalle')
        df_display = df.copy()
        df_display['Dias_Inactivo'] = df_display['Dias_Inactivo'].fillna(0).astype(int)
        st.dataframe(df_display[['ID_Lead', 'Prospecto', 'Ultimo_Contacto', 'Estado', 'Monto_ARS', 'Probabilidad', 'Dias_Inactivo']], height=350)

    st.markdown('### Oportunidades que requieren seguimiento (>=7 días)')
    if not df.empty:
        need_follow = df[df['Dias_Inactivo'] >= 7]
        if need_follow.empty:
            st.success('No hay oportunidades con 7+ días inactivo.')
        else:
            st.dataframe(need_follow[['ID_Lead', 'Prospecto', 'Dias_Inactivo', 'Estado']], height=220)

    advice, tactical = get_business_advice(df)
    st.markdown('### El Consejo de BorgIA')
    st.info(advice)
    st.write(tactical)

    st.markdown('---')
    st.write('Última actualización:', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


if __name__ == '__main__':
    main()