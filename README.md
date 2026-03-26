# Central de Ventas

Aplicación simple para gestionar actividades de ventas usando emails y Google Sheets.

## Configuración Inicial

1. **Crea un proyecto en Google Cloud Console**:
   - Ve a https://console.cloud.google.com/
   - Crea un proyecto nuevo.
   - Habilita las APIs: Gmail API y Google Sheets API.

2. **Descarga credentials.json**:
   - En Credentials, crea OAuth 2.0 Client ID (tipo Desktop).
   - Descarga el archivo JSON y renómbralo a `credentials.json`.
   - Colócalo en la carpeta `data/`.

3. **Crea un Google Sheet**:
   - Crea un nuevo Sheet en Google Sheets.
   - Copia el ID del Sheet (de la URL: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit).
   - Edita `data/config.json` y reemplaza `TU_SPREADSHEET_ID_AQUI` con el ID real.

4. **Ejecuta la inicialización**:
   - Corre `python src/init_sheet.py` para configurar las columnas.

5. **Autenticación**:
   - La primera vez, corre cualquier script que use auth.py; se abrirá un navegador para autorizar.

## Uso

- **Monitor de Salida**: Próximamente.
- **Dashboard**: Próximamente.

## Dependencias

Instaladas automáticamente con `pip install -r requirements.txt`.