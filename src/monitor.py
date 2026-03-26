import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

from googleapiclient.errors import HttpError
from .auth import get_gmail_service, get_sheets_service

# Parámetros de configuración
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CONFIG_PATH = os.path.join(DATA_DIR, 'config.json')
WHITELIST_DOMAINS = [
    'gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com',
    'icloud.com', 'live.com', 'msn.com', 'rosariocentral.com',
]
MONITOR_STATE_PATH = os.path.join(DATA_DIR, 'monitor_state.json')


def _extract_domain(email_address):
    if not email_address or '@' not in email_address:
        return ''
    return email_address.split('@')[-1].lower().strip()


def _load_last_run():
    if not os.path.exists(MONITOR_STATE_PATH):
        return None
    try:
        with open(MONITOR_STATE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            ts = data.get('last_run')
            if not ts:
                return None
            return datetime.fromisoformat(ts)
    except Exception:
        return None


def _save_last_run():
    data = {'last_run': datetime.now(timezone.utc).isoformat()}
    with open(MONITOR_STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f)


def get_last_run_time():
    return _load_last_run()


def _normaliza_email(email_text):
    # Extrae el email de la forma 'Nombre <email@example.com>' o directamente email
    pattern = r'([\w\.-]+@[\w\.-]+)' 
    match = re.search(pattern, email_text)
    return match.group(1).strip().lower() if match else email_text.strip().lower()


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def _sheet_read_all(sheet_service, spreadsheet_id, sheet_name):
    range_name = f"{sheet_name}!A2:H"
    result = sheet_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        majorDimension='ROWS'
    ).execute()
    return result.get('values', [])


def _sheet_write_header(sheet_service, spreadsheet_id, sheet_name):
    header_values = [[
        'ID_Lead', 'Prospecto', 'Ultimo_Contacto', 'Estado',
        'Monto_ARS', 'Probabilidad', 'Dias_Inactivo', 'Ultimo_Thread_ID'
    ]]
    sheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f'{sheet_name}!A1:H1',
        valueInputOption='RAW',
        body={'values': header_values}
    ).execute()


def _row_to_lead(row):
    return {
        'ID_Lead': row[0] if len(row) > 0 else '',
        'Prospecto': row[1] if len(row) > 1 else '',
        'Ultimo_Contacto': row[2] if len(row) > 2 else '',
        'Estado': row[3] if len(row) > 3 else '',
        'Monto_ARS': row[4] if len(row) > 4 else '',
        'Probabilidad': row[5] if len(row) > 5 else '',
        'Dias_Inactivo': row[6] if len(row) > 6 else '',
        'Ultimo_Thread_ID': row[7] if len(row) > 7 else ''
    }


def _execute_with_retry(request, max_retries=5):
    for attempt in range(max_retries):
        try:
            return request.execute()
        except HttpError as err:
            status = int(getattr(err.resp, 'status', 0))
            if status in (429, 503):
                sleep_seconds = (2 ** attempt) + 1
                print(f"Quota rate limit / server busy ({status}). Reintentando en {sleep_seconds}s...")
                time.sleep(sleep_seconds)
                continue
            raise
    raise RuntimeError('No se pudo ejecutar la solicitud después de reintentos')


def _update_or_create_lead(sheet_service, spreadsheet_id, sheet_name, row_index, lead_data):
    # row_index es 0 basada en los datos (A2 es index 0). Se calcula como row_index + 2.
    target_row = row_index + 2
    values = [[
        lead_data.get('ID_Lead', ''),
        lead_data.get('Prospecto', ''),
        lead_data.get('Ultimo_Contacto', ''),
        lead_data.get('Estado', ''),
        lead_data.get('Monto_ARS', ''),
        lead_data.get('Probabilidad', ''),
        lead_data.get('Dias_Inactivo', f"=TODAY()-C{target_row}"),
        lead_data.get('Ultimo_Thread_ID', '')
    ]]
    range_name = f"{sheet_name}!A{target_row}:H{target_row}"
    request = sheet_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body={'values': values}
    )
    _execute_with_retry(request)


