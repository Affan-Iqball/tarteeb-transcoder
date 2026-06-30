import sys
import gdown
import re

def extract_file_id(url):
    # Try to match the ID in common Google Drive formats
    match = re.search(r'/file/d/([^/]+)', url)
    if match:
        return match.group(1)
    
    match = re.search(r'id=([^&]+)', url)
    if match:
        return match.group(1)
        
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python download.py <google_drive_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    file_id = extract_file_id(url)
    
    if not file_id:
        print(f"Error: Could not extract Google Drive File ID from URL: {url}")
        sys.exit(1)
        
    print(f"Extracted File ID: {file_id}")
    download_url = f"https://drive.google.com/uc?id={file_id}"
    
    # gdown automatically handles the 'virus scan' warning page bypass
    output_filename = "raw_video.mp4"
    try:
        output = gdown.download(download_url, output_filename, quiet=False, fuzzy=True, use_cookies=False)
        if not output:
            print("Error: gdown failed to download the file. Ensure the link is set to 'Anyone with the link can view'.")
            sys.exit(1)
        print(f"Successfully downloaded to {output_filename}")
        sys.exit(0)
    except Exception as e:
        print(f"Download failed with exception: {str(e)}")
        sys.exit(1)
