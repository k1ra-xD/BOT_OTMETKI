import io
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

MAIN_FOLDER_ID = "1282un1P5x8Qk0tejGYAUjj-cPU_k1JxQ"
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Авторизация через пользовательский token.json"""
    token_path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
    
    if not os.path.exists(token_path):
        raise FileNotFoundError(
            f"Файл '{token_path}' не найден! Загрузите token.json в Secret Files на Render."
        )

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Автоматическое обновление токена, если он истечет
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def get_or_create_subject_folder(service, subject_name: str) -> str:
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

def upload_file_to_subject(
    file_path: str = None,
    filename: str = "file",
    subject_name: str = "Общее",
    file_bytes: bytes = None,
    **kwargs
) -> str:
    service = get_drive_service()
    folder_id = get_or_create_subject_folder(service, subject_name)

    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }

    if file_bytes is not None:
        if isinstance(file_bytes, bytes):
            fh = io.BytesIO(file_bytes)
        elif hasattr(file_bytes, 'read'):
            fh = file_bytes
        else:
            fh = io.BytesIO(bytes(file_bytes))
        media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=True)
    elif file_path is not None:
        media = MediaFileUpload(file_path, resumable=True)
    else:
        raise ValueError("Необходимо передать file_bytes или file_path")

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return uploaded_file.get('webViewLink')

upload_file_to_drive = upload_file_to_subject