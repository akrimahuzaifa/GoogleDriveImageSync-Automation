# Google Drive 'Computers' Section Image Sync

A Python-based utility to replicate the folder structure under the Google Drive **"Computers" section**, download image files, and maintain optimized, up-to-date local backups.

### NOTE: YOU NEED TO DOWNLOAD THE CREDENTIALS.JSON FILE FROM THE GOOGLE CONSOLE

---

## 🚀 Features

- ✅ Authenticates with Google Drive API.
- ✅ Recursively traverses folders in the "Computers" section.
- ✅ Preserves full folder hierarchy locally.
- ✅ Downloads images using Drive's binary content API.
- ✅ Skips already-downloaded files to support resume.
- ✅ Resizes images to 800x800 (maintaining aspect ratio).
- ✅ Logs progress and errors to a local log file.
- ✅ Deletes and re-downloads outdated images (older than 3 days).
- ✅ Prints original dimensions and size-on-disk stats before/after resizing.

---

## 🧱 Milestone Breakdown

### 🔹 Milestone 1: Google Drive Authentication & Folder Traversal

- Set up OAuth2 authentication (`credentials.json`, `token.json`).
- Fetched and processed all root folders in the "Computers" section.
- Maintained folder hierarchy during local directory creation.

### 🔹 Milestone 2: Image Download Implementation

- Downloaded image files via the direct binary content API.
- Saved images one by one to prevent corruption.

### 🔹 Milestone 3: Image Resizing After Download

- Resized downloaded images to 800x800 using PIL.
- Resized image saved over the original image.

### 🔹 Milestone 4: Logging and Debugging

- Created a `download_progress.log` to track:
  - Skipped, downloaded, resized, or deleted images.
  - Errors with tracebacks for debugging.

### 🔹 Milestone 5: Size & Dimension Reporting

- Printed original image dimensions before resizing.
- Logged size-on-disk before and after resizing.

### 🔹 Milestone 6: Resume Support for Downloads

- Skipped download if the image file already existed locally.
- Prevented re-downloading to optimize time.

### 🔹 Milestone 7: Cleanup of Outdated Images

- Deleted image if older than 3 days.
- Re-downloaded fresh copy automatically.

---

## 🛠 Requirements

- Python 3.x
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
- `Pillow`
- `requests`

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 📁 Directory Structure

```
Computers_Section_Replica_Thumbnails_Optimized/
├── My Laptop/
│   ├── Pictures/
│   │   ├── image1.jpg
│   │   └── image2.jpg
│   └── Documents/
│       └── screenshot.png
...
```

---

## 📌 Notes

- Be sure to generate `credentials.json` from your Google Cloud Console.
- The app will prompt browser-based login the first time and cache the session to `token.json`.
- All actions are logged to `download_progress.log`.

---

## 🧑‍💻 Author

Built with ❤️ using Python
by

### AKRIMA HUZAIFA AKHTAR.
