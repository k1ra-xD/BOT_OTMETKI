import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'

# ID главной папки "Учёба" на вашем Google Диске
PARENT_FOLDER_ID = '1282un1P5x8Qk0tejGYAUjj-cPU_k1JxQ'


def get_drive_service():
    """Авторизация и получение объекта сервиса Google Drive API."""
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)


def get_or_create_subfolder(service, folder_name: str, parent_id: str) -> str:
    """Ищет папку предмета внутри PARENT_FOLDER_ID. Если папки нет — создаёт её."""
    query = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if items:
        return items[0]['id']

    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')


async def upload_file_to_subject(file_bytes: bytes, filename: str, subject_name: str) -> str:
    """
    Загружает файл в папку указанного предмета и возвращает прямую ссылку на него.
    """
    service = get_drive_service()
    
    # 1. Находим или создаем папку для предмета (например, "Философия")
    subject_folder_id = get_or_create_subfolder(service, subject_name, PARENT_FOLDER_ID)
    
    # 2. Загружаем сам файл
    file_metadata = {
        'name': filename,
        'parents': [subject_folder_id]
    }
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype='application/octet-stream', resumable=True)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    return file.get('webViewLink')