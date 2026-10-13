import io
from googleapiclient.http import MediaIoBaseUpload
from drive_helper import get_drive_service, MAIN_FOLDER_ID

def get_or_create_subfolder(service, folder_name: str, parent_id: str) -> str:
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

def get_existing_student_folders(student_name: str, subject_name: str) -> list:
    """Возвращает список уже созданных папок (СРО) конкретного студента по конкретному предмету."""
    try:
        service = get_drive_service()

        # 1. Ищем папку СРО
        q_sro = f"name = 'СРО' and '{MAIN_FOLDER_ID}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_sro = service.files().list(q=q_sro, fields="files(id)").execute().get('files', [])
        if not res_sro:
            return []
        sro_id = res_sro[0]['id']

        # 2. Ищем папку студента
        safe_student = student_name.replace("'", "\\'")
        q_student = f"name = '{safe_student}' and '{sro_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_student = service.files().list(q=q_student, fields="files(id)").execute().get('files', [])
        if not res_student:
            return []
        student_id = res_student[0]['id']

        # 3. Ищем папку предмета
        safe_subject = subject_name.replace("'", "\\'")
        q_subj = f"name = '{safe_subject}' and '{student_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        res_subj = service.files().list(q=q_subj, fields="files(id)").execute().get('files', [])
        if not res_subj:
            return []
        subj_id = res_subj[0]['id']

        # 4. Получаем список всех созданных подпапок (заданий)
        q_subfolders = f"'{subj_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        subfolders = service.files().list(q=q_subfolders, fields="files(id, name)", orderBy="name").execute().get('files', [])
        return [f['name'] for f in subfolders]
    except Exception as e:
        print(f"Ошибка получения существующих папок: {e}")
        return []

def upload_sro_file(file_bytes: bytes, filename: str, student_name: str, subject_name: str, sro_num: str = "СРО 1") -> str:
    service = get_drive_service()

    sro_root_id = get_or_create_subfolder(service, "СРО", MAIN_FOLDER_ID)
    student_folder_id = get_or_create_subfolder(service, student_name, sro_root_id)
    subject_folder_id = get_or_create_subfolder(service, subject_name, student_folder_id)
    sro_folder_id = get_or_create_subfolder(service, sro_num, subject_folder_id)

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