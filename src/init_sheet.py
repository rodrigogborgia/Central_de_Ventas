import json
import os
from .auth import get_sheets_service

def init_sheet():
    """
    Inicializa el Google Sheet con las columnas necesarias.
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)

    spreadsheet_id = config['spreadsheet_id']
    sheet_name = config['sheet_name']

    service = get_sheets_service()

    # Columnas: A: ID_Lead, B: Prospecto, C: Ultimo_Contacto, D: Estado, E: Monto_ARS, F: Probabilidad, G: Dias_Inactivo, H: Ultimo_Thread_ID
    headers = [
        ['ID_Lead', 'Prospecto', 'Ultimo_Contacto', 'Estado', 'Monto_ARS', 'Probabilidad', 'Dias_Inactivo', 'Ultimo_Thread_ID']
    ]

    # Escribir headers en la fila 1
    range_name = f'{sheet_name}!A1:H1'
    body = {
        'values': headers
    }
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f"Sheet '{sheet_name}' inicializado con columnas.")

if __name__ == "__main__":
    init_sheet()