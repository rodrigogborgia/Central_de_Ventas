import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes para Gmail y Sheets
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]

def authenticate_google():
    """
    Autentica con Google APIs usando OAuth2.
    Requiere credentials.json en la carpeta data/.
    """
    creds = None
    token_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'token.json')
    creds_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'credentials.json')

    # Cargar token existente si existe
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Si no hay creds válidas, autenticar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    "No se encontró credentials.json en data/. "
                    "Descárgalo desde Google Cloud Console: "
                    "https://console.cloud.google.com/apis/credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # Guardar token
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return creds

def get_gmail_service():
    creds = authenticate_google()
    return build('gmail', 'v1', credentials=creds)

def get_sheets_service():
    creds = authenticate_google()
    return build('sheets', 'v4', credentials=creds)

if __name__ == "__main__":
    # Probar autenticación
    try:
        gmail_service = get_gmail_service()
        sheets_service = get_sheets_service()
        print("Autenticación exitosa. Servicios listos.")
    except Exception as e:
        print(f"Error en autenticación: {e}")