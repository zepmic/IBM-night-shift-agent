import base64, hashlib, json, os
from arena import llm
CACHE="runs/vision_cache.json"
_c=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
Q="Transcribe ALL text in this image exactly, including notes, captions and small print."
def make(read):
    def vision(path):
        data=read(path); h=hashlib.sha256(data).hexdigest()
        if h not in _c:
            ct="image/png" if path.lower().endswith(".png") else "image/jpeg"
            _c[h]=llm.describe_image(f"data:{ct};base64,"+base64.b64encode(data).decode(), Q)
            json.dump(_c,open(CACHE,"w"))
        return _c[h]
    return vision
