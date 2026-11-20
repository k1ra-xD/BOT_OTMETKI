from google_auth_oauthlib.flow import InstalledAppFlow

# Права доступа (должны совпадать с теми, что в боте)
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    # access_type='offline' и prompt='consent' гарантируют получение refresh_token
    creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')

    with open('token.json', 'w', encoding='utf-8') as f:
        f.write(creds.to_json())

    print("✅ Готово! Новый token.json успешно создан в папке.")

if __name__ == '__main__':
    main()