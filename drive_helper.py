import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ID вашей папки «лекции»
MAIN_FOLDER_ID = "1282un1P5x8Qk0tejGYAUjj-cPU_k1JxQ"

# Область доступа к Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Авторизация сервисного аккаунта"""
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    creds = Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def get_or_create_subject_folder(service, subject_name: str) -> str:
    """Ищет или создаёт папку предмета строго внутри основной папки лекций"""
    query = (
        f"name = '{subject_name}' and "
        f"'{MAIN_FOLDER_ID}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if folders:
        return folders[0]['id']

    folder_metadata = {
        'name': subject_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [MAIN_FOLDER_ID]
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

def upload_file_to_subject(file_path: str, filename: str, subject_name: str) -> str:
    """Загружает файл в подпапку предмета внутри папки лекций"""
    service = get_drive_service()
    folder_id = get_or_create_subject_folder(service, subject_name)

    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    
    media = MediaFileUpload(file_path, resumable=True)
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return uploaded_file.get('webViewLink')

# Алиас на случай, если где-то используется старое название
upload_file_to_drive = upload_file_to_subject