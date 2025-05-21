import os
import sys
import io
import traceback
import time
from datetime import datetime, timedelta
from pathlib import Path
from multiprocessing import Process, freeze_support
from PIL import Image, UnidentifiedImageError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm # Progress bar

# --- Path Configuration ---
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# --- Constants ---
SCOPES = ['https://www.googleapis.com/auth/drive']
LOG_FILE = BASE_DIR / "download_progress.log"
RESIZE_IMG = True
THUMBNAIL_SIZE = (800, 800)

# --- Logging Setup ---
def write_log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{log_entry}\n")
    print(log_entry)

# --- Core Functions ---
def authenticate_drive():
    creds = None
    token_path = BASE_DIR / 'token.json'
    credentials_path = BASE_DIR / 'credentials.json'
    
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                write_log("❌ Missing credentials.json file")
                sys.exit(1)
                
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)

def human_readable_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

def resize_image(file_path):
    try:
        original_file_size = os.path.getsize(file_path)
        with Image.open(file_path) as img:
            original_dimensions = img.size
            img = img.convert("RGB")
            img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
            img.save(file_path, format='JPEG', quality=90)

        new_file_size = os.path.getsize(file_path)
        """
        write_log(
            f"• Dimensions: {original_dimensions} → {img.size}"
            f"• Size: {human_readable_size(original_file_size)} → {human_readable_size(new_file_size)}\t"
            f"🖼️ Resized: {file_path}"
        )
        """
    except UnidentifiedImageError:
        write_log(f"⚠️ Unidentified image format: {file_path}")
    except Exception as e:
        write_log(f"⚠️ Error resizing {file_path}: {str(e)}")

def download_image(service, file_id, file_name, folder_path):
    try:
        target_dir = BASE_DIR / folder_path
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / file_name

        request = service.files().get_media(fileId=file_id)
        with file_path.open('wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            while not downloader.next_chunk()[1]: pass

        #write_log(f"✅ Downloaded: {file_path}")
        if RESIZE_IMG:
            resize_image(str(file_path))

    except Exception as e:
        write_log(f"❌ Error downloading {file_name}: {traceback.format_exc()}")

def process_folder(service, folder_id, parent_path, max_passes=3, delay=30):
    parent_dir = BASE_DIR / parent_path
    parent_dir.mkdir(parents=True, exist_ok=True)
    write_log(f"📁 Processing folder: {parent_path}")

    existing_files = {f.name for f in parent_dir.iterdir() if f.is_file()}
    
    for attempt in range(max_passes):
        write_log(f"🔁 Pass {attempt + 1}/{max_passes} for {parent_path}")
        new_files = 0

        try:
            page_token = None
            while True:
                response = service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    spaces='drive',
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageSize=100,
                    pageToken=page_token
                ).execute()

                items = response.get('files', [])
                subfolders = [f for f in items if f['mimeType'] == 'application/vnd.google-apps.folder']
                images = [f for f in items if 'image/' in f['mimeType']]

                for img in tqdm(images, desc=f"Processing images ", unit="image"):
                    file_path = parent_dir / img['name']
                    
                    # File existence and age check
                    if img['name'] in existing_files:
                        if file_path.exists():
                            file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                            if file_age.days > 3:
                                file_path.unlink()
                                write_log(f"🗑️ Deleted old file during Downloading process ({file_age.days}): {file_path}")
                            #else:
                                #write_log(f"⏩ Skipped recent file: [{file_age.days} day(s) old] Path: {file_path}")
                        continue
                    
                    # New file download
                    download_image(service, img['id'], img['name'], parent_path)
                    existing_files.add(img['name'])
                    new_files += 1

                # Process subfolders
                for folder in subfolders:
                    new_path = parent_dir / folder['name']
                    process_folder(service, folder['id'], str(new_path.relative_to(BASE_DIR)))

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

        except Exception:
            write_log(f"⚠️ Folder error: {traceback.format_exc()}")
            break

        if new_files == 0:
            write_log(f"✅ No new files in pass {attempt + 1}")
            break

        if attempt < max_passes - 1:
            write_log(f"⏳ Waiting {delay}s...")
            time.sleep(delay)

    write_log(f"🏁 Finished: {parent_path}")

def fetch_computers_folders(service):
    write_log("🔍 Fetching root folders...")
    folders = []
    page_token = None

    while True:
        try:
            response = service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(id, name, parents)',
                pageSize=100,
                pageToken=page_token
            ).execute()

            folders.extend([f for f in response.get('files', []) if not f.get('parents')])
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except Exception:
            write_log(f"⚠️ Folder fetch error: {traceback.format_exc()}")
            break

    write_log(f"✅ Found {len(folders)} root folders.")
    return folders

