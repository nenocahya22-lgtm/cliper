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
    prompt = f"""Kamu adalah ahli strategi konten viral untuk TikTok, YouTube Shorts, dan Instagram Reels.
Tugasmu: analisis transkrip video ini (durasi {duration} detik) dan temukan 3-5 momen dengan POTENSI VIRAL TERTINGGI.

Kriteria momen VIRAL:
1. HOOK (0-20 detik pertama):
   - Cari kalimat pembuka yang bikin penasaran, kontroversial, atau mengejutkan
   - Pertanyaan retoris, fakta mengejutkan, pernyataan berani
   - Kata-kata: 'tahukah', 'rahasia', 'jangan sampai', 'stop scrolling'
   
2. KLIMAKS / PLOT TWIST:
   - Bagian paling intens, mengejutkan, atau emosional
   - Momen 'plot twist', pengakuan mengejutkan, atau puncak cerita
   - Kata-kata: 'tapi ternyata', 'akhirnya', 'tiba-tiba', 'luar biasa'
   
3. CTA (Ajakan Interaksi):
   - Bagian akhir yang mengajak subscribe, like, comment, share
   - Kalimat yang bikin orang mau klik follow

4. MOMEN VIRAL LAINNYA (jika ada):
   - Bagian lucu, relatable, atau kontroversial
   - Kutipan yang bisa jadi 'sound viral'
   - Momen emosional yang bikin baper/merinding

🚨 FORMAT OUTPUT (WAJIB):
Keluarkan ONLY JSON ARRAY. NO teks lain sebelum/sesudah JSON!
[
  {{"start_time": 0.0, "end_time": 15.0, "reason": "[jelaskan kenapa ini viral: hook kuat, bikin penasaran tentang rahasia sukses]", "category": "HOOK", "viral_score": 9}},
  {{"start_time": 20.0, "end_time": 45.0, "reason": "[plot twist mengejutkan yang bikin speechless]", "category": "KLIMAKS", "viral_score": 10}},
  {{"start_time": 50.0, "end_time": 60.0, "reason": "[ajakan subscribe dengan alasan kuat]", "category": "CTA", "viral_score": 7}}
]

RULES:
- start_time dan end_time: angka float, 0 sampai {duration}
- start_time HARUS < end_time
- viral_score: 1-10 (10 = paling viral potential)
- Durasi tiap momen: 10-60 detik (idealnya 15-45 detik)

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
            score = item.get("viral_score", 7)
            reason = str(item.get("reason", "Momen viral oleh AI"))
            # Tambah skor ke reason untuk display
            stars = "⭐" * max(1, min(5, int(score / 2)))
            enriched_reason = f"{reason} [{stars}]"
            moments.append({
                "start_time": float(item.get("start_time", 0)),
                "end_time": float(item.get("end_time", 0)),
                "reason": enriched_reason,
                "category": str(item.get("category", "AUTO")).upper()
            })
        # Sort by viral potential (highest score first)
        try:
            moments.sort(key=lambda x: -float(x.get("viral_score", 0)))
        except:
            pass
        return moments
    except Exception as e:
        print("[LLM ERROR] Gagal parse JSON momen:", e, "Result was:", result)
        return []
