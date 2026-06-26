import requests, json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2"

def _ask(prompt: str, max_tokens: int = 256) -> str:
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7}
        }, timeout=60)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return ""
    except:
        return ""

def generate_title(transcript: str, topik: str = "") -> str:
    prompt = f"""Buat 1 judul video pendek (max 60 karakter) yang membuat penasaran dari transkrip ini. Judul harus langsung menarik perhatian. Hanya 1 opsi, tanpa penjelasan.

Transkrip:
{transcript[:500]}

Judul:"""
    result = _ask(prompt, 80)
    if result and len(result) > 5:
        return result[:80]
    return ""

def generate_description(transcript: str, title: str = "") -> str:
    prompt = f"""Buat deskripsi untuk video pendek (max 150 kata) berdasarkan transkrip ini. 
- Buka dengan hook yang menarik dari transkrip
- Jelaskan isi video secara natural, dari transkrip
- Akhiri dengan CTA (ajakan) yang relevan dengan isi video
- Bahasa Indonesia natural, seperti orang ngomong

Transkrip:
{transcript[:1000]}

Deskripsi:"""
    result = _ask(prompt, 300)
    if result and len(result) > 20:
        return result[:500]
    return ""

def generate_tags(transcript: str, topik: str = "") -> list:
    prompt = f"""Buat 10-15 hashtag yang relevan untuk video YouTube/TikTok dari transkrip ini. Pisahkan dengan spasi. Contoh: tips bisnis online marketing digital

Transkrip:
{transcript[:500]}

Hashtag:"""
    result = _ask(prompt, 150)
    if result:
        tags = result.strip().split()
        return [t.lstrip("#") for t in tags if t][:15]
    return []
