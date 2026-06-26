import core.llm as llm
import core.finder as finder

def generate_title(transcript: str, topik: str = "", moments: list = None) -> str:
    result = llm.generate_title(transcript, topik)
    if result: return result

    if moments:
        hook = next((m for m in moments if m.category == "HOOK"), None)
        if hook and hook.transcript_snippet:
            snippet = hook.transcript_snippet.strip()[:65]
            if snippet: return snippet

    sentences = [s.strip() for s in transcript.replace("?", ".").replace("!", ".").split(".") if len(s.strip()) > 5]
    if sentences:
        return sentences[0][:65]
    return topik or "Video"

def generate_description(transcript: str, title: str = "", topik: str = "", moments: list = None) -> str:
    result = llm.generate_description(transcript, title)
    if result: return result

    if moments:
        hook = next((m for m in moments if m.category == "HOOK"), None)
        clim = next((m for m in moments if m.category == "KLIMAKS"), None)
        parts = []
        if hook and hook.transcript_snippet: parts.append(hook.transcript_snippet.strip())
        if clim and clim.transcript_snippet: parts.append(clim.transcript_snippet.strip())
        if parts: return " ".join(parts)

    sentences = [s.strip() for s in transcript.replace("?", ".").replace("!", ".").split(".") if len(s.strip()) > 5]
    return " ".join(sentences[:5]) if sentences else (topik or "Video")

def generate_tags(transcript: str, topik: str = "") -> list:
    result = llm.generate_tags(transcript, topik)
    if len(result) >= 3: return result

    stopwords = {"dan","di","ke","dari","yang","ini","itu","dengan","untuk","pada",
                 "adalah","akan","telah","sudah","bisa","tidak","juga","dalam","oleh",
                 "atau","saya","kita","kami","mereka","dia","anda","kalau","karena",
                 "jika","saat","seperti","ketika","setelah","sebelum","tentang","lalu",
                 "maka","saja","sangat","semua","hal","ada","banyak","lain","bikin","liat"}
    words = transcript.lower().split()
    filtered = [w.strip(".,!?;:'\"()[]") for w in words
                if w.strip(".,!?;:'\"()[]") not in stopwords and len(w) > 3]
    freq = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    sorted_words = [w for w, c in sorted(freq.items(), key=lambda x: -x[1])]
    tags = [topik] if topik else []
    tags += sorted_words[:10]
    return list(dict.fromkeys(tags))[:15] if tags else ["viral", "fyp", "trending"]

def generate_hashtag_string(transcript: str, topik: str = "") -> str:
    tags = generate_tags(transcript, topik)
    return " ".join(f"#{t.replace(' ', '')}" for t in tags)