def split_batches(lst, n):
    k, m = divmod(len(lst), n)
    return (lst[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n))

def process_batch(service, batch, base_path, batch_id):
    for folder in tqdm(batch, desc=f"[Batch-{batch_id}] Progress", unit="folder"):
        folder_path = BASE_DIR / base_path / folder['name']
        write_log(f"[Batch-{batch_id}] Processing: {folder['name']}")
        process_folder(service, folder['id'], str(folder_path.relative_to(BASE_DIR)))

def cleanup_old_files(base_dir, days=3):
    write_log("🟢 Runing cleanup_old_files...")
    cutoff = datetime.now() - timedelta(days=days)
    all_files = []
    all_dirs = []
    for root, dirs, files in os.walk(base_dir, topdown=False):
        for name in files:
            all_files.append(Path(root) / name)
        for name in dirs:
            all_dirs.append(Path(root) / name)

    for file_path in tqdm(all_files, desc="Cleaning old files", unit="file"):
        this_timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
        if this_timestamp < cutoff:
            try:
                file_path.unlink()
                #write_log(f"🗑️  Pre-Cleaning: Deleted  (timestamp: {this_timestamp}, cutoff: {cutoff}): {file_path}")
            except Exception as e:
                write_log(f"⚠️  Pre-Cleaning: Error deleting file {file_path}: {e}")

    for dir_path in tqdm(all_dirs, desc="Cleaning old folders", unit="folder"):
        try:
            if not any(dir_path.iterdir()) and datetime.fromtimestamp(dir_path.stat().st_mtime) < cutoff:
                dir_path.rmdir()
                #write_log(f"🗑️  Pre-Cleaning: Deleted old empty folder: {dir_path}")
        except Exception as e:
            write_log(f"⚠️  Pre-Cleaning: Error deleting folder {dir_path}: {e}")

    write_log(f"✅ Pre-Cleaning: {days} day(s) old files checked & are removed...!")

def cleanup_old_log_entries(log_file, days=7):
    write_log("🟢 Runing cleanup_old_log_entries...")
    if not log_file.exists():
        write_log("❌ Log file not found... Will be created in run")
        return

    cutoff = datetime.now() - timedelta(days=days)
    # Use errors='replace' to avoid UnicodeDecodeError
    log_text = log_file.read_text(encoding='utf-8', errors='replace')
    lines = log_text.splitlines(keepends=True)
    new_lines = []
    for line in tqdm(lines, desc="Cleaning old log entries", unit="line"):
        if line.startswith('['):
            try:
                timestamp_str = line.split(']')[0][1:]
                log_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                if log_time >= cutoff:
                    new_lines.append(line)
            except Exception:
                # If parsing fails, keep the line
                new_lines.append(line)
        else:
            # Keep separator or non-timestamp lines
            new_lines.append(line)
    log_file.write_text(''.join(new_lines), encoding='utf-8')
    write_log(f"✅ Log file checked for last {days} entries & are removed...!")

def main():
    try:
        write_log(f"{'='*40}")
        write_log(f"🏁 Starting execution in: {BASE_DIR}")
        write_log(f"📁 Contents: {[f.name for f in BASE_DIR.iterdir()]}")
        
        # Cleanup old log entries before authentication
        cleanup_old_log_entries(LOG_FILE)

        # Cleanup old files/folders before authentication
        computers_drive = BASE_DIR / "Computers_Drive"
        if computers_drive.exists():
            cleanup_old_files(computers_drive)

        # Authenticate and fetch folders
        write_log("🔑 Authenticating with Google Drive...")
        service = authenticate_drive()
        base_folder = BASE_DIR / "Computers_Drive"
        base_folder.mkdir(exist_ok=True)

        folders = fetch_computers_folders(service)
        if not folders:
            write_log("❌ No folders found")
            return

        num_workers = os.cpu_count() or 4
        batches = list(split_batches(folders, num_workers))

        write_log(f"🚀 Starting {num_workers} parallel batches")
        processes = []

        for i, batch in enumerate(batches):
            p = Process(target=process_batch, args=(service, batch, base_folder, i+1))
            p.start()
            processes.append(p)

        # Wait for all processes to finish
        for p in processes:
            p.join()

        write_log("🎉 All batches completed!")
        write_log(f"{'='*40}")
        sys.exit(0)

    except Exception:
        write_log(f"🔥 Critical error: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    freeze_support()  # Required for PyInstaller
    main()
