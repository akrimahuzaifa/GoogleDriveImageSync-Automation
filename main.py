import os
import io
import traceback
import time
from datetime import datetime, timedelta
from PIL import Image, UnidentifiedImageError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from multiprocessing import Process, current_process
import math

SCOPES = ['https://www.googleapis.com/auth/drive']
LOG_FILE = "download_progress.log"
RESIZE_IMG = True
THUMBNAIL_SIZE = (800, 800)

BATCH_COUNT = os.cpu_count() or 8  # Fallback to 4 if unknown


def write_log(message):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{message}\n")
    print(message)

def authenticate_drive():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def human_readable_size(size_bytes):
    """Convert bytes to a human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def resize_image(file_path, size=(800, 800)):
    try:
        original_file_size = os.path.getsize(file_path)
        with Image.open(file_path) as img:
            original_dimensions = img.size
            img = img.convert("RGB")
            img.thumbnail(size, Image.LANCZOS)
            img.save(file_path, format='JPEG', quality=90)

        new_file_size = os.path.getsize(file_path)

        write_log(
            f"    • dimensions   = Original: {original_dimensions} ➜ New dimensions: {img.size}\n"
            f"    • Size on disk = Original: {human_readable_size(original_file_size)} ➜ After Resizing: {human_readable_size(new_file_size)}\n"
            f"🖼️ Resized Save to: {file_path}\n"
        )

    except UnidentifiedImageError:
        write_log(f"⚠️ Unidentified image format: {file_path}")
    except Exception as e:
        write_log(f"⚠️ Error resizing image {file_path}: {e}")


def download_image(service, file_id, file_name, folder_path):
    try:
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, file_name)

        if os.path.exists(file_path):
            # Get last modified time of the file
            modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            age_days = (datetime.now() - modified_time).days

            if age_days > 3:
                os.remove(file_path)
                write_log(f"🗑️ Deleted old file (>{age_days} days): {file_path}")
                return
            else:
                write_log(f"⏩ Skipped (already exists & recent - {age_days} days): {file_path}")
                return

        request = service.files().get_media(fileId=file_id)
        with open(file_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        write_log(f"✅ Downloaded: {file_path}")
        
        if RESIZE_IMG:
            resize_image(file_path)

    except Exception as e:
        write_log(f"❌ Error downloading {file_name}: {traceback.format_exc()}")


def process_folder(service, folder_id, parent_path):
    os.makedirs(parent_path, exist_ok=True)
    write_log(f"\n--------📁 Processing folder: {parent_path}--------\n")

    page_token = None
    while True:
        try:
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                spaces='drive',
                fields="nextPageToken, files(id, name, mimeType)",
                pageSize=100,
                pageToken=page_token
            ).execute()

            image_files = []
            subfolders = []

            for item in response.get('files', []):
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    subfolders.append(item)
                elif 'image/' in item['mimeType']:
                    image_files.append(item)

            for f in image_files:
                download_image(service, f['id'], f['name'], parent_path)

            for folder in subfolders:
                process_folder(service, folder['id'], os.path.join(parent_path, folder['name']))

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        except Exception:
            write_log(f"⚠️ Error in folder {parent_path}: {traceback.format_exc()}")
            break

def fetch_computers_root_folders(service):
    write_log("🔍 Fetching 'Computers' section folders...")
    computers_folders = []
    page_token = None

    while True:
        try:
            response = service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed = false",
                spaces='drive',
                fields='nextPageToken, files(id, name, parents)',
                pageSize=100,
                pageToken=page_token
            ).execute()

            for folder in response.get('files', []):
                if not folder.get('parents'):
                    computers_folders.append(folder)

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        except Exception:
            write_log(f"⚠️ Error fetching computers folders: {traceback.format_exc()}")
            break

    write_log(f"✅ Found {len(computers_folders)} root folders.")
    return computers_folders


def replicate_batch(service, folders_batch, local_base_path):
    for index, folder in enumerate(folders_batch, 1):
        folder_path = os.path.join(local_base_path, folder['name'])
        write_log(f"📂 Batch Processing: {folder['name']}")
        process_folder(service, folder['id'], folder_path)


def replicate_computers_section(service, local_base_path):
    computers_folders = fetch_computers_root_folders(service)
    if not computers_folders:
        write_log("❌ No folders found in 'Computers' section.")
        return

    for index, folder in enumerate(computers_folders, 1):
        folder_path = os.path.join(local_base_path, folder['name'])
        write_log(f"📂 ({index}/{len(computers_folders)}) Processing: {folder['name']}")
        process_folder(service, folder['id'], folder_path)

    write_log(f"🎉 All folders processed successfully at '{local_base_path}'.")

def split_into_batches(lst, n):
    """Split a list into `n` approximately equal batches."""
    k, m = divmod(len(lst), n)
    return (lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n))

def process_batch(service, folders_batch, local_base_path, batch_id):
    for index, folder in enumerate(folders_batch, 1):
        folder_path = os.path.join(local_base_path, folder['name'])
        write_log(f"[Batch-{batch_id}] 📂 ({index}/{len(folders_batch)}) Processing: {folder['name']}")
        process_folder(service, folder['id'], folder_path)
    write_log(f"[Batch-{batch_id}] ✅ Batch complete.")

def main():
    try:
        service = authenticate_drive()
        local_base_folder = os.path.join(os.getcwd(), "Computers_Drive")
        os.makedirs(local_base_folder, exist_ok=True)

        computers_folders = fetch_computers_root_folders(service)
        if not computers_folders:
            write_log("❌ No folders found in 'Computers' section.")
            return

        num_cores = os.cpu_count() or 4
        print(f"Available Cores: {num_cores}")
        batches = list(split_into_batches(computers_folders, num_cores))

        write_log(f"🚀 Starting download with {num_cores} parallel batches.")

        processes = []
        for i, batch in enumerate(batches):
            p = Process(target=process_batch, args=(service, batch, local_base_folder, i+1))
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

        write_log("🎉 All parallel batches completed successfully!")

    except Exception:
        write_log(f"🔥 Fatal error: {traceback.format_exc()}")

if __name__ == '__main__':
    main()
