from typing import List, Tuple
from dataclasses import dataclass, field

@dataclass
class WordTimestamp:
    word: str; start: float; end: float

@dataclass
class ViralMoment:
    start_time: float; end_time: float; reason: str
    category: str; transcript_snippet: str = ""

@dataclass
class ProcessingResult:
    video_path: str = ""; audio_path: str = ""; title: str = ""
    duration: float = 0.0; transcript: str = ""
    word_timestamps: List[WordTimestamp] = field(default_factory=list)
    viral_moments: List[ViralMoment] = field(default_factory=list)
    output_path: str = ""; error: str = ""

class ViralMomentFinder:
    # ── Viral Hook Keywords ─────────────────────────────────────
    # HOOK: Pembuka yang bikin penasaran & engagement tinggi
    HOOK_KW = [
        "tahukah","coba lihat","perhatikan","bayangkan","tebak","rahasia","tips","wow",
        "gila","serius","nggak nyangka","ternyata","jangan sampai","penting","did you know",
        "omg","bro","guys","pernah gak sih","kalian tahu gak","stop scrolling","wait till",
        "you won't believe","incredible","shocking","mind blowing","this is crazy",
        "watch this","check this out","you need to see","this changes everything",
        "the truth about","what happened next","i can't believe","this is why",
        "the real reason","nobody tells you","the secret behind","how to actually",
        "stop everything","this one trick","game changer","life hack","terbaru",
        "heboh","viral banget","fyp","for you","must watch","don't skip","baru tau",
        "ga nyangka","ini dia","nih","wajib tonton","auto","bikin merinding",
        "bikin mewek","bikin ketawa","nggak nyangka","ngagetin","mengejutkan",
        "kebanyakan orang","99% orang","hanya sedikit","the moment when"
    ]

    # KLIMAKS: Intensitas tinggi, plot twist, atau puncak emosi
    CLIMAX_KW = [
        "tapi","namun","akhirnya","ternyata","tiba-tiba","luar biasa","gila","keren",
        "amazing","paling","sangat","sekali","bikin ngakak","lucu","parah","gokil","wkwk",
        "yang penting","intinya","pokoknya","plot twist","the twist","what the",
        "no way","for real","actually","the best part","here's the thing",
        "this is where","and then","suddenly","out of nowhere","boom","wow",
        "mind blowing","epic","legendary","insane","brilliant","genius",
        "tak terduga","di luar dugaan","puncaknya","klimaksnya","momen paling",
        "inti dari","yang bikin","sampai-sampai","bikin speechless","bikin merinding"
    ]

    # CTA: Ajakan berinteraksi di akhir video
    CTA_KW = [
        "follow","ikuti","subscribe","subs","langganan","like","share","bagikan",
        "komentar","simpan","jangan lupa","support","join","terima kasih","makasih",
        "sampai jumpa","bye bye","assalamualaikum","next video","stay tuned",
        "turn on notifications","comment below","let me know","what do you think",
        "drop a comment","hit that like","smash that like","see you next time",
        "jangan lupa subscribe","komen di bawah","share ke teman","tag teman",
        "save this video","bookmark this","follow for more","check out my",
        "link in bio","link di deskripsi","sampe sini dulu","sekian dulu",
        "salam kenal","jangan kemana-mana","tunggu video selanjutnya"
    ]

    # EMOSIONAL: Kata-kata dengan muatan emosi tinggi (viral potential)
    EMOTIONAL = {
        "gila","keren","amazing","wow","luar biasa","mengejutkan","terbaik","lucu",
        "ngakak","nangis","baper","semangat","motivasi","hebat","mantap","viral","parah","gokil",
        "brilliant","genius","incredible","shocking","epic","legendary","insane","mindblowing",
        "speechless","merinding","mewek","haru","terharu","greget","menegangkan",
        "fantastic","awesome","terbaik","terkeren","tergila","wonderful","magnificent",
        "sakti","jago","expert","masterpiece","goosebumps","thrilling","heartwarming",
        "kontroversial","debatable","unik","langka","rare","exclusive","rahasia umum"
    }

    @staticmethod
    def find_moments(transcript: str, duration: float, word_ts: List[WordTimestamp],
                     use_llm: bool = False, model_name: str = None) -> List[ViralMoment]:
        if use_llm:
            from core.llm import find_moments_with_llm
            moments_raw = find_moments_with_llm(transcript, duration, model_name)
            if moments_raw:
                res = []
                for m in moments_raw:
                    res.append(ViralMoment(m["start_time"], m["end_time"], m["reason"], m["category"], ""))
                words = transcript.split()
                for m in res:
                    m.transcript_snippet = " ".join(ViralMomentFinder._words_in_range(word_ts, words, duration, m.start_time, m.end_time))[:300]
                # Sort by viral potential — use category priority if no viral_score
                priority = {"HOOK": 10, "KLIMAKS": 8, "CTA": 6, "AUTO": 4}
                res.sort(key=lambda x: -priority.get(x.category, 5))
                return res

        if not transcript or duration <= 5:
            return [ViralMoment(0, min(duration,30), "Klip pendek", "KLIMAKS", transcript or "")]
        words = transcript.split()
        if len(words) < 5:
            return [ViralMoment(0, min(duration,30), "Video dengan sedikit teks", "KLIMAKS", transcript)]

        num = min(8, max(3, int(duration/15)))
        part_dur = duration / num
        scores = []
        for i in range(num):
            ps, pe = i*part_dur, (i+1)*part_dur
            pw = ViralMomentFinder._words_in_range(word_ts, words, duration, ps, pe)
            pt = " ".join(pw).lower()
            sc = 0
            dens = len(pw) / max(part_dur, 1)
            if dens > 2.0: sc += 3
            elif dens > 1.0: sc += 1
            for ew in ViralMomentFinder.EMOTIONAL:
                if ew.lower() in pt: sc += 2
            scores.append({"start":ps,"end":pe,"score":sc,"text":pt[:200]})

        first = " ".join(ViralMomentFinder._words_in_range(word_ts, words, duration, 0, duration*0.2)).lower()
        hr = "Pembukaan video"
        for kw in ViralMomentFinder.HOOK_KW:
            if kw.lower() in first: hr = f"Hook: '{kw}'"; break
        if scores and scores[0]["score"] >= 3: hr += " (intensitas tinggi)"
        hook = ViralMoment(0.0, min(15.0, duration*0.2), hr, "HOOK", first[:200])

        mid = scores[1:-1] if len(scores)>2 else scores
        best = max(mid, key=lambda p: p["score"]) if mid else scores[len(scores)//2]
        mp = (best["start"]+best["end"])/2
        cs, ce = max(0,mp-15), min(duration,mp+15)
        cr = "Inti pembahasan"
        for kw in ViralMomentFinder.CLIMAX_KW:
            if kw.lower() in best["text"]: cr = f"Klimaks: '{kw}'"; break
        if best["score"] >= 5: cr += " (intensitas sangat tinggi)"
        elif best["score"] >= 3: cr += " (intensitas tinggi)"
        csnip = " ".join(ViralMomentFinder._words_in_range(word_ts, words, duration, cs, ce))[:300]
        climax = ViralMoment(cs, ce, cr, "KLIMAKS", csnip)

        cta_t = duration * 0.75
        cta_text = " ".join(ViralMomentFinder._words_in_range(word_ts, words, duration, cta_t, duration)).lower()
        cta_r = "Bagian akhir video"
        for kw in ViralMomentFinder.CTA_KW:
            if kw.lower() in cta_text: cta_r = f"CTA: '{kw}'"; break
        cta = ViralMoment(cta_t, duration, cta_r, "CTA", cta_text[:200])
        return [hook, climax, cta]

    @staticmethod
    def _words_in_range(word_ts, all_words, duration, start, end):
        if word_ts:
            return [w.word for w in word_ts if w.start < end and w.end > start]
        if not all_words or duration <= 0: return []
        rs, re_ = start/duration, end/duration
        ws, we = int(rs*len(all_words)), int(re_*len(all_words))
        return all_words[max(0,ws):min(len(all_words),we)]

    @staticmethod
    def top_moments(moments: List[ViralMoment], transcript: str, duration: float,
                    word_ts: list, n: int = 5, min_dur: float = 30, max_dur: float = 60) -> List[ViralMoment]:
        if not moments:
            return [ViralMoment(0, min(duration, max_dur), "Full video", "AUTO", transcript[:200])]

        result = []
        used_ranges = []

        hook = next((m for m in moments if m.category == "HOOK"), None)
        climax = next((m for m in moments if m.category == "KLIMAKS"), None)
        cta = next((m for m in moments if m.category == "CTA"), None)

        candidates = []

        # 1. Hook alone
        if hook:
            d = min(hook.end_time - hook.start_time, max_dur)
            candidates.append((0, ViralMoment(hook.start_time, hook.start_time + d,
                f"Hook: {hook.reason}", "HOOK", hook.transcript_snippet)))

        # 2. Climax alone
        if climax:
            start = max(0, climax.start_time)
            d = min(climax.end_time - climax.start_time, max_dur)
            mid = (climax.start_time + climax.end_time) / 2
            cs = max(0, mid - max_dur/2)
            candidates.append((1, ViralMoment(cs, min(cs + max_dur, duration),
                f"Klimaks: {climax.reason}", "KLIMAKS", climax.transcript_snippet)))

        # 3. CTA alone
        if cta:
            d = min(cta.end_time - cta.start_time, max_dur)
            candidates.append((2, ViralMoment(cta.start_time, min(cta.start_time + max_dur, duration),
                f"CTA: {cta.reason}", "CTA", cta.transcript_snippet)))

        # 4. Hook + Climax
        if hook and climax:
            s = hook.start_time
            e = max(hook.end_time, climax.end_time)
            if e - s <= max_dur:
                candidates.append((3, ViralMoment(s, e,
                    f"Full: {hook.reason} + {climax.reason}", "AUTO",
                    (hook.transcript_snippet or "") + " [...] " + (climax.transcript_snippet or ""))))

        # 5. Extra segments from transcript analysis
        segments = ViralMomentFinder._split_transcript(transcript, duration, word_ts, min_dur, max_dur)
        for seg in segments:
            candidates.append((4, seg))

        # De-duplicate by start time
        candidates.sort(key=lambda x: x[1].start_time)
        seen_starts = set()
        unique = []
        for priority, m in candidates:
            rounded = round(m.start_time, 1)
            if rounded not in seen_starts:
                seen_starts.add(rounded)
                unique.append((priority, m))

        # Pick top N with minimum overlap
        unique.sort(key=lambda x: x[0])
        for _, m in unique:
            if len(result) >= n:
                break
            overlap = False
            for s, e in used_ranges:
                if m.start_time < e and m.end_time > s:
                    overlap = True
                    break
            if not overlap and (m.end_time - m.start_time) >= min_dur * 0.5:
                result.append(m)
                used_ranges.append((m.start_time, m.end_time))

        return result[:n]

    @staticmethod
    def _split_transcript(transcript: str, duration: float, word_ts: list,
                          min_dur: float, max_dur: float) -> List[ViralMoment]:
        if duration <= max_dur:
            return []
        parts = max(2, int(duration // max_dur))
        seg_dur = duration / parts
        result = []
        for i in range(parts):
            s = i * seg_dur
            e = min(s + max_dur, duration)
            snippet = " ".join(ViralMomentFinder._words_in_range(word_ts, transcript.split(), duration, s, e))[:200]
            if snippet:
                result.append(ViralMoment(s, e, f"Segmen {i+1}", "AUTO", snippet))
        return result

    @staticmethod
    def auto_best_moment(moments: List[ViralMoment], min_dur: float = 30, max_dur: float = 60) -> ViralMoment:
        hook = next((m for m in moments if m.category == "HOOK"), None)
        climax = next((m for m in moments if m.category == "KLIMAKS"), None)
        cta = next((m for m in moments if m.category == "CTA"), None)

        candidates = []

        # Hook only
        if hook:
            d = hook.end_time - hook.start_time
            candidates.append((d, hook))

        # Climax only
        if climax:
            d = climax.end_time - climax.start_time
            candidates.append((d, climax))

        # CTA only
        if cta:
            d = cta.end_time - cta.start_time
            candidates.append((d, cta))

        # Hook + Climax
        if hook and climax:
            combined_start = hook.start_time
            combined_end = max(hook.end_time, climax.end_time)
            d = combined_end - combined_start
            if d <= max_dur:
                candidates.append((d, ViralMoment(
                    combined_start, combined_end,
                    f"Hook + Klimaks ({hook.reason} + {climax.reason})",
                    "AUTO",
                    hook.transcript_snippet + " [...] " + climax.transcript_snippet
                )))

        # Hook + Climax + CTA (full story)
        if hook and climax and cta:
            combined_start = hook.start_time
            combined_end = max(hook.end_time, climax.end_time, cta.end_time)
            d = combined_end - combined_start
            if min_dur <= d <= max_dur:
                candidates.append((d, ViralMoment(
                    combined_start, combined_end,
                    f"Full Story: {hook.reason} + {climax.reason} + CTA",
                    "AUTO",
                    hook.transcript_snippet + " [...] " + climax.transcript_snippet + " [...] " + cta.transcript_snippet
                )))

        # Pick best in range
        valid = [(d, m) for d, m in candidates if min_dur <= d <= max_dur]
        if valid:
            # Prefer longer clips within range
            valid.sort(key=lambda x: -x[0])
            return valid[0][1]
        if candidates:
            candidates.sort(key=lambda x: -x[0])
            best_dur, best_moment = candidates[0]
            if best_dur < min_dur:
                return ViralMoment(best_moment.start_time, best_moment.start_time + min_dur,
                    f"{best_moment.reason} (diperpanjang ke {min_dur:.0f}s)", "AUTO", best_moment.transcript_snippet)
            if best_dur > max_dur:
                return ViralMoment(best_moment.start_time, best_moment.start_time + max_dur,
                    f"{best_moment.reason} (dipotong ke {max_dur:.0f}s)", "AUTO", best_moment.transcript_snippet)
            return best_moment
        return moments[0] if moments else ViralMoment(0, max_dur, "Full video", "AUTO", "")
