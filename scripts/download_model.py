"""Download the pinned public YOLOv8 pothole checkpoint and verify its SHA-256."""
import hashlib
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = '30a4d21de50998dbfa7cc79abb0d7a0d4aa71a4d'
URL = f'https://huggingface.co/Harisanth/Pothole-Finetuned-YOLOv8/resolve/{REVISION}/best.pt'
SHA256 = '8542745fa3e4f7ee0d03d8320443c6161747ba4658d2bbd770ee93abf7a7701a'

def main():
    target = ROOT / 'models' / 'pothole.pt'
    target.parent.mkdir(exist_ok=True)
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        print('Verified existing model:', target)
        return
    part = target.with_suffix('.download')
    try:
        print('Downloading public pothole model (23 MB)...', flush=True)
        with urlopen(URL, timeout=120) as response, part.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        if hashlib.sha256(part.read_bytes()).hexdigest() != SHA256:
            raise RuntimeError('Model checksum mismatch; download was not installed.')
        if target.exists():
            old_digest = hashlib.sha256(target.read_bytes()).hexdigest()
            backup = target.with_name(f'pothole-backup-{old_digest[:12]}.pt')
            if not backup.exists():
                import shutil
                shutil.copy2(target, backup)
                print('Previous checkpoint preserved:', backup)
        part.replace(target)
        print('Verified and saved:', target)
    finally:
        part.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
