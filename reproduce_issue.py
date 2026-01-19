import sys
from pathlib import Path
from urllib.parse import unquote, quote

# Setup paths
root_path = Path(r"c:\Users\Admin\Desktop\Agentes IA en Acción Legacy")
course_path = root_path / "video-player" / "COURSE"

# The problematic directory and file
# Note: I am copying the string exactly as it appeared in list_dir output
subdir_name = "1 Qué Es N8N y Por Qué Es Clave para Automatización y Agentes de IA"
parent_dir = "- Recursos Youtube"
file_name = "Qué Es N8N y Por Qué Es Clave para Automatización y Agentes de IA (1080p_30fps_H264-128kbit_AAC).mp4"

# Construct the full path using pathlib to verify it exists first
full_real_path = course_path / parent_dir / subdir_name / file_name

print(f"Checking existence of: {full_real_path}")
print(f"Exists: {full_real_path.exists()}")

if not full_real_path.exists():
    print("CRITICAL: File does not exist via direct path construction!")
    # Try listing directory to see what Python sees
    print("Listing parent directory:")
    try:
        for p in (course_path / parent_dir / subdir_name).iterdir():
            print(f" - {p.name}")
            print(f"   bytes: {p.name.encode('utf-8')}")
    except Exception as e:
        print(f"Error listing dir: {e}")

# Now mimic server logic
# 1. Simulate the URL string
rel_path = f"{parent_dir}/{subdir_name}/{file_name}"
# Scanner does quote on individual parts
parts = [parent_dir, subdir_name, file_name]
encoded_parts = [quote(p, safe='') for p in parts]
url_path = "/media/" + "/".join(encoded_parts)

print(f"\nConstructed URL: {url_path}")

# 2. Server decodes it
# Server strips /media/
request_path = url_path[7:] # remove /media/
decoded = unquote(request_path)
print(f"Server decoded path: {decoded}")

# 3. Server joins with course_path
server_file_path = course_path / decoded
print(f"Server resolved path: {server_file_path}")
print(f"Server path exists: {server_file_path.exists()}")

# Test opening
if server_file_path.exists():
    try:
        with open(server_file_path, 'rb') as f:
            print("Successfully opened file")
    except Exception as e:
        print(f"Failed to open file: {e}")