def run_monitor(force=False, max_messages=150):
    last_run = _load_last_run()
    if not force and last_run:
        elapsed = datetime.now(timezone.utc) - last_run
        if elapsed < timedelta(hours=24):
            print(f"Monitor: última ejecución hace {elapsed}, no toca correr de nuevo.")
            return {'status': 'skipped', 'last_run': last_run.isoformat()}

    config = load_config()
    spreadsheet_id = config['spreadsheet_id']
    sheet_name = config.get('sheet_name', 'Hoja 1')

    gmail = get_gmail_service()
    sheets = get_sheets_service()

    # Leer el estado actual de leads
    current_rows = _sheet_read_all(sheets, spreadsheet_id, sheet_name)
    existing = {row[0]: {'row_data': row, 'row_index': idx} for idx, row in enumerate(current_rows) if row}

    # Traer threads enviados recientes (último día)
    since_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y/%m/%d')
    query = f"after:{since_date}"
    resp = gmail.users().messages().list(userId='me', labelIds=['SENT'], q=query, maxResults=max_messages).execute()
    messages = resp.get('messages', [])

    if not messages:
        print('No hay mensajes enviados recientes')
        return

    new_leads = []
    updated_leads = []

    for m in messages:
        msg = gmail.users().messages().get(userId='me', id=m['id'], format='metadata', metadataHeaders=['To', 'Subject', 'Date']).execute()
        headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}
        to_field = headers.get('To', '')
        subject = headers.get('Subject', '')
        date_sent = headers.get('Date', '')

        # Extraemos un mail válido del campo To
        to_email = _normaliza_email(to_field)
        domain = _extract_domain(to_email)

        if not to_email or not domain or domain in WHITELIST_DOMAINS:
            continue

        # Datos del lead
        lead_id = to_email
        prospect_name = to_field.split('<')[0].strip().strip('"') or to_email
        contact_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        thread_id = msg.get('threadId', '')

        lead_data = {
            'ID_Lead': lead_id,
            'Prospecto': prospect_name,
            'Ultimo_Contacto': contact_date,
            'Estado': existing.get(lead_id, {}).get('row_data', ['', '', '', ''])[3] or 'Calificación',
            'Monto_ARS': existing.get(lead_id, {}).get('row_data', ['', '', '', '', ''])[4] or '0',
            'Probabilidad': existing.get(lead_id, {}).get('row_data', ['', '', '', '', '', ''])[5] or '0',
            'Ultimo_Thread_ID': thread_id,
        }

        if lead_id in existing:
            _update_or_create_lead(sheets, spreadsheet_id, sheet_name, existing[lead_id]['row_index'], lead_data)
            updated_leads.append(lead_id)
        else:
            # Append row para nuevo lead
            append_range = f"{sheet_name}!A:H"
            values = [[
                lead_data['ID_Lead'], lead_data['Prospecto'], lead_data['Ultimo_Contacto'],
                lead_data['Estado'], lead_data['Monto_ARS'], lead_data['Probabilidad'],
                f"=TODAY()-C{len(current_rows) + 2}", lead_data['Ultimo_Thread_ID']
            ]]
            request = sheets.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=append_range,
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': values}
            )
            _execute_with_retry(request)
            new_leads.append(lead_id)
            current_rows.append(values[0])

    print(f"Leads nuevos: {len(new_leads)}. Leads actualizados: {len(updated_leads)}")
    if new_leads:
        print('Nuevos:', new_leads)
    if updated_leads:
        print('Actualizados:', updated_leads)

    _save_last_run()
    return {
        'status': 'ran',
        'new_leads': len(new_leads),
        'updated_leads': len(updated_leads),
        'last_run': _load_last_run().isoformat(),
    }


if __name__ == '__main__':
    run_monitor()
