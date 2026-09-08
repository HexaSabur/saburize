from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re, os, uuid, asyncio, json, datetime, urllib.request, urllib.error
from typing import Optional
import warnings
import google.generativeai as genai

# ─────────────────────────────────────────────────────────
app = FastAPI(title="Otonom Ajan Kontrol Paneli")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

# ── Durum ────────────────────────────────────────────────
job_queues:    dict[str, asyncio.Queue]  = {}
MAX_GECMIS   = 20
is_gecmisi:   list[dict] = []
job_dosyalari: dict[str, dict[str, str]] = {}
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ── Bağlantı Deposu ──────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
BAGLANTILAR_DOSYA = os.path.join(_BASE, "baglantilar.json")
baglantilar: list[dict] = []

def baglantilar_yukle():
    global baglantilar
    if os.path.exists(BAGLANTILAR_DOSYA):
        try:
            with open(BAGLANTILAR_DOSYA, 'r', encoding='utf-8') as f:
                baglantilar = json.load(f)
        except Exception:
            baglantilar = []

def baglantilar_kaydet():
    with open(BAGLANTILAR_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(baglantilar, f, ensure_ascii=False, indent=2, default=str)

baglantilar_yukle()

# ── Veri Modelleri ────────────────────────────────────────
class PipelineIstegi(BaseModel):
    musteri_istegi: str
    kurallar: str
    model_adi:   Optional[str] = "gemini-1.5-flash"
    proje_adi:   Optional[str] = ""
    surge_token: Optional[str] = ""

class GelenVeri(BaseModel):
    ai_metni: str

class ApiKeyIstegi(BaseModel):
    api_key: str

class BaglantiEkle(BaseModel):
    tip:       str        # gemini | groq | openai | surge | netlify | github
    ad:        str
    api_key:   str
    aktif:     bool = True
    model_adi: Optional[str] = ""

class BaglantiGuncelle(BaseModel):
    ad:        Optional[str]  = None
    api_key:   Optional[str]  = None
    aktif:     Optional[bool] = None
    model_adi: Optional[str]  = None

# ── Yardımcılar ───────────────────────────────────────────
def sse_mesaj(veri: dict) -> str:
    return f"data: {json.dumps(veri, ensure_ascii=False)}\n\n"

def aktif_ai_baglanti_bul() -> tuple[str, str, str]:
    """(tip, api_key, model_adi)"""
    for b in baglantilar:
        if b.get('aktif') and b.get('tip') in ['gemini', 'groq', 'openai'] and b.get('api_key'):
            return b['tip'], b['api_key'], b.get('model_adi', '') or ''
    return 'gemini', GEMINI_API_KEY, ''

# ── Dashboard Serve ───────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    dosya = os.path.join(_BASE, "dashboard", "index.html")
    if os.path.exists(dosya):
        with open(dosya, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Dashboard bulunamadı. dashboard/index.html oluşturulmalı.</h1>")

# ── API Key ───────────────────────────────────────────────
@app.post("/api-key")
async def api_key_ayarla(istek: ApiKeyIstegi):
    global GEMINI_API_KEY
    if not istek.api_key.strip():
        return JSONResponse({"basarili": False, "mesaj": "API key boş olamaz."}, status_code=400)
    GEMINI_API_KEY = istek.api_key.strip()
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
    return {"basarili": True, "mesaj": "Gemini API key ayarlandı."}

@app.get("/api-key-durum")
async def api_key_durum():
    mevcut = bool(GEMINI_API_KEY)
    maskeli = (GEMINI_API_KEY[:8] + "..." + GEMINI_API_KEY[-4:]) if mevcut and len(GEMINI_API_KEY) > 12 else ("****" if mevcut else "")
    return {"mevcut": mevcut, "maskeli": maskeli}

# ── Modeller ─────────────────────────────────────────────
@app.get("/modeller")
async def modelleri_listele():
    return {"modeller": [
        {"id": "gemini-1.5-flash",           "ad": "Gemini 1.5 Flash",      "aciklama": "Hızlı · Ücretsiz"},
        {"id": "gemini-1.5-pro",             "ad": "Gemini 1.5 Pro",        "aciklama": "Güçlü · Ücretsiz"},
        {"id": "gemini-2.0-flash",           "ad": "Gemini 2.0 Flash",      "aciklama": "En yeni · Ücretsiz"},
        {"id": "llama-3.3-70b-versatile",    "ad": "Llama 3.3 70B (Groq)",  "aciklama": "Güçlü · Ücretsiz"},
        {"id": "llama-3.1-8b-instant",       "ad": "Llama 3.1 8B (Groq)",   "aciklama": "Ultra hız · Ücretsiz"},
        {"id": "mixtral-8x7b-32768",         "ad": "Mixtral 8x7B (Groq)",   "aciklama": "Uzun bağlam · Ücretsiz"},
    ]}

# ── Bağlantı CRUD ─────────────────────────────────────────
@app.get("/baglantilar")
async def baglantilar_listele():
    sonuc = []
    for b in baglantilar:
        item = {k: v for k, v in b.items() if k != 'api_key'}
        key = b.get('api_key', '')
        item['api_key_maskeli'] = (key[:8] + '...' + key[-4:]) if len(key) > 12 else ('****' if key else '')
        sonuc.append(item)
    return {"baglantilar": sonuc}

@app.post("/baglantilar")
async def baglanti_ekle(istek: BaglantiEkle):
    yeni = {
        "id":             str(uuid.uuid4()),
        "tip":            istek.tip,
        "ad":             istek.ad,
        "api_key":        istek.api_key,
        "aktif":          istek.aktif,
        "model_adi":      istek.model_adi or "",
        "son_test_zamani": None,
        "test_durumu":    "test_edilmedi",
        "test_mesaji":    ""
    }
    baglantilar.append(yeni)
    baglantilar_kaydet()
    return {"basarili": True, "id": yeni["id"]}

@app.put("/baglantilar/{bid}")
async def baglanti_guncelle(bid: str, istek: BaglantiGuncelle):
    for b in baglantilar:
        if b["id"] == bid:
            if istek.ad        is not None: b["ad"]        = istek.ad
            if istek.api_key   is not None and istek.api_key: b["api_key"]   = istek.api_key
            if istek.aktif     is not None: b["aktif"]     = istek.aktif
            if istek.model_adi is not None: b["model_adi"] = istek.model_adi
            baglantilar_kaydet()
            return {"basarili": True}
    return JSONResponse({"hata": "Bağlantı bulunamadı"}, status_code=404)

@app.delete("/baglantilar/{bid}")
async def baglanti_sil(bid: str):
    global baglantilar
    n = len(baglantilar)
    baglantilar = [b for b in baglantilar if b["id"] != bid]
    if len(baglantilar) == n:
        return JSONResponse({"hata": "Bulunamadı"}, status_code=404)
    baglantilar_kaydet()
    return {"basarili": True}

@app.post("/baglantilar/{bid}/test")
async def baglanti_test(bid: str):
    b = next((x for x in baglantilar if x["id"] == bid), None)
    if not b:
        return JSONResponse({"hata": "Bulunamadı"}, status_code=404)
    loop = asyncio.get_event_loop()
    sonuc = await loop.run_in_executor(None, lambda: _test_et(b))
    b["test_durumu"]    = sonuc["durum"]
    b["test_mesaji"]    = sonuc["mesaj"]
    b["son_test_zamani"] = datetime.datetime.now().isoformat()
    baglantilar_kaydet()
    return sonuc

def _test_et(b: dict) -> dict:
    tip, key = b.get("tip",""), b.get("api_key","")
    if not key and tip != "surge":
        return {"durum": "basarisiz", "mesaj": "API key boş"}
    try:
        if tip == "gemini":   return _test_gemini(key, b.get("model_adi") or "gemini-1.5-flash")
        if tip == "groq":     return _test_groq(key)
        if tip == "openai":   return _test_openai(key)
        if tip == "surge":    return _test_surge(key)
        if tip == "netlify":  return _test_netlify(key)
        if tip == "github":   return _test_github(key)
        return {"durum": "basarisiz", "mesaj": f"Bilinmeyen tip: {tip}"}
    except urllib.error.HTTPError as e:
        return {"durum": "basarisiz", "mesaj": f"HTTP {e.code}: Geçersiz key veya izin yok"}
    except urllib.error.URLError as e:
        return {"durum": "basarisiz", "mesaj": f"Bağlantı hatası: {e.reason}"}
    except Exception as e:
        return {"durum": "basarisiz", "mesaj": str(e)}

def _test_gemini(key: str, model: str) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        r = m.generate_content("Say OK")
        if r.text:
            return {"durum": "basarili", "mesaj": f"✅ Gemini bağlantısı başarılı ({model})"}
    return {"durum": "basarisiz", "mesaj": "Yanıt alınamadı"}

def _test_groq(key: str) -> dict:
    req = urllib.request.Request("https://api.groq.com/openai/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    n = len(data.get("data", []))
    return {"durum": "basarili", "mesaj": f"✅ Groq bağlantısı başarılı ({n} model)"}

def _test_openai(key: str) -> dict:
    req = urllib.request.Request("https://api.openai.com/v1/models",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        json.loads(r.read())
    return {"durum": "basarili", "mesaj": "✅ OpenAI bağlantısı başarılı"}

def _test_surge(key: str) -> dict:
    import subprocess
    try:
        r = subprocess.run(["npx", "surge", "--help"], capture_output=True, timeout=15, text=True)
        out = (r.stdout + r.stderr).lower()
        if "surge" in out or "domain" in out:
            return {"durum": "basarili", "mesaj": "✅ Surge.sh hazır (npx surge mevcut)"}
    except Exception:
        pass
    return {"durum": "basarisiz", "mesaj": "Surge bulunamadı (Node.js/npm kurulu mu?)"}

def _test_netlify(key: str) -> dict:
    req = urllib.request.Request("https://api.netlify.com/api/v1/user",
                                 headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return {"durum": "basarili", "mesaj": f"✅ Netlify başarılı ({data.get('email','')})"}

def _test_github(key: str) -> dict:
    req = urllib.request.Request("https://api.github.com/user",
                                 headers={"Authorization": f"token {key}", "User-Agent": "OtonomAjan/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    return {"durum": "basarili", "mesaj": f"✅ GitHub başarılı (@{data.get('login','')})"}

# ── Sistem Durumu (Akış Haritası için) ─────────────────────
@app.get("/sistem-durumu")
async def sistem_durumu():
    ai_bag  = next(({"tip": b['tip'], "ad": b['ad'], "durum": b.get('test_durumu','test_edilmedi')}
                    for b in baglantilar if b.get('aktif') and b.get('tip') in ['gemini','groq','openai']), None)
    dep_bag = next(({"tip": b['tip'], "ad": b['ad'], "durum": b.get('test_durumu','test_edilmedi')}
                    for b in baglantilar if b.get('aktif') and b.get('tip') in ['surge','netlify']), None)
    return {
        "pipeline_calisiyor": len(job_queues) > 0,
        "toplam_is":          len(is_gecmisi),
        "ai":                 ai_bag,
        "deployment":         dep_bag,
    }

# ── İş Geçmişi ────────────────────────────────────────────
@app.get("/gecmis")
async def is_gecmisini_getir():
    return {"gecmis": list(reversed(is_gecmisi))}

@app.get("/gecmis/{job_id}")
async def is_detayi(job_id: str):
    for is_ in is_gecmisi:
        if is_["job_id"] == job_id:
            return {"is": is_, "dosya_isimleri": list(job_dosyalari.get(job_id, {}).keys())}
    return JSONResponse({"hata": "Job bulunamadı"}, status_code=404)

@app.get("/dosya/{job_id}/{dosya_adi}")
async def dosya_icerik(job_id: str, dosya_adi: str):
    d = job_dosyalari.get(job_id, {})
    if dosya_adi not in d:
        return JSONResponse({"hata": "Dosya bulunamadı"}, status_code=404)
    return {"icerik": d[dosya_adi], "dosya_adi": dosya_adi}

# ── Pipeline Başlat ────────────────────────────────────────
@app.post("/calistir")
async def pipeline_baslat(istek: PipelineIstegi):
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    job_queues[job_id] = queue
    is_gecmisi.append({"job_id": job_id, "zaman": datetime.datetime.now().isoformat(),
                        "musteri_istegi": istek.musteri_istegi[:120],
                        "model_adi": istek.model_adi or "gemini-1.5-flash",
                        "durum": "calisiyor", "canli_url": ""})
    if len(is_gecmisi) > MAX_GECMIS:
        is_gecmisi.pop(0)
    asyncio.create_task(pipeline_calistir(job_id, istek))
    return {"job_id": job_id}

# ── SSE Stream ────────────────────────────────────────────
@app.get("/durum/{job_id}")
async def durum_stream(job_id: str):
    async def gen():
        if job_id not in job_queues:
            yield sse_mesaj({"tip": "hata", "mesaj": "Geçersiz job ID"}); return
        q = job_queues[job_id]
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=90.0)
                yield sse_mesaj(msg)
                if msg.get("tip") in ("tamamlandi", "hata"):
                    job_queues.pop(job_id, None); break
            except asyncio.TimeoutError:
                yield sse_mesaj({"tip": "ping"})
    return StreamingResponse(gen(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no","Connection":"keep-alive"})

# ── Groq Üretim ───────────────────────────────────────────
def _groq_uret(api_key: str, model: str, prompt: str) -> tuple[str, dict]:
    data = json.dumps({"model": model or "llama-3.3-70b-versatile",
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 8000, "temperature": 0.7}).encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                 data=data, headers={"Authorization": f"Bearer {api_key}",
                                                      "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read())
    text  = result['choices'][0]['message']['content']
    usage = result.get('usage', {})
    return text, {"girdi": usage.get('prompt_tokens',0),
                  "cikti":  usage.get('completion_tokens',0),
                  "toplam": usage.get('total_tokens',0)}

# ── Ana Pipeline ──────────────────────────────────────────
async def pipeline_calistir(job_id: str, istek: PipelineIstegi):
    q = job_queues[job_id]

    def guncelle(**kw):
        for is_ in is_gecmisi:
            if is_["job_id"] == job_id:
                is_.update(kw); break

    async def bildir(tip, mesaj, detay="", ekstra=None):
        veri = {"tip": tip, "mesaj": mesaj, "detay": detay}
        if ekstra: veri.update(ekstra)
        await q.put(veri)

    try:
        # ADIM 1
        await bildir("adim","🧠 Adım 1/4: İstek analiz ediliyor...","Müşteri isteği ve kurallar değerlendiriliyor.",{"adim_no":1})
        bag_tip, bag_key, bag_model = aktif_ai_baglanti_bul()
        if not bag_key:
            await bildir("hata","❌ Aktif AI bağlantısı bulunamadı!","Bağlantılar sekmesinden Gemini veya Groq API key ekleyin.")
            guncelle(durum="hata"); return
        await asyncio.sleep(0.3)

        # ADIM 2
        model_goster = bag_model or ("llama-3.3-70b-versatile" if bag_tip=="groq" else "gemini-1.5-flash")
        await bildir("adim",f"✍️  Adım 2/4: {bag_tip.upper()} ({model_goster}) modeline istek gönderiliyor...","Yapay zeka kodları üretiyor...",{"adim_no":2})

        prompt = f"""Sen kıdemli bir Otonom Yazılım Geliştirici ve DevOps Ajanısın.
MÜŞTERİ İSTEĞİ: {istek.musteri_istegi}
KURALLAR: {istek.kurallar or 'Sadece HTML, CSS ve Vanilla JavaScript kullan. Ekstra kütüphane ekleme.'}
TALİMATLAR:
1. Adım adım düşün. Sadece belirtilen teknolojileri kullan.
2. Her dosya için eksiksiz, çalışır kod yaz. KESINLIKLE yer tutucu kullanma.
3. Her dosyayı şu formatta üret:
index.html
```html
[TAM HTML KODU]
```
style.css
```css
[TAM CSS KODU]
```
app.js
```javascript
[TAM JAVASCRIPT KODU]
```"""

        loop = asyncio.get_event_loop()
        ai_metni, token_bilgisi = "", {"girdi":0,"cikti":0,"toplam":0}

        if bag_tip == "groq":
            ai_metni, token_bilgisi = await loop.run_in_executor(
                None, lambda: _groq_uret(bag_key, model_goster, prompt))
        else:  # gemini / openai
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                genai.configure(api_key=bag_key)
                m_obj = genai.GenerativeModel(model_goster)
                yanit = await loop.run_in_executor(None, lambda: m_obj.generate_content(prompt))
                ai_metni = yanit.text
                if hasattr(yanit,"usage_metadata") and yanit.usage_metadata:
                    um = yanit.usage_metadata
                    token_bilgisi = {
                        "girdi":  getattr(um,"prompt_token_count",0) or 0,
                        "cikti":  getattr(um,"candidates_token_count",0) or 0,
                        "toplam": getattr(um,"total_token_count",0) or 0,
                    }

        await bildir("token","📊 Token kullanımı","",{"token":token_bilgisi})
        await bildir("log",f"✅ {bag_tip.upper()} yanıt verdi ({len(ai_metni)} karakter).",ai_metni[:300]+"...")

        # ADIM 3
        await bildir("adim","📂 Adım 3/4: Dosyalar oluşturuluyor...","Kod dosyalara yazılıyor.",{"adim_no":3})
        desen = r"([a-zA-Z0-9_\-\.]+)\s*```[a-zA-Z0-9]*\n(.*?)```"
        eslesme = re.findall(desen, ai_metni, re.DOTALL)
        hedef = "Musteri_Projesi"; os.makedirs(hedef, exist_ok=True)
        dosyalar = []; job_dosyalari[job_id] = {}
        for ad, kod in eslesme:
            ad = ad.strip(); kod = kod.strip()
            with open(os.path.join(hedef, ad), "w", encoding="utf-8") as f: f.write(kod)
            dosyalar.append(ad); job_dosyalari[job_id][ad] = kod
            await bildir("dosya", f"✅ {ad} kaydedildi.", os.path.join(hedef, ad))
        if not dosyalar:
            await bildir("hata","❌ Dosya oluşturulamadı.","Regex eşleşmedi — AI formatı farklı olabilir.")
            guncelle(durum="hata"); return

        # ADIM 4
        await bildir("adim","🌐 Adım 4/4: Surge ile yayına alınıyor...","Proje internete yükleniyor.",{"adim_no":4})
        surge_token = istek.surge_token or ""
        if not surge_token:
            for b in baglantilar:
                if b.get('aktif') and b.get('tip')=='surge' and b.get('api_key'):
                    surge_token = b['api_key']; break
        proje = istek.proje_adi or ""
        if proje and not proje.endswith(".surge.sh"): proje += ".surge.sh"
        elif not proje: proje = f"otonom-proje-{job_id[:8]}.surge.sh"
        token_flag = f" --token {surge_token}" if surge_token else " --token bypass"
        cmd = f"npx surge ./{hedef} {proje}{token_flag}"
        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        cikti = out.decode("utf-8","replace") + err.decode("utf-8","replace")
        url = f"https://{proje}"
        if "Success" in cikti or "surge.sh" in cikti:
            guncelle(durum="tamamlandi", canli_url=url)
            await bildir("tamamlandi","🚀 Proje canlıya alındı!",url,{"dosyalar":dosyalar})
        else:
            guncelle(durum="tamamlandi", canli_url="")
            await bildir("tamamlandi","✅ Dosyalar hazır! Surge giriş gerektiriyor.",
                         f"Terminal'de çalıştırın:\nnpx surge ./{hedef} {proje}\nOluşturulan: {', '.join(dosyalar)}",
                         {"dosyalar":dosyalar})
    except Exception as e:
        guncelle(durum="hata")
        await q.put({"tip":"hata","mesaj":f"❌ Pipeline hatası: {e}","detay":str(e)})

# ── Eski Endpoint ─────────────────────────────────────────
@app.post("/dosyalari-olustur")
async def dosyalari_olustur(veri: GelenVeri):
    desen = r"([a-zA-Z0-9_\-\.]+)\s*```[a-zA-Z0-9]*\n(.*?)```"
    eslesme = re.findall(desen, veri.ai_metni, re.DOTALL)
    hedef = "Musteri_Projesi"; os.makedirs(hedef, exist_ok=True)
    olusturulan = []
    for ad, kod in eslesme:
        ad = ad.strip()
        with open(os.path.join(hedef, ad), "w", encoding="utf-8") as f: f.write(kod.strip())
        olusturulan.append(ad)
    if not olusturulan:
        return {"mesaj": "Hata: format uyuşmadı."}
    return {"mesaj": "Kaydedildi!", "kaydedilen_dosyalar": olusturulan}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
