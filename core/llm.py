import requests, json

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2:latest"

def _ask(prompt: str, max_tokens: int = 256, model_name: str = None) -> str:
    model = model_name or DEFAULT_MODEL
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7}
        }, timeout=180)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
        return ""
    except:
        return ""

def generate_title(transcript: str, topik: str = "", model_name: str = None) -> str:
    prompt = f"""Buat 1 judul video pendek (max 60 karakter) yang membuat penasaran dari transkrip ini. Judul harus langsung menarik perhatian. Hanya 1 opsi, tanpa penjelasan.

Transkrip:
{transcript[:500]}

Judul:"""
    result = _ask(prompt, 80, model_name)
    if result and len(result) > 5:
        return result[:80]
    return ""

def generate_description(transcript: str, title: str = "", model_name: str = None) -> str:
    prompt = f"""Buat deskripsi untuk video pendek (max 150 kata) berdasarkan transkrip ini. 
- Buka dengan hook yang menarik dari transkrip
- Jelaskan isi video secara natural, dari transkrip
- Akhiri dengan CTA (ajakan) yang relevan dengan isi video
- Bahasa Indonesia natural, seperti orang ngomong

Transkrip:
{transcript[:1000]}

Deskripsi:"""
    result = _ask(prompt, 300, model_name)
    if result and len(result) > 20:
        return result[:500]
    return ""

def generate_tags(transcript: str, topik: str = "", model_name: str = None) -> list:
    prompt = f"""Buat 10-15 hashtag yang relevan untuk video YouTube/TikTok dari transkrip ini. Pisahkan dengan spasi. Contoh: tips bisnis online marketing digital

Transkrip:
{transcript[:500]}

Hashtag:"""
    result = _ask(prompt, 150, model_name)
    if result:
        tags = result.strip().split()
        return [t.lstrip("#") for t in tags if t][:15]
    return []

def find_moments_with_llm(transcript: str, duration: float, model_name: str = None) -> list:
    prompt = f"""Kamu adalah ahli editing video pendek (TikTok/Shorts/Reels).
Analisis transkrip video berikut (total durasi {duration} detik) dan tentukan 3 momen paling viral.
Momen harus berupa:
1. HOOK (Pembukaan menarik, 0 - 15 detik pertama)
2. KLIMAKS (Inti paling menarik/lucu/mengejutkan)
3. CTA (Ajakan bertindak di akhir video)

Format output harus berupa JSON ARRAY murni berisi objek, tanpa teks penjelasan apa pun sebelum atau sesudah JSON!
Contoh format output:
[
  {{"start_time": 0.0, "end_time": 15.0, "reason": "Hook pembuka tentang rahasia sukses", "category": "HOOK"}},
  {{"start_time": 20.0, "end_time": 50.0, "reason": "Klimaks penjelasan cara kerja AI", "category": "KLIMAKS"}},
  {{"start_time": 50.0, "end_time": 60.0, "reason": "Ajakan follow dan like", "category": "CTA"}}
]

Batasan:
- Waktu start_time dan end_time harus angka float/integer antara 0 dan {duration}.
- start_time harus kurang dari end_time.

Transkrip:
{transcript}

JSON Output:"""
    result = _ask(prompt, 256, model_name)
    try:
        import re
        m = re.search(r"\[\s*\{.*\}\s*\]", result, re.DOTALL)
        json_str = m.group(0) if m else result
        data = json.loads(json_str)
        moments = []
        for item in data:
            moments.append({
                "start_time": float(item.get("start_time", 0)),
                "end_time": float(item.get("end_time", 0)),
                "reason": str(item.get("reason", "Momen viral oleh Llama AI")),
                "category": str(item.get("category", "AUTO")).upper()
            })
        return moments
    except Exception as e:
        print("[LLM ERROR] Gagal parse JSON momen:", e, "Result was:", result)
        return []
