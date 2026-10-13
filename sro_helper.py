import io
from googleapiclient.http import MediaIoBaseUpload
from drive_helper import get_drive_service, MAIN_FOLDER_ID

def get_or_create_subfolder(service, folder_name: str, parent_id: str) -> str:
    """Ищет папку с указанным именем внутри parent_id, если нет — создаёт."""
    safe_name = folder_name.replace("'", "\\'")
    query = (
        f"name = '{safe_name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if folders:
        return folders[0]['id']

    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

def upload_sro_file(file_bytes: bytes, filename: str, student_name: str, subject_name: str, sro_num: str = "СРО 1") -> str:
    """
    Загружает файл в структуру:
    [Лекции] -> [СРО] -> [ФИО Студента] -> [Предмет] -> [СРО X] -> [Файл]
    """
    service = get_drive_service()

    # 1. Папка «СРО» внутри папки лекций
    sro_root_id = get_or_create_subfolder(service, "СРО", MAIN_FOLDER_ID)

    # 2. Папка студента (по его ФИО из базы)
    student_folder_id = get_or_create_subfolder(service, student_name, sro_root_id)

    # 3. Папка предмета внутри папки студента
    subject_folder_id = get_or_create_subfolder(service, subject_name, student_folder_id)

    # 4. Папка конкретного задания (СРО 1, СРО 2 и т.д.)
    sro_folder_id = get_or_create_subfolder(service, sro_num, subject_folder_id)

    # 5. Загрузка файла
    fh = io.BytesIO(file_bytes)
    media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=True)

    file_metadata = {
        'name': filename,
        'parents': [sro_folder_id]
    }

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()

    return uploaded_file.get('webViewLink')