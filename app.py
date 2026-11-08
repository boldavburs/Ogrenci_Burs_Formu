import json
import base64
import uuid
import math
from datetime import date, datetime
from io import BytesIO

import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ============================================================================
# AYARLAR
# ============================================================================
# Kısa Form'daki "Belgeler" bölümünde istenen belgeler. Fotoğraf hariç hepsi
# sadece PDF kabul eder. Sadece bu listeyi değiştirerek belge setini
# güncelleyebilirsiniz, başka yer değişmez.
REQUIRED_DOCUMENTS = [
    {"key": "vukuatli_nufus_kaydi", "label": "Tipi: Nüfus Aile Vukuatlı Kayıt Örneği", "tur": ["pdf"]},
    {"key": "anne_baba_gelir_belgesi", "label": "Baba ve Anne Maaş Gelir Belgesi", "tur": ["pdf"]},
    {"key": "ogrenci_kimlik_on", "label": "Öğrenci Nüfus Cüzdanı Kimlik Belgesi (Ön Yüz)", "tur": ["pdf","jpg","jpeg","png"]},
    {"key": "ogrenci_kimlik_arka", "label": "Öğrenci Nüfus Cüzdanı Kimlik Belgesi (Arka Yüz)", "tur": ["pdf","jpg","jpeg","png"]},
    {"key": "ikametgah_belgesi", "label": "Aile İkametgah Belgesi", "tur": ["pdf"]},
    {"key": "adli_sicil_belgesi", "label": "Adli Sicil Kayıt Belgesi", "tur": ["pdf"]},
    {"key": "lise_diploma_belgesi", "label": "Lise Öğrenci Diploma Belgesi ve Notu", "tur": ["pdf"]},
    {"key": "yks_yerlesme_belgesi", "label": "YKS Yerleşme Belgesi", "tur": ["pdf"]},
    {"key": "universite_kayit_belgesi", "label": "Üniversite Kayıt Aktif Öğrenci Belgesi", "tur": ["pdf"]},
    {"key": "transkript", "label": "Transkript (ara sınıflar için)", "tur": ["pdf"], "zorunlu": False},
    {"key": "banka_iban", "label": "Öğrenci Banka ve İban Numarası", "tur": ["pdf","jpg","jpeg","png"]},
    {"key": "vesikalik_fotograf", "label": "1 Adet Vesikalık Fotoğraf", "tur": ["jpg", "jpeg", "png"]},
]

MESLEK_SECENEKLERI = [
    "Memur", "İşçi (Özel Sektör)", "Esnaf / Küçük İşletme Sahibi", "Çiftçi / Hayvancılık",
    "Serbest Meslek (Avukat, Doktor, Mühendis vb.)", "Şoför", "Emekli",
    "Ev Hanımı", "İşsiz / Çalışmıyor", "Vefat Etti", "Diğer",
]

TURKCE_AYLAR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

# Nüfusa Kayıtlı Olduğu Yer alanı için: Bol-Dav yalnızca Bolvadinlilere burs verdiğinden
# il/ilçe serbest seçimi yerine sabit "Afyonkarahisar - Bolvadin" + Merkez/köy listesi kullanılır.
BOLVADIN_IL_ILCE_SABIT = "Afyonkarahisar - Bolvadin"
BOLVADIN_YERLESIM_YERLERI = [
    "Merkez", "Büyükkarabağ", "Derekarabağ", "Dipevler", "Dişli", "Güney", "Hamidiye",
    "Karayokuş", "Kemerkaya", "Kurucaova", "Kutlu", "Nusratlı", "Ortakarabağ",
    "Özburun", "Taşağıl", "Taşlıdere", "Yürükkaracaören",
]

# "Belge Gönderme" (3. form tipi) için istenen belgeler.
BELGE_FORM_DOKUMANLARI = [
    {"key": "belge_transkript", "label": "Sınıf veya Dönem Transkript", "tur": ["pdf"]},
    {"key": "belge_yeni_kayit", "label": "Sınıf veya Dönem Yeni Kayıt Belgesi", "tur": ["pdf"]},
    {"key": "belge_mezuniyet", "label": "Mezuniyet Belgesi", "tur": ["pdf"]},
    {"key": "belge_saglik_raporu", "label": "Sağlık veya Diğer Raporlar (Yalnızca Kayıtlarını Donduran Öğrenciler İçindir)", "tur": ["pdf"]},
    {"key": "belge_katilim_sertifika", "label": "Sosyal Sorumluluk Görevi Katılım Belgesi veya Sertifikası", "tur": ["pdf", "csv", "png"]},
]

# Form Tipi kodları ("Tam"/"Kisa"/"Belge" — Donemler sayfasında saklanan iç kodlar)
# ile kullanıcıya gösterilen isimler arasındaki eşleştirme. İsim değiştirmek
# isterseniz SADECE bu sözlüğü güncellemeniz yeterli, başka yer değişmez.
FORM_TIPI_GORUNEN = {
    "Tam": "Burs Ön Değerlendirme Formu",
    "Kisa": "Burs Başvuru ve Taahhüt Formu",
    "Belge": "Bursiyer Öğrenci Akademik Durum Güncelleme Formu",
}
FORM_TIPI_KOD = {v: k for k, v in FORM_TIPI_GORUNEN.items()}

try:
    st.set_page_config(page_title="Öğrenci Başvuru Formu", page_icon="logo.png", layout="wide")
except Exception:
    st.set_page_config(page_title="Öğrenci Başvuru Formu", page_icon="📋", layout="wide")

# Önceki çalıştırmada başarılı bir gönderim olduysa, formu HİÇBİR ALAN HENÜZ
# OLUŞTURULMADAN (script'in en başında) temizliyoruz. Bunu dialog içinde/daha
# sonra yapmak Streamlit'in "bu çalıştırmada zaten oluşturulmuş widget'ın
# durumunu değiştirememe" kısıtına takılıyordu — bu yüzden temizleme mutlaka
# BİR SONRAKİ çalıştırmanın en başında yapılmalı.
if st.session_state.get("_form_temizlensin"):
    _yeni_dosya_epoch = uuid.uuid4().hex[:8]
    st.session_state.clear()
    st.session_state["submit_success"] = True
    st.session_state["dosya_epoch"] = _yeni_dosya_epoch

# Sayfa kaynağında ("İncele" / "Sayfa Kaynağını Görüntüle") görünecek imza.
# Sadece bu metni değiştirerek imzayı güncelleyebilirsiniz.
st.markdown(
    """
    <!-- =======================================================================================================================
                            MUSTAFA SABRİ DOĞRUYOL - msabridogruyol.com - info@msabridogruyol.com
       ======================================================================================================================= -->
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# GİRİŞ ALANLARI RENK AYARI (metin kutusu / seçim kutusu arka planı ve yazı rengi)
# ============================================================================
# Sadece bu 2 değeri değiştirerek TÜM metin kutusu, seçim kutusu (selectbox/
# selectbox içindeki "İl seçiniz" gibi yer tutucu yazılar dahil) ve tarih
# seçim kutularının arka plan / yazı rengini tek yerden kontrol edebilirsiniz.
GIRIS_ALANI_ARKA_PLAN_RENGI = "#FFFFFF"  # kutuların arka plan rengi
GIRIS_ALANI_YAZI_RENGI = "#000000"       # kutu içindeki yazı ve yer tutucu rengi (normal siyah)

st.markdown(
    f"""
    <style>
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"],
    input, textarea {{
        background-color: {GIRIS_ALANI_ARKA_PLAN_RENGI} !important;
        color: {GIRIS_ALANI_YAZI_RENGI} !important;
    }}
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] [class*="placeholder"],
    input::placeholder, textarea::placeholder {{
        color: {GIRIS_ALANI_YAZI_RENGI} !important;
        -webkit-text-fill-color: {GIRIS_ALANI_YAZI_RENGI} !important;
        opacity: 1 !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner=False)
def _il_ilce_yukle():
    with open("data/il_ilce.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _universiteler_yukle():
    with open("data/universiteler.json", "r", encoding="utf-8") as f:
        return json.load(f)


IL_ILCE = _il_ilce_yukle()
IL_LISTESI = list(IL_ILCE.keys())

UNIVERSITE_LISTESI = _universiteler_yukle()
UNIVERSITE_LISTESI_ARAMA = UNIVERSITE_LISTESI + ["Listede Yok / Diğer"]


def _call_apps_script(payload: dict) -> dict:
    """Google Apps Script Web App'e POST isteği gönderir."""
    url = st.secrets["APPS_SCRIPT_URL"]
    payload["secret"] = st.secrets["APPS_SCRIPT_SECRET"]
    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _update_review_status(tc_no, value: str) -> bool:
    payload = {
        "action": "update_review",
        "tc_no": str(tc_no),
        "value": value,
        "secret": st.secrets["APPS_SCRIPT_SECRET"],
    }
    resp = requests.post(st.secrets["APPS_SCRIPT_URL"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json().get("ok", False)


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_all_rows() -> dict:
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "list_rows", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=20, show_spinner=False)
def _fetch_admin_dashboard() -> dict:
    """Yönetici panelinin ihtiyaç duyduğu başvurular + dönemler + soruları
    TEK istekte getirir — ayrı ayrı 3 çağrı yerine tek bir Google Apps Script
    gecikmesi ödenir, panel belirgin şekilde hızlanır."""
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_admin_dashboard", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_settings() -> dict:
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_settings", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=1200, show_spinner=False)
def _fetch_aktif_donemler() -> dict:
    """Şu an Aktif olan TÜM dönemleri getirir (birden fazla olabilir)."""
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_aktif_donemler", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_donemler() -> dict:
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_donemler", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _sync_donemler(donemler: list) -> dict:
    payload = {
        "action": "sync_donemler",
        "donemler": donemler,
        "secret": st.secrets["APPS_SCRIPT_SECRET"],
    }
    resp = requests.post(st.secrets["APPS_SCRIPT_URL"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _delete_row(tc_no, donem) -> bool:
    payload = {
        "action": "delete_row",
        "tc_no": str(tc_no),
        "donem": str(donem),
        "secret": st.secrets["APPS_SCRIPT_SECRET"],
    }
    resp = requests.post(st.secrets["APPS_SCRIPT_URL"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json().get("ok", False)


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_sorular() -> dict:
    """Yönetici paneli için TÜM ek soruları (aktif+pasif) getirir."""
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_sorular", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=180, show_spinner=False)
def _fetch_sorular_aktif() -> dict:
    """Form için SADECE aktif ek soruları getirir (önbelleğe alınır)."""
    url = st.secrets["APPS_SCRIPT_URL"]
    resp = requests.get(
        url,
        params={"action": "get_sorular_aktif", "secret": st.secrets["APPS_SCRIPT_SECRET"]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _sync_sorular(sorular: list) -> dict:
    payload = {
        "action": "sync_sorular",
        "sorular": sorular,
        "secret": st.secrets["APPS_SCRIPT_SECRET"],
    }
    resp = requests.post(st.secrets["APPS_SCRIPT_URL"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _file_to_b64(uploaded_file) -> dict:
    data = uploaded_file.getvalue()
    return {
        "filename": uploaded_file.name,
        "mimetype": uploaded_file.type or "application/octet-stream",
        "data_b64": base64.b64encode(data).decode("utf-8"),
    }


def _il_ilce_secimi(il_label: str, ilce_label: str, prefix: str):
    """İl seçilince ilçe listesini otomatik filtreler (canlı güncelleme için form dışında kullanılmalı)."""
    il = st.selectbox(il_label, IL_LISTESI, index=None, placeholder="İl seçiniz", key=f"{prefix}_il")
    ilceler = IL_ILCE.get(il, []) if il else []
    ilce = st.selectbox(
        ilce_label, ilceler, index=None,
        placeholder="Önce il seçiniz" if not il else "İlçe seçiniz",
        disabled=not il, key=f"{prefix}_ilce",
    )
    return il, ilce


def _meslek_secimi(label: str, prefix: str):
    meslek = st.selectbox(label, MESLEK_SECENEKLERI, index=None, placeholder="Seçiniz", key=f"{prefix}_meslek")
    meslek_diger = ""
    if meslek == "Diğer":
        meslek_diger = st.text_input("Mesleği yazın", key=f"{prefix}_meslek_diger")
    return meslek_diger.strip() if meslek == "Diğer" else meslek


def _iban_formatla():
    """IBAN girdisini her tuş vuruşunda "TR00 0000 0000 0000 0000 0000 00" şeklinde
    4'erli bloklar hâlinde normalize eder. "TR" önekini korur, ondan sonrasını sadece
    rakamla sınırlar ve toplamda TR + 24 haneyi (26 karakter) aşmasına izin vermez."""
    ham = (st.session_state.get("iban_girdi", "") or "").upper()
    if ham.startswith("TR"):
        rakam_kismi = "".join(ch for ch in ham[2:] if ch.isdigit())
    else:
        rakam_kismi = "".join(ch for ch in ham if ch.isdigit())
    rakam_kismi = rakam_kismi[:24]
    tam = "TR" + rakam_kismi
    gruplar = [tam[i:i + 4] for i in range(0, len(tam), 4)]
    st.session_state["iban_girdi"] = " ".join(gruplar)


@st.cache_data(show_spinner=False)
def _grafikleri_olustur(df: pd.DataFrame, donem_sayilari_df=None):
    """Tüm Genel Bakış grafiklerini bir kez hesaplayıp önbelleğe alır.
    Veri değişmediği sürece (15 sn önbellek süresi içinde) tekrar tıklamalarda
    Plotly grafikleri sıfırdan yeniden hesaplanmaz — panelin kasmasının ana
    sebeplerinden biri buydu."""
    grafikler = {}

    if "Cinsiyet" in df.columns:
        fig = px.pie(df, names="Cinsiyet", title="Cinsiyet Dağılımı", hole=0.5,
                     color_discrete_sequence=["#F5821F", "#2C2C2A"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0))
        grafikler["cinsiyet"] = fig

    if "Sınıfı" in df.columns:
        fig = px.bar(df["Sınıfı"].value_counts().reset_index(), x="Sınıfı", y="count",
                     title="Sınıf Dağılımı", color_discrete_sequence=["#F5821F"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="")
        grafikler["sinif"] = fig

    if "Bölüm" in df.columns:
        top_bolum = df["Bölüm"].value_counts().nlargest(10).reset_index()
        fig = px.bar(top_bolum, x="count", y="Bölüm", orientation="h",
                     title="En Çok Başvurulan 10 Bölüm", color_discrete_sequence=["#F5821F"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="",
                           yaxis=dict(autorange="reversed"))
        grafikler["bolum"] = fig

    if "İkamet İl" in df.columns:
        top_il = df["İkamet İl"].value_counts().nlargest(10).reset_index()
        fig = px.bar(top_il, x="count", y="İkamet İl", orientation="h",
                     title="En Çok Başvuru Yapılan 10 İl", color_discrete_sequence=["#2C2C2A"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="",
                           yaxis=dict(autorange="reversed"))
        grafikler["il"] = fig

    if "Ebeveyn Medeni Durumu" in df.columns:
        fig = px.bar(df["Ebeveyn Medeni Durumu"].value_counts().reset_index(),
                     x="Ebeveyn Medeni Durumu", y="count", title="Ebeveyn Medeni Durumu Dağılımı",
                     color_discrete_sequence=["#F5821F"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="")
        grafikler["medeni_durum"] = fig

    if "Babasının Mesleği" in df.columns:
        fig = px.bar(df["Babasının Mesleği"].value_counts().nlargest(8).reset_index(),
                     x="count", y="Babasının Mesleği", orientation="h",
                     title="Babasının Mesleği Dağılımı", color_discrete_sequence=["#2C2C2A"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="",
                           yaxis=dict(autorange="reversed"))
        grafikler["meslek"] = fig

    gerekli_kolonlar = {"Cinsiyet", "Babanın Aylık Geliri (TL)", "Annenin Aylık Geliri (TL)",
                        "Okumakta Olan Kardeş Sayısı"}
    if gerekli_kolonlar.issubset(df.columns) and df["Cinsiyet"].nunique() > 0:
        eksenler = ["Ort. Baba Geliri", "Ort. Anne Geliri", "Ort. Kardeş Sayısı", "Başvuru Oranı (%)"]
        fig = go.Figure()
        renkler = {"Kadın": "#F5821F", "Erkek": "#2C2C2A"}
        for cinsiyet_grubu, renk in renkler.items():
            alt_df = df[df["Cinsiyet"] == cinsiyet_grubu]
            if alt_df.empty:
                continue
            degerler = [
                alt_df["Babanın Aylık Geliri (TL)"].fillna(0).mean(),
                alt_df["Annenin Aylık Geliri (TL)"].fillna(0).mean(),
                alt_df["Okumakta Olan Kardeş Sayısı"].fillna(0).mean() * 5000,
                (len(alt_df) / len(df)) * 100 * 200,
            ]
            fig.add_trace(go.Scatterpolar(
                r=degerler, theta=eksenler, fill="toself", name=cinsiyet_grubu, line_color=renk,
            ))
        fig.update_layout(
            title="Cinsiyete Göre Profil Karşılaştırması (Örümcek Grafik)",
            polar=dict(radialaxis=dict(visible=False)),
            margin=dict(t=40, b=0, l=40, r=40), showlegend=True,
        )
        grafikler["radar"] = fig

    if "Babanın Aylık Geliri (TL)" in df.columns and "Annenin Aylık Geliri (TL)" in df.columns:
        toplam_gelir = df["Babanın Aylık Geliri (TL)"].fillna(0) + df["Annenin Aylık Geliri (TL)"].fillna(0)
        fig = px.histogram(toplam_gelir, nbins=15, title="Aile Toplam Gelir Dağılımı",
                           color_discrete_sequence=["#F5821F"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="Toplam Gelir (TL)",
                           yaxis_title="Başvuru Sayısı", showlegend=False)
        grafikler["gelir_histogram"] = fig

    if donem_sayilari_df is not None and len(donem_sayilari_df) > 1:
        fig = px.bar(donem_sayilari_df, x="Dönem", y="count", title="Dönemlere Göre Toplam Başvuru Sayısı",
                     color_discrete_sequence=["#F5821F"])
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0), xaxis_title="", yaxis_title="")
        grafikler["donem_karsilastirma"] = fig

    return grafikler


def _turkce_tarih_secimi(label: str, prefix: str, varsayilan: date, min_yil: int, max_yil: int):
    """Takvim yerine Gün/Ay/Yıl seçim kutuları — ay isimleri Türkçe, tam kontrol bizde."""
    st.markdown(f"<p style='font-size:14px; color:#31333F; margin-bottom:2px;'>{label}</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        gun = st.selectbox(
            "Gün", list(range(1, 32)), index=varsayilan.day - 1,
            key=f"{prefix}_gun", label_visibility="collapsed",
        )
    with c2:
        ay = st.selectbox(
            "Ay", TURKCE_AYLAR, index=varsayilan.month - 1,
            key=f"{prefix}_ay", label_visibility="collapsed",
        )
    with c3:
        yil_listesi = list(range(max_yil, min_yil - 1, -1))
        yil = st.selectbox(
            "Yıl", yil_listesi, index=yil_listesi.index(varsayilan.year),
            key=f"{prefix}_yil", label_visibility="collapsed",
        )
    ay_no = TURKCE_AYLAR.index(ay) + 1
    try:
        return date(yil, ay_no, gun)
    except ValueError:
        return None  # örn. 30 Şubat gibi geçersiz kombinasyon


def _logo_base64():
    try:
        with open("logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _basari_animasyonu():
    """Başvuru/gönderim başarılı olduğunda balon yerine logo ile gösterilen animasyon.
    Ekranın tam ortasında sabit (fixed) bir katman olarak belirir: dönen parıltı
    halkası + büyük logo + etrafa saçılan konfeti noktaları, birkaç saniye sonra
    otomatik kaybolur. Her çağrıda benzersiz bir kimlik kullanılır ki tarayıcı
    animasyonu 'içerik değişmedi' diyerek atlamasın."""
    logo_b64 = _logo_base64()
    if not logo_b64:
        st.balloons()  # logo bulunamazsa yedek olarak Streamlit'in kendi efekti
        return

    benzersiz_id = f"basari_{uuid.uuid4().hex[:8]}"

    # Logonun etrafına saçılan konfeti noktalarını üret
    KONFETI_RENKLERI = ["#F5821F", "#2C2C2A", "#FFFFFF", "#F5821F", "#D6272A"]
    konfeti_sayisi = 18
    konfeti_html_parcalari = []
    konfeti_css_parcalari = []
    for i in range(konfeti_sayisi):
        aci = (360 / konfeti_sayisi) * i
        mesafe = 160 + (i % 3) * 30
        dx = round(math.cos(math.radians(aci)) * mesafe)
        dy = round(math.sin(math.radians(aci)) * mesafe)
        renk = KONFETI_RENKLERI[i % len(KONFETI_RENKLERI)]
        boyut = 10 if i % 2 == 0 else 7
        gecikme = 0.15 + (i % 5) * 0.05
        konfeti_css_parcalari.append(f"""
        @keyframes {benzersiz_id}_k{i} {{
            0% {{ transform: translate(0, 0) scale(0) rotate(0deg); opacity: 1; }}
            70% {{ opacity: 1; }}
            100% {{ transform: translate({dx}px, {dy}px) scale(1) rotate(220deg); opacity: 0; }}
        }}
        #{benzersiz_id}_k{i} {{
            position: absolute; top: 50%; left: 50%;
            width: {boyut}px; height: {boyut}px; margin: -{boyut//2}px 0 0 -{boyut//2}px;
            background: {renk}; border-radius: 3px;
            animation: {benzersiz_id}_k{i} 1.4s cubic-bezier(0.2, 0.7, 0.4, 1) {gecikme}s both;
        }}
        """)
        konfeti_html_parcalari.append(f'<div id="{benzersiz_id}_k{i}"></div>')

    konfeti_css = "".join(konfeti_css_parcalari)
    konfeti_html = "".join(konfeti_html_parcalari)

    st.markdown(
        f"""
        <style>
        @keyframes {benzersiz_id}_pop {{
            0%   {{ transform: scale(0) rotate(-30deg); opacity: 0; }}
            50%  {{ transform: scale(1.25) rotate(8deg); opacity: 1; }}
            70%  {{ transform: scale(0.92) rotate(-4deg); }}
            85%  {{ transform: scale(1.05) rotate(2deg); }}
            100% {{ transform: scale(1) rotate(0deg); opacity: 1; }}
        }}
        @keyframes {benzersiz_id}_glow {{
            0%, 100% {{ box-shadow: 0 0 0px 0px rgba(245,130,31,0.55); }}
            50% {{ box-shadow: 0 0 55px 20px rgba(245,130,31,0.55); }}
        }}
        @keyframes {benzersiz_id}_ringspin {{
            0% {{ transform: rotate(0deg); opacity: 0.9; }}
            100% {{ transform: rotate(360deg); opacity: 0.9; }}
        }}
        @keyframes {benzersiz_id}_shockwave {{
            0% {{ transform: scale(0.3); opacity: 0.9; border-width: 6px; }}
            100% {{ transform: scale(2.6); opacity: 0; border-width: 1px; }}
        }}
        @keyframes {benzersiz_id}_fadeout {{
            0%, 82% {{ opacity: 1; }}
            100% {{ opacity: 0; }}
        }}
        #{benzersiz_id}_kapsayici {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            display: flex; justify-content: center; align-items: center;
            z-index: 9999; pointer-events: none;
            animation: {benzersiz_id}_fadeout 4s ease-in forwards;
        }}
        #{benzersiz_id}_sahne {{
            position: relative; width: 320px; height: 320px;
            display: flex; justify-content: center; align-items: center;
        }}
        #{benzersiz_id}_shock {{
            position: absolute; width: 200px; height: 200px; border-radius: 50%;
            border: 6px solid #F5821F;
            animation: {benzersiz_id}_shockwave 1.1s ease-out 0.15s both;
        }}
        #{benzersiz_id}_ring {{
            position: absolute; width: 230px; height: 230px; border-radius: 50%;
            background: conic-gradient(from 0deg, #F5821F, #FFFFFF, #2C2C2A, #F5821F);
            animation: {benzersiz_id}_ringspin 3.5s linear infinite;
            -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 6px));
                    mask: radial-gradient(farthest-side, transparent calc(100% - 6px), #000 calc(100% - 6px));
        }}
        #{benzersiz_id}_kapsayici img {{
            position: relative; z-index: 2;
            width: 220px; height: 220px; border-radius: 50%;
            background: #FFFFFF; padding: 10px; object-fit: cover;
            animation: {benzersiz_id}_pop 0.8s cubic-bezier(0.34, 1.56, 0.64, 1),
                       {benzersiz_id}_glow 1.7s ease-in-out 0.8s 2;
        }}
        {konfeti_css}
        </style>
        <div id="{benzersiz_id}_kapsayici">
            <div id="{benzersiz_id}_sahne">
                <div id="{benzersiz_id}_shock"></div>
                <div id="{benzersiz_id}_ring"></div>
                {konfeti_html}
                <img src="data:image/png;base64,{logo_b64}" />
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ust_serit(baslik: str, alt_baslik: str, buton_metni: str = None, buton_key: str = "ust_serit_btn") -> bool:
    logo_b64 = _logo_base64()
    st.markdown(
        """
        <style>
        .st-key-ust_serit_kutu { background:#F5821F; border-radius:12px;
            padding:1.25rem 2rem; margin-bottom:1.5rem; }
        .st-key-ust_serit_kutu button { background:#FFFFFF !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    tiklandi = False
    # NOT: Sol ve sağ kenar kolonları BİLEREK eşit toplam genişlikte (3 birim) tutulur.
    # Bu sayede logo kolonu, içeriğin uzunluğundan bağımsız olarak matematiksel
    # olarak tam ortada kalır (position:absolute yerine simetrik kolon genişliği kullanıldı,
    # çünkü absolute konumlandırma bazı Streamlit sürümlerinde şeridin dışına taşabiliyor).
    with st.container(key="ust_serit_kutu"):
        col_baslik, col_logo, col_bosluk, col_buton = st.columns(
            [3, 1.4, 1.4, 1.6], vertical_alignment="center"
        )
        with col_baslik:
            st.markdown(
                f"<p style='color:#FFFFFF; font-size:24px; font-weight:600; margin:0;'>{baslik}</p>"
                f"<p style='color:#FFFFFF; font-size:14px; margin:6px 0 0; opacity:0.92;'>{alt_baslik}</p>",
                unsafe_allow_html=True,
            )
        with col_logo:
            if logo_b64:
                # LOGO_BOYUT: logo çapı (px). LOGO_DIKEY_KAYDIRMA: negatif değer yukarı,
                # pozitif değer aşağı kaydırır — sadece bu iki değeri değiştirerek ayarlayın.
                LOGO_BOYUT = 100
                LOGO_DIKEY_KAYDIRMA = "-10px"
                st.markdown(
                    f'<div style="text-align:center;">'
                    f'<img src="data:image/png;base64,{logo_b64}" '
                    f'style="height:{LOGO_BOYUT}px; width:{LOGO_BOYUT}px; border-radius:50%; '
                    f'background:#FFFFFF; padding:4px; object-fit:cover; display:inline-block; '
                    f'vertical-align:middle; position:relative; top:{LOGO_DIKEY_KAYDIRMA};" /></div>',
                    unsafe_allow_html=True,
                )
        with col_buton:
            if buton_metni:
                tiklandi = st.button(buton_metni, key=buton_key, use_container_width=True)
    return tiklandi


def _bolum_basligi(numara: str, baslik: str):
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:10px; margin:1.75rem 0 1rem;">
            <div style="width:26px; height:26px; border-radius:50%; background:#F5821F;
                        color:#FFFFFF; font-size:13px; font-weight:600; display:flex;
                        align-items:center; justify-content:center; flex-shrink:0;">{numara}</div>
            <p style="font-size:16px; font-weight:600; margin:0; color:#111111;">{baslik}</p>
        </div>
        <hr style="margin:-6px 0 1rem; border:none; border-top:1px solid #E5E5E5;">
        """,
        unsafe_allow_html=True,
    )


@st.dialog("Silme İşlemini Onaylayın")
def _silme_onay_dialogu():
    n = len(st.session_state.get("silinecek_kayitlar", set()))
    st.write(f"**{n} adet kayıt silinecektir.**")
    st.write(
        "Bu işlem sonrasında başvuru satırı tablodan kalıcı olarak silinir "
        "(Drive'daki evrak klasörü çöp kutusuna taşınır, 30 gün içinde geri alınabilir)."
    )
    st.write("**Emin misiniz?**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Evet, Sil", type="primary", use_container_width=True):
            basarili = 0
            for tc_no, donem_deger in list(st.session_state.silinecek_kayitlar):
                try:
                    if _delete_row(tc_no, donem_deger):
                        basarili += 1
                except Exception as e:
                    st.error(f"{tc_no} silinemedi: {e}")
            st.session_state.silinecek_kayitlar = set()
            st.session_state["silme_onay_bekliyor"] = False
            _fetch_all_rows.clear()
            _fetch_admin_dashboard.clear()
            st.session_state["silme_basarili_sayisi"] = basarili
            st.rerun()
    with col2:
        if st.button("Vazgeç", use_container_width=True):
            st.session_state["silme_onay_bekliyor"] = False
            st.rerun()


@st.dialog("Başvuruyu Onaylayın")
def _onay_dialogu():
    st.write("Bilgilerinizi kontrol ettiniz mi? Başvuru gönderildikten sonra düzenleyemezsiniz.")
    st.write("**Başvuruyu göndermek istediğinizden emin misiniz?**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Evet, Gönder", type="primary", use_container_width=True):
            with st.spinner("Başvurunuz gönderiliyor, lütfen bekleyin..."):
                try:
                    result = _call_apps_script(st.session_state["pending_payload"])
                    if result.get("ok"):
                        # Formu şu an (bu çalıştırma içinde, alanlar zaten çizilmişken)
                        # temizlemek yerine, bir sonraki sayfa yüklemesinin EN BAŞINDA
                        # (hiçbir alan henüz oluşturulmamışken) temizlenmesi için bayrak
                        # bırakıp yeniden çalıştırıyoruz — bu, Streamlit'in "aktif
                        # widget durumunu aynı çalıştırmada değiştirememe" kısıtını aşar.
                        st.session_state["_form_temizlensin"] = True
                        st.rerun()
                    else:
                        st.error(f"Gönderim başarısız: {result.get('error', 'Bilinmeyen hata')}")
                except Exception as e:
                    hata_metni = str(e)
                    if "googleusercontent.com/macros/echo" in hata_metni and "404" in hata_metni:
                        # Bu spesifik desen: Apps Script sunucu tarafında işlemi
                        # tamamlıyor (veri kaydediliyor) ama Google'ın cevabı geri
                        # teslim etmesinde geçici bir aksaklık oluyor. Doğruladığımız
                        # kadarıyla veri bu durumda kaydediliyor — bu yüzden korkutucu
                        # teknik hata yerine normal başarı akışı gösteriliyor.
                        st.session_state["_form_temizlensin"] = True
                        st.rerun()
                    else:
                        st.error(f"Bir hata oluştu, lütfen tekrar deneyin. Teknik detay: {e}")
    with col2:
        if st.button("Vazgeç", use_container_width=True):
            st.session_state["confirm_pending"] = False
            st.rerun()


# ============================================================================
# NAVİGASYON
# ============================================================================
if "view" not in st.session_state:
    st.session_state.view = "form"
if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False

# ============================================================================
# ÖĞRENCİ BAŞVURU FORMU
# ============================================================================
# NOT: Bu bölüm bilinçli olarak st.form KULLANMAZ. İl -> İlçe seçimlerinin
# anında (her il değiştiğinde) filtrelenebilmesi için widget'ların her
# etkileşimde yeniden çalışması (rerun) gerekir; st.form içindeki widget'lar
# sadece "gönder" butonuna basılınca güncellenir ve ilçe listesi o ana kadar
# bayat kalırdı. Bu yüzden gönderim ayrı bir st.button ile tetiklenir.
if st.session_state.view == "form":
    try:
        if "ilk_yukleme_yapildi" not in st.session_state:
            with st.spinner("Form bilgileri yükleniyor..."):
                aktif_sonuc = _fetch_aktif_donemler()
            st.session_state.ilk_yukleme_yapildi = True
        else:
            aktif_sonuc = _fetch_aktif_donemler()  # önbellekte hazırsa anında döner, gösterge yok
        aktif_donemler = aktif_sonuc.get("donemler", []) if aktif_sonuc.get("ok") else []
        aktif_bilgi_alindi = aktif_sonuc.get("ok", False)
    except Exception:
        aktif_donemler = []
        aktif_bilgi_alindi = False
        st.error("📌 Sayfa şu anda yüklenemedi. Lütfen sayfayı yenileyin (F5 veya yenile tuşu).")

    if "secili_donem_key" not in st.session_state:
        st.session_state.secili_donem_key = None

    # Daha önce seçilen (isim, form tipi) kombinasyonu artık aktif değilse
    # (yönetici pasif yaptıysa) seçimi sıfırla
    if st.session_state.secili_donem_key and not any(
        (d.get("ad"), d.get("form_tipi")) == st.session_state.secili_donem_key for d in aktif_donemler
    ):
        st.session_state.secili_donem_key = None

    secili_donem = None
    if len(aktif_donemler) == 1:
        secili_donem = aktif_donemler[0]
    elif len(aktif_donemler) > 1 and st.session_state.secili_donem_key:
        secili_donem = next(
            (d for d in aktif_donemler
             if (d.get("ad"), d.get("form_tipi")) == st.session_state.secili_donem_key),
            None,
        )

    donem_adi = secili_donem["ad"] if secili_donem else ""
    form_tipi_erken = secili_donem["form_tipi"] if secili_donem else "Tam"

    if len(aktif_donemler) > 1 and not secili_donem:
        ana_baslik = "Bol-Dav Öğrenci Burs Başvuru Sistemi"
    else:
        ana_baslik = f"Bol-Dav {FORM_TIPI_GORUNEN.get(form_tipi_erken, 'Öğrenci Burs Başvuru Formu')}"
    alt_baslik = f"Bol-Dav Bolvadinliler Dayanışma Vakfı — {donem_adi}" if donem_adi else "Bol-Dav Bolvadinliler Dayanışma Vakfı"
    if _ust_serit(ana_baslik, alt_baslik, "Yönetici Girişi", "btn_yonetici_girisi"):
        st.session_state.view = "admin"
        st.rerun()

    if not aktif_bilgi_alindi:
        st.stop()

    if len(aktif_donemler) == 0:
        st.warning("📌 Başvurular şu anda kapalıdır. Yeni dönem başvuruları açıldığında bu sayfadan duyurulacaktır.")
        st.stop()

    # -------- Birden fazla dönem/form aktifse: seçim ekranı göster --------
    if len(aktif_donemler) > 1 and not secili_donem:
        st.write("Şu anda birden fazla form aktif. Lütfen doldurmak istediğiniz formu seçin:")
        for i, d in enumerate(aktif_donemler):
            gorunen_form_adi = FORM_TIPI_GORUNEN.get(d.get("form_tipi"), "Form")
            if st.button(
                f"📋 {d.get('ad')} — {gorunen_form_adi}",
                use_container_width=True,
                key=f"secim_{i}_{d.get('ad')}",
            ):
                st.session_state.secili_donem_key = (d.get("ad"), d.get("form_tipi"))
                st.rerun()
        st.stop()

    if len(aktif_donemler) > 1 and secili_donem:
        if st.button("🔁 Başka form seç"):
            st.session_state.secili_donem_key = None
            st.rerun()

    form_tipi = form_tipi_erken
    kisa_form_mu = form_tipi == "Kisa"

    # ========================================================================
    # BELGE GÖNDERME FORMU (3. form tipi) — diğerlerinden TAMAMEN BAĞIMSIZ.
    # Kendi alanları, kendi belgeleri, kendi onayı var; T.C. Kimlik No YOKTUR
    # (bu formda toplanmıyor). Bu yüzden yönetici panelindeki "İncelendi" ve
    # "Sil" özellikleri (T.C. Kimlik No ile eşleştirme yapıyor) bu form tipinden
    # gelen satırlarda ÇALIŞMAZ — sadece görüntüleme/Excel indirme çalışır.
    # ========================================================================
    if form_tipi == "Belge":
        st.write("Lütfen aşağıdaki bilgileri eksiksiz doldurun ve istenen belgeleri ekleyin. Tüm alanlar zorunludur.")

        _bolum_basligi("1", "Öğrenci Bilgileri")
        bc1, bc2 = st.columns(2)
        with bc1:
            belge_ad_soyad = st.text_input("Öğrenci Adı Soyadı *")
            belge_universite = st.selectbox(
                "Üniversite Adı *", UNIVERSITE_LISTESI_ARAMA, index=None,
                placeholder="Üniversite adı yazarak arayın...",
            )
            belge_universite_diger = ""
            if belge_universite == "Listede Yok / Diğer":
                belge_universite_diger = st.text_input("Üniversite adını yazın *")
        with bc2:
            belge_cinsiyet = st.radio("Cinsiyet *", ["Erkek", "Kadın"], horizontal=True)
            belge_bolum = st.text_input("Bölümü *")
        gc1, gc2 = st.columns(2)
        with gc1:
            belge_sinif_donem = st.text_input(
                "Sınıf ve Dönemi *", placeholder="Örn: 3. Sınıf, 2025-2026 Güz Dönemi"
            )
        with gc2:
            belge_not_ortalamasi = st.number_input(
                "Genel Not Ortalaması (4 üzerinden) *", min_value=0.0, max_value=4.0,
                step=0.01, value=None, placeholder="Örn: 3.25",
            )

        _bolum_basligi("2", "Sosyal Sorumluluk Görevi")
        belge_sorumluluk_yerine_getirildi = st.radio(
            "Burs Başvuru formunda taahhüt ettiğiniz sosyal sorumluluk görevinizi yerine getirdiniz mi? *",
            ["Evet", "Hayır"], horizontal=True,
        )
        _sr_zorunlu = " *" if belge_sorumluluk_yerine_getirildi == "Evet" else ""
        bsc1, bsc2 = st.columns(2)
        with bsc1:
            belge_sorumluluk_kurum = st.text_input(
                f"Eğer getirdiyseniz hangi kurum/kuruluş/topluluk'da yerine getirdiniz?{_sr_zorunlu}",
                key="belge_sorumluluk_kurum_girdi",
            )
        with bsc2:
            belge_sorumluluk_gorev = st.text_input(
                f"Hangi görevi üstlendiniz?{_sr_zorunlu}", key="belge_sorumluluk_gorev_girdi",
            )

        _bolum_basligi("3", "Taranıp Gönderilecek Belgeler")
        st.caption("Tüm belgeler **PDF** formatında olmalıdır (dosya başına en fazla 10 MB).")
        belge_uploaded = {}
        BELGE_SUTUN_SAYISI = 2
        for i in range(0, len(BELGE_FORM_DOKUMANLARI), BELGE_SUTUN_SAYISI):
            satir_belgeleri = BELGE_FORM_DOKUMANLARI[i:i + BELGE_SUTUN_SAYISI]
            kolonlar = st.columns(BELGE_SUTUN_SAYISI)
            for kolon, doc in zip(kolonlar, satir_belgeleri):
                with kolon:
                    etiket = doc["label"]
                    if doc["key"] == "belge_katilim_sertifika":
                        etiket = doc["label"] + _sr_zorunlu
                    belge_uploaded[doc["key"]] = st.file_uploader(
                        etiket, type=doc.get("tur", ["pdf"]),
                        key=f"{doc['key']}_{st.session_state.get('dosya_epoch', '0')}",
                    )

        _bolum_basligi("4", "Onay")
        belge_onay = st.checkbox("Yukarıdaki bilgileri doğrularım ve belgelerin doğruluğunu onaylarım. *")

        if st.button("Belgeleri Gönder", use_container_width=True, type="primary"):
            eksikler = []
            if not belge_ad_soyad.strip():
                eksikler.append("Öğrenci Adı Soyadı")
            if not belge_universite:
                eksikler.append("Üniversite Adı")
            elif belge_universite == "Listede Yok / Diğer" and not belge_universite_diger.strip():
                eksikler.append("Üniversite Adı (listede yoksa elle yazılmalı)")
            if not belge_bolum.strip():
                eksikler.append("Bölümü")
            if not belge_sinif_donem.strip():
                eksikler.append("Sınıf ve Dönemi")
            if belge_not_ortalamasi is None:
                eksikler.append("Genel Not Ortalaması")
            # Sosyal sorumluluk görevi "Evet" ise kurum/görev/belge zorunlu hale gelir.
            if belge_sorumluluk_yerine_getirildi == "Evet":
                if not belge_sorumluluk_kurum.strip():
                    eksikler.append("Hangi kurum/kuruluş/topluluk'da yerine getirdiniz")
                if not belge_sorumluluk_gorev.strip():
                    eksikler.append("Hangi görevi üstlendiniz")
                if belge_uploaded.get("belge_katilim_sertifika") is None:
                    eksikler.append("Katılım Belgesi veya Sertifikası (Evet dediğiniz için zorunlu)")
            # Diğer belgeler isteğe bağlı — varsa yüklenir, yoksa boş geçilir.
            if not belge_onay:
                eksikler.append("Onay kutusu işaretlenmeli")

            if eksikler:
                st.error("Aşağıdaki alanları tamamlayın:\n\n- " + "\n- ".join(eksikler))
            else:
                belge_universite_final = (
                    belge_universite_diger.strip() if belge_universite == "Listede Yok / Diğer" else belge_universite
                )
                payload = {
                    "action": "submit",
                    "donem_adi": donem_adi,
                    "timestamp": datetime.now().isoformat(),
                    "fields": {
                        "Form Tipi": FORM_TIPI_GORUNEN["Belge"],
                        "Öğrenci Adı Soyadı": belge_ad_soyad,
                        "Cinsiyet": belge_cinsiyet,
                        "Üniversite Adı": belge_universite_final,
                        "Bölüm": belge_bolum,
                        "Sınıf ve Dönemi": belge_sinif_donem,
                        "Genel Not Ortalaması (4 üzerinden)": belge_not_ortalamasi,
                        "Sosyal Sorumluluk Görevini Yerine Getirdi mi": belge_sorumluluk_yerine_getirildi,
                        "Sosyal Sorumluluk - Kurum/Kuruluş/Topluluk": belge_sorumluluk_kurum,
                        "Sosyal Sorumluluk - Üstlenilen Görev": belge_sorumluluk_gorev,
                    },
                    "files": {
                        doc["key"]: _file_to_b64(belge_uploaded[doc["key"]])
                        for doc in BELGE_FORM_DOKUMANLARI
                        if belge_uploaded.get(doc["key"]) is not None
                    },
                    "folder_name": f"{belge_ad_soyad.strip()}_belge_gonderme",
                }
                st.session_state["pending_payload"] = payload
                st.session_state["confirm_pending"] = True
                st.rerun()

        if st.session_state.get("confirm_pending"):
            _onay_dialogu()

        if st.session_state.get("submit_success"):
            st.success("Başvurunuz başarıyla alındı. Lütfen tekrar gönderim yapmayınız.")
            _basari_animasyonu()
            st.session_state["submit_success"] = False

        st.stop()

    st.write("Lütfen aşağıdaki bilgileri eksiksiz doldurun ve istenen belgeleri ekleyin. Tüm alanlar zorunludur.")

    _bolum_basligi("1", "Öğrenci Bilgileri")
    c1, c2 = st.columns(2)
    with c1:
        ad_soyad = st.text_input("Öğrenci Adı Soyadı *")
        tc_no = st.text_input("T.C. Kimlik No *", max_chars=11)
    with c2:
        cinsiyet = st.radio("Cinsiyet *", ["Erkek", "Kadın"], horizontal=True)
        email = st.text_input("E-Posta Adresi (sadece gmail e-posta adreslerinizi girmelisiniz!) *")
    telefon = st.text_input("Cep Telefon Numarası *", placeholder="05xx xxx xx xx")
    dogum_tarihi = _turkce_tarih_secimi(
        "Öğrenci Doğum Tarihi *", "ogrenci_dogum_tarihi",
        varsayilan=date(2004, 1, 1), min_yil=1980, max_yil=date.today().year,
    )

    st.markdown("**Öğrenci Doğum Yeri**")
    d1, d2 = st.columns(2)
    with d1:
        dogum_il, dogum_ilce = _il_ilce_secimi("İl *", "İlçe *", "ogrenci_dogum")
    st.markdown("**Nüfusa Kayıtlı Olduğu Yer**")
    n1, n2 = st.columns(2)
    with n1:
        st.selectbox(
            "İl", [BOLVADIN_IL_ILCE_SABIT], index=0, disabled=True, key="nufus_il_sabit",
        )
        nufus_il = BOLVADIN_IL_ILCE_SABIT
    with n2:
        nufus_ilce = st.selectbox(
            "Merkez / Köy *", BOLVADIN_YERLESIM_YERLERI, index=None,
            placeholder="Seçiniz", key="nufus_koy",
        )

    # -------- Banka Bilgileri: SADECE "Kısa Form" (Burs Başvuru ve Taahhüt Formu) tipinde gösterilir --------
    banka_ismi = iban_no = None
    if kisa_form_mu:
        st.markdown("**Öğrenciye Ait Banka Bilgileri**")
        if "iban_girdi" not in st.session_state:
            st.session_state["iban_girdi"] = "TR"
        ib1, ib2 = st.columns(2)
        with ib1:
            banka_ismi = st.text_input("Banka İsmi *")
        with ib2:
            st.text_input(
                "IBAN No *", key="iban_girdi", on_change=_iban_formatla,
                max_chars=32, placeholder="TR00 0000 0000 0000 0000 0000 00",
            )
            iban_no = st.session_state["iban_girdi"]

    # -------- Aşağıdaki bölümler SADECE "Tam Anket" form tipinde gösterilir --------
    ikamet_il = ikamet_ilce = kaldigi_yer = None
    universite = universite_diger = bolum = okul_ili = None
    fakulte = sinif = lise_derece = lise_adi = None
    baba_adi = baba_telefon = baba_meslek = baba_adres = None
    baba_gelir = baba_dogum_tarihi = baba_dogum_il = baba_dogum_ilce = None
    anne_adi = anne_telefon = anne_meslek = anne_adres = None
    anne_gelir = anne_dogum_tarihi = anne_dogum_il = anne_dogum_ilce = None
    ebeveyn_durumu = None
    kardes_sayisi = kardes_okullari = sosyo_ekonomik = None
    aktif_sorular = []
    ek_cevaplar = {}

    if not kisa_form_mu:
        _bolum_basligi("2", "İkamet Bilgisi")
        c3, c4 = st.columns(2)
        with c3:
            ikamet_il, ikamet_ilce = _il_ilce_secimi("İkamet Edilen İl *", "İkamet Edilen İlçe *", "ikamet")
        with c4:
            kaldigi_yer = st.selectbox(
                "Öğrencinin Kaldığı Yer *",
                ["Aile Yanında", "Yurtta", "Kirada / Arkadaşlarıyla", "Akraba Yanında", "Diğer"],
            )

        _bolum_basligi("3", "Eğitim Bilgileri")
        c5, c6 = st.columns(2)
        with c5:
            universite = st.selectbox(
                "Üniversite Adı *", UNIVERSITE_LISTESI_ARAMA, index=None,
                placeholder="Üniversite adı yazarak arayın...",
            )
            universite_diger = ""
            if universite == "Listede Yok / Diğer":
                universite_diger = st.text_input("Üniversite adını yazın *")
            bolum = st.text_input("Bölüm *")
            okul_ili = st.selectbox("Okulun Bulunduğu İl *", IL_LISTESI, index=None, placeholder="İl seçiniz")
        with c6:
            fakulte = st.text_input("Fakülte *")
            sinif = st.selectbox("Sınıfı *", ["Hazırlık", "1", "2", "3", "4", "5", "6", "Yüksek Lisans"])
            lise_derece = st.text_input("Lise Mezuniyet Derecesi / Ortalaması *")
        lise_adi = st.text_input("Mezun Olduğu Lise ve Dengi Okul *")

        _bolum_basligi("4", "Aile Bilgileri")
        st.markdown("**Baba**")
        c7, c8 = st.columns(2)
        with c7:
            baba_adi = st.text_input("Baba Adı *")
            baba_telefon = st.text_input("Baba Telefonu *")
        with c8:
            baba_meslek = _meslek_secimi("Babasının Mesleği *", "baba")
            baba_gelir = st.number_input(
                "Babanın Aylık Gelir Durumu (TL) *", min_value=0, step=500,
                value=None, placeholder="Örn: 15000",
            )
        baba_dogum_tarihi = _turkce_tarih_secimi(
            "Baba Doğum Tarihi *", "baba_dogum_tarihi",
            varsayilan=date(1975, 1, 1), min_yil=1930, max_yil=date.today().year,
        )
        st.markdown("Baba Doğum Yeri")
        bd1, bd2 = st.columns(2)
        with bd1:
            baba_dogum_il, baba_dogum_ilce = _il_ilce_secimi("İl *", "İlçe *", "baba_dogum")
        baba_adres = st.text_area("Baba Adresi *")

        st.markdown("**Anne**")
        c9, c10 = st.columns(2)
        with c9:
            anne_adi = st.text_input("Anne Adı *")
            anne_telefon = st.text_input("Anne Telefonu *")
        with c10:
            anne_meslek = _meslek_secimi("Annenin Mesleği *", "anne")
            anne_gelir = st.number_input(
                "Annenin Aylık Gelir Durumu (TL) *", min_value=0, step=500,
                value=None, placeholder="Örn: 10000",
            )
        anne_dogum_tarihi = _turkce_tarih_secimi(
            "Anne Doğum Tarihi *", "anne_dogum_tarihi",
            varsayilan=date(1978, 1, 1), min_yil=1930, max_yil=date.today().year,
        )
        st.markdown("Anne Doğum Yeri")
        ad1, ad2 = st.columns(2)
        with ad1:
            anne_dogum_il, anne_dogum_ilce = _il_ilce_secimi("İl *", "İlçe *", "anne_dogum")
        anne_adres = st.text_area("Anne Adresi *")

        ebeveyn_durumu = st.selectbox(
            "Ebeveyn Medeni Durumu *",
            ["Evli", "Boşanmış", "Baba Vefat", "Anne Vefat", "Her İkisi Vefat"],
        )

        _bolum_basligi("5", "Sosyoekonomik Bilgiler")
        kardes_sayisi = st.number_input("Okumakta Olan Kardeş Sayısı *", min_value=0, max_value=15, step=1)
        kardes_okullari = st.text_area(
            "Kardeşlerin Okuduğu Okullar *",
            placeholder="Okuyan kardeşiniz yoksa 'Yok' yazınız",
        )
        sosyo_ekonomik = st.text_area(
            "Sosyo Ekonomik Faktörler *",
            placeholder="Aile durumunu etkileyen ek faktörler (engellilik, kronik hastalık, kira yükü vb.)",
        )

        try:
            aktif_sorular = _fetch_sorular_aktif().get("sorular", [])
        except Exception:
            aktif_sorular = []

        if aktif_sorular:
            _bolum_basligi("6", "Ek Sorular")
            for soru in aktif_sorular:
                soru_id = soru["id"]
                soru_metni = soru["soru"] + " *"
                tip = soru.get("tip", "Kısa Metin")
                if tip == "Uzun Metin":
                    ek_cevaplar[soru_id] = st.text_area(soru_metni, key=f"eksoru_{soru_id}")
                elif tip == "Sayı":
                    ek_cevaplar[soru_id] = st.number_input(soru_metni, step=1, key=f"eksoru_{soru_id}")
                elif tip == "Tarih":
                    ek_cevaplar[soru_id] = _turkce_tarih_secimi(
                        soru_metni, f"eksoru_{soru_id}",
                        varsayilan=date.today(), min_yil=1930, max_yil=date.today().year + 1,
                    )
                elif tip == "Seçenekli":
                    secenekler = [s.strip() for s in soru.get("secenekler", "").split(",") if s.strip()]
                    ek_cevaplar[soru_id] = st.selectbox(
                        soru_metni, secenekler, index=None, placeholder="Seçiniz", key=f"eksoru_{soru_id}"
                    )
                elif tip == "Evet/Hayır":
                    ek_cevaplar[soru_id] = st.radio(soru_metni, ["Evet", "Hayır"], horizontal=True, key=f"eksoru_{soru_id}")
                else:  # Kısa Metin
                    ek_cevaplar[soru_id] = st.text_input(soru_metni, key=f"eksoru_{soru_id}")

    # -------- Belgeler: SADECE "Kısa Form" tipinde gösterilir --------
    uploaded = {}
    if kisa_form_mu:
        _bolum_basligi("2", "Belgeler")
        st.caption(
            "Belgeleri istenilen formatlarda gönderiniz"
        )
        SUTUN_SAYISI = 3
        for i in range(0, len(REQUIRED_DOCUMENTS), SUTUN_SAYISI):
            satir_belgeleri = REQUIRED_DOCUMENTS[i:i + SUTUN_SAYISI]
            kolonlar = st.columns(SUTUN_SAYISI)
            for kolon, doc in zip(kolonlar, satir_belgeleri):
                with kolon:
                    zorunlu_mu = doc.get("zorunlu", True)
                    etiket = f"{doc['label']} *" if zorunlu_mu else doc["label"]
                    uploaded[doc["key"]] = st.file_uploader(
                        etiket, type=doc.get("tur", ["pdf"]),
                        key=f"{doc['key']}_{st.session_state.get('dosya_epoch', '0')}",
                    )

    if kisa_form_mu:
        onay_no = "3"
    else:
        onay_no = "7" if aktif_sorular else "6"
    ONAY_IFADESI = "Bol-Dav Burs Başvurusu Yükümlülük Taahhütnamesini Okudum Onaylıyorum"

    _bolum_basligi(onay_no, "Onay")
    if kisa_form_mu:
        st.markdown(
            """
            <div style="background:#FAFAFA; border:1px solid #E5E5E5; border-radius:8px;
                        padding:1.25rem 1.5rem; font-size:14px; line-height:1.8; color:#111111;">
                <p style="text-align:center; font-weight:600; margin:0 0 12px;">BOL-DAV BURSLARI KARŞILIKSIZDIR</p>
                <p>Öğrenim hayatım boyunca akademik başarı düzeyimi, BOL-DAV Vakfı Burs Verme Usul ve
                Esaslarında belirtilen kriterlerin üzerinde tutmak için azami gayret göstereceğimi;
                vakfımızın teşvik ettiği sosyal, kültürel ve toplumsal sorumluluk projelerine aktif olarak
                katılım sağlamaya çalışacağımı beyan ediyorum.</p>
                <p>Allah nasip eder de eğitimimi tamamlayıp çalışma hayatına atılırsam, imkânlarım
                ölçüsünde BOL-DAV'a maddi ve manevi destek vermeyi; bir zamanlar bana uzanan yardım elini,
                kendim gibi eğitim hayatını sürdüren en az bir Bolvadinli üniversite öğrencisine ulaştırmak
                amacıyla BOL-DAV aracılığıyla burs vermeyi hedef olarak benimsediğimi ifade ediyorum.</p>
                <p>Ayrıca, BOL-DAV'ın amaç ve faaliyetlerini bulunduğum her ortamda tanıtmayı, vakfımızın
                birlik ve dayanışma anlayışını temsil etmeyi, gönüllü bir kültür ve dayanışma elçisi olarak
                hareket etmeyi vicdani bir sorumluluk ve vefa borcu olarak kabul ediyorum.</p>
                <p style="text-align:center; font-weight:600; margin:16px 0 0;">BOL-DAV BOLVADİNLİLER DAYANIŞMA VAKFI</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown(
            f"Onaylamak için aşağıdaki kutuya **tam olarak** şunu yazın: "
            f"\n\n> {ONAY_IFADESI}"
        )
        onay_metni = st.text_input("Onay ifadesi *", placeholder=ONAY_IFADESI)
        onay = onay_metni.strip() == ONAY_IFADESI
    else:
        onay = st.checkbox("Yukarıdaki bilgileri doğrularım ve belgelendiririm. *")

    gonder_buton_metni = "Taahhütnameyi Onayla" if kisa_form_mu else "Başvuruyu Gönder"
    submitted = st.button(gonder_buton_metni, use_container_width=True, type="primary")

    if submitted:
        zorunlu_metin_alanlari = {
            "Öğrenci Adı Soyadı": ad_soyad, "T.C. Kimlik No": tc_no, "E-Posta Adresi": email,
            "Cep Telefon Numarası": telefon,
        }
        if kisa_form_mu:
            zorunlu_metin_alanlari.update({
                "Banka İsmi": banka_ismi, "IBAN No": iban_no,
            })
        if not kisa_form_mu:
            zorunlu_metin_alanlari.update({
                "Fakülte": fakulte, "Bölüm": bolum, "Mezun Olduğu Lise": lise_adi,
                "Lise Mezuniyet Derecesi": lise_derece,
                "Baba Adı": baba_adi, "Baba Telefonu": baba_telefon, "Baba Adresi": baba_adres,
                "Anne Adı": anne_adi, "Anne Telefonu": anne_telefon, "Anne Adresi": anne_adres,
                "Sosyo Ekonomik Faktörler": sosyo_ekonomik, "Kardeşlerin Okuduğu Okullar": kardes_okullari,
            })
        eksikler = [ad for ad, deger in zorunlu_metin_alanlari.items() if not (deger or "").strip()]

        il_ilce_kontrol_listesi = [
            (dogum_il, dogum_ilce, "Öğrenci Doğum Yeri (İl/İlçe)"),
            (nufus_il, nufus_ilce, "Nüfusa Kayıtlı Olduğu Yer (Merkez/Köy)"),
        ]
        if not kisa_form_mu:
            il_ilce_kontrol_listesi += [
                (ikamet_il, ikamet_ilce, "İkamet Edilen İl/İlçe"),
                (baba_dogum_il, baba_dogum_ilce, "Baba Doğum Yeri (İl/İlçe)"),
                (anne_dogum_il, anne_dogum_ilce, "Anne Doğum Yeri (İl/İlçe)"),
            ]
        for il_deger, ilce_deger, ad in il_ilce_kontrol_listesi:
            if not il_deger or not ilce_deger:
                eksikler.append(ad)

        universite_final = None
        if not kisa_form_mu:
            if not okul_ili:
                eksikler.append("Okulun Bulunduğu İl")
            if not universite:
                eksikler.append("Üniversite Adı")
            elif universite == "Listede Yok / Diğer" and not universite_diger.strip():
                eksikler.append("Üniversite Adı (listede yoksa elle yazılmalı)")
            universite_final = universite_diger.strip() if universite == "Listede Yok / Diğer" else universite

            if not baba_meslek:
                eksikler.append("Babasının Mesleği")
            if not anne_meslek:
                eksikler.append("Annenin Mesleği")
            if baba_gelir is None:
                eksikler.append("Babanın Aylık Gelir Durumu")
            if anne_gelir is None:
                eksikler.append("Annenin Aylık Gelir Durumu")

        tarih_kontrol_listesi = [(dogum_tarihi, "Öğrenci Doğum Tarihi (geçersiz gün/ay kombinasyonu)")]
        if not kisa_form_mu:
            tarih_kontrol_listesi += [
                (baba_dogum_tarihi, "Baba Doğum Tarihi (geçersiz gün/ay kombinasyonu)"),
                (anne_dogum_tarihi, "Anne Doğum Tarihi (geçersiz gün/ay kombinasyonu)"),
            ]
        for tarih_deger, ad in tarih_kontrol_listesi:
            if tarih_deger is None:
                eksikler.append(ad)

        for soru in aktif_sorular:
            cevap = ek_cevaplar.get(soru["id"])
            if soru.get("tip") in ("Kısa Metin", "Uzun Metin") and not str(cevap or "").strip():
                eksikler.append(soru["soru"])
            elif soru.get("tip") == "Seçenekli" and not cevap:
                eksikler.append(soru["soru"])
            elif soru.get("tip") == "Tarih" and cevap is None:
                eksikler.append(soru["soru"] + " (geçersiz gün/ay kombinasyonu)")

        if len(tc_no.strip()) != 11 or not tc_no.strip().isdigit():
            eksikler.append("T.C. Kimlik No (11 haneli olmalı)")
        if kisa_form_mu:
            iban_temiz = (iban_no or "").replace(" ", "").upper()
            if len(iban_temiz) != 26 or not iban_temiz.startswith("TR") or not iban_temiz[2:].isdigit():
                eksikler.append("IBAN No (TR + 24 haneli olmalı, örn: TR00 0000 0000 0000 0000 0000 00)")
        if kisa_form_mu:
            for doc in REQUIRED_DOCUMENTS:
                if doc.get("zorunlu", True) and uploaded.get(doc["key"]) is None:
                    eksikler.append(doc["label"])
        if not onay:
            if kisa_form_mu:
                eksikler.append("Taahhütname ifadesi tam olarak yazılmalı")
            else:
                eksikler.append("Onay kutusu işaretlenmeli")

        if eksikler:
            st.error("Aşağıdaki alanları tamamlayın:\n\n- " + "\n- ".join(eksikler))
        else:
            temel_alanlar = {
                "Form Tipi": FORM_TIPI_GORUNEN["Kisa"] if kisa_form_mu else FORM_TIPI_GORUNEN["Tam"],
                "Cinsiyet": cinsiyet, "Öğrenci Adı Soyadı": ad_soyad, "T.C. Kimlik No": tc_no,
                "E-Posta Adresi": email, "Cep Telefon Numarası": telefon,
                "Öğrenci Doğum Tarihi": str(dogum_tarihi),
                "Öğrenci Doğum Yeri İl": dogum_il, "Öğrenci Doğum Yeri İlçe": dogum_ilce,
                "Nüfusa Kayıtlı Olduğu İl": nufus_il, "Nüfusa Kayıtlı Olduğu İlçe": nufus_ilce,
            }
            if kisa_form_mu:
                temel_alanlar.update({
                    "Banka İsmi": (banka_ismi or "").strip(),
                    "IBAN No": (iban_no or "").strip().upper().replace(" ", ""),
                })
            if not kisa_form_mu:
                temel_alanlar.update({
                    "İkamet İl": ikamet_il, "İkamet İlçe": ikamet_ilce,
                    "Öğrencinin Kaldığı Yer": kaldigi_yer,
                    "Üniversite Adı": universite_final, "Fakülte": fakulte, "Bölüm": bolum, "Sınıfı": sinif,
                    "Okulun Bulunduğu İl": okul_ili, "Mezun Olduğu Lise": lise_adi,
                    "Lise Mezuniyet Derecesi": lise_derece,
                    "Baba Adı": baba_adi,
                    "Baba Doğum Yeri İl": baba_dogum_il, "Baba Doğum Yeri İlçe": baba_dogum_ilce,
                    "Baba Doğum Tarihi": str(baba_dogum_tarihi), "Baba Adresi": baba_adres,
                    "Baba Telefonu": baba_telefon, "Babasının Mesleği": baba_meslek,
                    "Babanın Aylık Geliri (TL)": baba_gelir,
                    "Anne Adı": anne_adi,
                    "Anne Doğum Yeri İl": anne_dogum_il, "Anne Doğum Yeri İlçe": anne_dogum_ilce,
                    "Anne Doğum Tarihi": str(anne_dogum_tarihi), "Anne Adresi": anne_adres,
                    "Anne Telefonu": anne_telefon, "Annenin Mesleği": anne_meslek,
                    "Annenin Aylık Geliri (TL)": anne_gelir,
                    "Ebeveyn Medeni Durumu": ebeveyn_durumu,
                    "Okumakta Olan Kardeş Sayısı": kardes_sayisi,
                    "Kardeşlerin Okuduğu Okullar": kardes_okullari,
                    "Sosyo Ekonomik Faktörler": sosyo_ekonomik,
                    **{
                        f"Ek Soru: {soru['soru']}": str(ek_cevaplar.get(soru["id"], ""))
                        for soru in aktif_sorular
                    },
                })

            payload = {
                "action": "submit",
                "donem_adi": donem_adi,
                "timestamp": datetime.now().isoformat(),
                "fields": temel_alanlar,
                "files": (
                    {
                        doc["key"]: _file_to_b64(uploaded[doc["key"]])
                        for doc in REQUIRED_DOCUMENTS
                        if uploaded.get(doc["key"]) is not None
                    }
                    if kisa_form_mu else {}
                ),
                "folder_name": f"{ad_soyad.strip()}_{tc_no.strip()}",
            }
            st.session_state["pending_payload"] = payload
            st.session_state["confirm_pending"] = True
            st.rerun()

    if st.session_state.get("confirm_pending"):
        _onay_dialogu()

    if st.session_state.get("submit_success"):
        st.success("Başvurunuz başarıyla alındı. Lütfen tekrar gönderim yapmayınız.")
        _basari_animasyonu()
        st.session_state["submit_success"] = False


# ============================================================================
# YÖNETİCİ PANELİ
# ============================================================================
else:
    if _ust_serit("Yönetici Paneli", "Bol-Dav Bolvadinliler Dayanışma Vakfı", "Forma Dön", "btn_forma_don"):
        st.session_state.view = "form"
        st.rerun()

    if not st.session_state.admin_authed:
        st.markdown("#### Yönetici Girişi")
        u = st.text_input("Kullanıcı Adı")
        p = st.text_input("Şifre", type="password")
        if st.button("Giriş Yap"):
            creds = st.secrets["admin_credentials"]
            if u == creds["user"] and p == creds["pass"]:
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("Kullanıcı adı veya şifre hatalı.")
    else:
        if st.button("🔄 Verileri Yenile"):
            st.cache_data.clear()

        try:
            with st.spinner("Panel verileri yükleniyor..."):
                _dashboard = _fetch_admin_dashboard()
        except Exception:
            _dashboard = {"ok": False}
            st.error("📌 Panel verileri şu anda alınamadı. Lütfen sayfayı yenileyin.")

        if "exp_donem_acik" not in st.session_state:
            st.session_state.exp_donem_acik = False
        with st.expander("⚙️ Dönem Yönetimi (Ekle / Düzenle / Sil / Aktif-Pasif)", expanded=st.session_state.exp_donem_acik):
            if st.session_state.get("donem_basarili"):
                st.success("✅ Dönemler güncellendi.")
                st.session_state.donem_basarili = False
            donem_sonuc = (
                {"ok": True, "donemler": _dashboard.get("donemler", [])}
                if _dashboard.get("ok") else {"ok": False}
            )

            if donem_sonuc.get("ok"):
                st.caption(
                    "Tabloya yeni satır ekleyerek yeni dönem oluşturun, isimleri doğrudan düzenleyin, "
                    "satır silmek için satırın solundaki kutucuğu işaretleyip çöp kutusuna basın. "
                    "**Birden fazla dönem aynı anda 'Aktif' olabilir** — birden fazla aktifse öğrenci "
                    "forma girdiğinde hangi formu doldurmak istediğini seçer. Tek bir dönem aktifse "
                    "öğrenci doğrudan o forma yönlenir. Her dönem **kendi Form Tipi ayarına göre** "
                    f"öğrenciye {FORM_TIPI_GORUNEN['Tam']}, {FORM_TIPI_GORUNEN['Kisa']} ya da "
                    f"{FORM_TIPI_GORUNEN['Belge']} formunu gösterir."
                )

                donem_df = pd.DataFrame(donem_sonuc.get("donemler", []))
                if donem_df.empty:
                    donem_df = pd.DataFrame([{"ad": "", "durum": "Pasif", "form_tipi": "Tam"}])
                if "form_tipi" not in donem_df.columns:
                    donem_df["form_tipi"] = "Tam"
                donem_df["form_tipi"] = donem_df["form_tipi"].map(FORM_TIPI_GORUNEN).fillna(FORM_TIPI_GORUNEN["Tam"])

                edited_donem_df = st.data_editor(
                    donem_df,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "ad": st.column_config.TextColumn("Dönem Adı", required=True),
                        "durum": st.column_config.SelectboxColumn("Durum", options=["Aktif", "Pasif"], required=True),
                        "form_tipi": st.column_config.SelectboxColumn(
                            "Form Tipi", options=list(FORM_TIPI_GORUNEN.values()), required=True
                        ),
                    },
                    key="donem_editor",
                )

                if st.button("💾 Dönemleri Kaydet", type="primary"):
                    temiz_liste = [
                        {
                            "ad": str(r["ad"]).strip(),
                            "durum": r["durum"],
                            "form_tipi": FORM_TIPI_KOD.get(r["form_tipi"], "Tam"),
                        }
                        for _, r in edited_donem_df.iterrows()
                        if str(r["ad"]).strip()
                    ]
                    tum_anahtarlar = [(d["ad"], d["form_tipi"]) for d in temiz_liste]
                    tekrarlayanlar = sorted({k for k in tum_anahtarlar if tum_anahtarlar.count(k) > 1})
                    if tekrarlayanlar:
                        st.error(
                            "Aşağıdaki dönem + form tipi kombinasyonu birden fazla satırda kullanılmış: "
                            + ", ".join(f"'{ad}' ({FORM_TIPI_GORUNEN.get(ft, ft)})" for ad, ft in tekrarlayanlar)
                            + ". Aynı dönem adı farklı form tiplerinde tekrar edebilir (bu normaldir), "
                            "ama **aynı dönem adı + aynı form tipi** kombinasyonu birden fazla satırda olamaz "
                            "(sistem hangi satırın hangisi olduğunu ayırt edemez). Lütfen düzeltip tekrar kaydedin."
                        )
                    else:
                        try:
                            sonuc = _sync_donemler(temiz_liste)
                            if sonuc.get("ok"):
                                _fetch_donemler.clear()
                                _fetch_settings.clear()
                                _fetch_aktif_donemler.clear()
                                _fetch_admin_dashboard.clear()
                                st.session_state.donem_basarili = True
                                st.session_state.exp_donem_acik = True
                                st.rerun()
                            else:
                                st.error(f"Güncellenemedi: {sonuc.get('error', 'Bilinmeyen hata')}")
                        except Exception as e:
                            st.error(f"Güncellenemedi: {e}")

        if "exp_sorular_acik" not in st.session_state:
            st.session_state.exp_sorular_acik = False
        with st.expander("📝 Form Soruları (Ek Sorular) Yönetimi", expanded=st.session_state.exp_sorular_acik):
            st.caption(
                "Buradan eklediğiniz sorular, sabit alanların (T.C., aile bilgileri vb.) ALTINA, "
                "'Ek Sorular' başlığı altında forma otomatik eklenir. Sadece 'Aktif' işaretli sorular "
                "öğrenciye gösterilir. **Seçenekler** sütununu yalnızca Tip='Seçenekli' ise, "
                "seçenekleri virgülle ayırarak doldurun (örn: Evet, Hayır, Bilmiyorum)."
            )
            if st.session_state.get("sorular_basarili"):
                st.success("✅ Sorular güncellendi.")
                st.session_state.sorular_basarili = False
            sorular_sonuc = (
                {"ok": True, "sorular": _dashboard.get("sorular", [])}
                if _dashboard.get("ok") else {"ok": False}
            )

            if sorular_sonuc.get("ok"):
                sorular_liste = sorular_sonuc.get("sorular", [])
                sorular_df = pd.DataFrame(sorular_liste) if sorular_liste else pd.DataFrame(
                    [{"id": "", "soru": "", "tip": "Kısa Metin", "secenekler": "", "aktif": "Pasif", "sira": 0}]
                )
                for kol in ["id", "soru", "tip", "secenekler", "aktif", "sira"]:
                    if kol not in sorular_df.columns:
                        sorular_df[kol] = ""
                sorular_df = sorular_df[["soru", "tip", "secenekler", "aktif", "sira", "id"]]

                edited_sorular_df = st.data_editor(
                    sorular_df,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "soru": st.column_config.TextColumn("Soru Metni", required=True, width="large"),
                        "tip": st.column_config.SelectboxColumn(
                            "Tip", options=["Kısa Metin", "Uzun Metin", "Sayı", "Tarih", "Seçenekli", "Evet/Hayır"],
                            required=True,
                        ),
                        "secenekler": st.column_config.TextColumn("Seçenekler (virgülle)"),
                        "aktif": st.column_config.SelectboxColumn("Aktif", options=["Aktif", "Pasif"], required=True),
                        "sira": st.column_config.NumberColumn("Sıra", min_value=0, step=1),
                        "id": st.column_config.TextColumn("ID (dokunmayın)", disabled=True),
                    },
                    key="sorular_editor",
                )

                if st.button("💾 Soruları Kaydet", type="primary"):
                    temiz_liste = [
                        {
                            "id": str(r["id"]).strip() or None,
                            "soru": str(r["soru"]).strip(),
                            "tip": r["tip"],
                            "secenekler": str(r["secenekler"]).strip(),
                            "aktif": r["aktif"],
                        }
                        for _, r in edited_sorular_df.iterrows()
                        if str(r["soru"]).strip()
                    ]
                    try:
                        sonuc = _sync_sorular(temiz_liste)
                        if sonuc.get("ok"):
                            _fetch_sorular.clear()
                            _fetch_sorular_aktif.clear()
                            _fetch_admin_dashboard.clear()
                            st.session_state.sorular_basarili = True
                            st.session_state.exp_sorular_acik = True
                            st.rerun()
                        else:
                            st.error(f"Güncellenemedi: {sonuc.get('error', 'Bilinmeyen hata')}")
                    except Exception as e:
                        st.error(f"Güncellenemedi: {e}")

        if _dashboard.get("ok"):
            data = {"ok": True, "rows": _dashboard.get("rows", [])}
        else:
            st.error("📌 Başvuru verileri şu anda alınamadı. Lütfen sayfayı yenileyin.")
            st.stop()

        rows = data.get("rows", [])
        if not rows:
            st.info("Henüz başvuru yok.")
        else:
            df_tum = pd.DataFrame(rows)
            for col in ["Babanın Aylık Geliri (TL)", "Annenin Aylık Geliri (TL)", "Okumakta Olan Kardeş Sayısı"]:
                if col in df_tum.columns:
                    df_tum[col] = pd.to_numeric(df_tum[col], errors="coerce")
            if "Zaman Damgası" in df_tum.columns:
                df_tum["Zaman Damgası"] = pd.to_datetime(
                    df_tum["Zaman Damgası"], errors="coerce"
                ).dt.strftime("%d/%m/%Y %H:%M").fillna(df_tum["Zaman Damgası"])
            for tarih_kolonu in ["Öğrenci Doğum Tarihi", "Baba Doğum Tarihi", "Anne Doğum Tarihi"]:
                if tarih_kolonu in df_tum.columns:
                    donusmus = pd.to_datetime(df_tum[tarih_kolonu], errors="coerce").dt.strftime("%d/%m/%Y")
                    df_tum[tarih_kolonu] = donusmus.fillna(df_tum[tarih_kolonu])

            if "Dönem" in df_tum.columns:
                donemler = ["Tümü"] + sorted(df_tum["Dönem"].dropna().unique().tolist(), reverse=True)
                secilen_donem = st.selectbox("📅 Dönem Filtrele", donemler)
                df = df_tum if secilen_donem == "Tümü" else df_tum[df_tum["Dönem"] == secilen_donem]
            else:
                df = df_tum

            if "Form Tipi" in df.columns:
                form_tipi_serisi = df["Form Tipi"].dropna().astype(str).str.strip()
                form_tipleri = ["Tümü"] + sorted(form_tipi_serisi[form_tipi_serisi != ""].unique().tolist())
                secilen_form_tipi = st.selectbox("🧾 Form Tipi Filtrele", form_tipleri)
                if secilen_form_tipi != "Tümü":
                    df = df[df["Form Tipi"] == secilen_form_tipi].copy()
                    # Bu form tipinde tamamen boş kalan sütunları gizle (temiz görünüm/indirme için)
                    df = df.dropna(axis=1, how="all")
                    df = df.loc[:, ~(df.astype(str).apply(lambda s: s.str.strip()) == "").all()]

            tab_genel, tab_liste, tab_evrak = st.tabs(
                ["📊 Genel Bakış", "📋 Başvuru Listesi", "📁 Evrak Klasörleri"]
            )

            # -------------------- GENEL BAKIŞ --------------------
            with tab_genel:
                incelenen = int((df.get("İncelendi", pd.Series(dtype=str)) == "Evet").sum()) if "İncelendi" in df.columns else 0
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Toplam Başvuru", len(df))
                m2.metric("İncelenen", incelenen)
                m3.metric("Bekleyen", len(df) - incelenen)
                if "Babanın Aylık Geliri (TL)" in df.columns and "Annenin Aylık Geliri (TL)" in df.columns:
                    ort_gelir = (df["Babanın Aylık Geliri (TL)"].fillna(0) + df["Annenin Aylık Geliri (TL)"].fillna(0)).mean()
                    m4.metric("Ort. Aile Geliri (TL)", f"{ort_gelir:,.0f}".replace(",", "."))

                st.divider()
                if "analiz_goster" not in st.session_state:
                    st.session_state.analiz_goster = False

                if not st.session_state.analiz_goster:
                    if st.button("📊 Analizleri Göster (Grafikler)", use_container_width=True):
                        st.session_state.analiz_goster = True
                        st.rerun()
                else:
                    if st.button("🔽 Analizleri Gizle", use_container_width=True):
                        st.session_state.analiz_goster = False
                        st.rerun()

                    donem_sayilari_df = None
                    if "Dönem" in df_tum.columns and df_tum["Dönem"].nunique() > 1:
                        donem_sayilari_df = df_tum["Dönem"].value_counts().reset_index()

                    grafikler = _grafikleri_olustur(df, donem_sayilari_df)

                    g1, g2 = st.columns(2)
                    with g1:
                        if "cinsiyet" in grafikler:
                            st.plotly_chart(grafikler["cinsiyet"], use_container_width=True)
                    with g2:
                        if "sinif" in grafikler:
                            st.plotly_chart(grafikler["sinif"], use_container_width=True)

                    g3, g4 = st.columns(2)
                    with g3:
                        if "bolum" in grafikler:
                            st.plotly_chart(grafikler["bolum"], use_container_width=True)
                    with g4:
                        if "il" in grafikler:
                            st.plotly_chart(grafikler["il"], use_container_width=True)

                    g5, g6 = st.columns(2)
                    with g5:
                        if "medeni_durum" in grafikler:
                            st.plotly_chart(grafikler["medeni_durum"], use_container_width=True)
                    with g6:
                        if "meslek" in grafikler:
                            st.plotly_chart(grafikler["meslek"], use_container_width=True)

                    g7, g8 = st.columns(2)
                    with g7:
                        if "radar" in grafikler:
                            st.plotly_chart(grafikler["radar"], use_container_width=True)
                            st.caption(
                                "Not: Eksenler farklı birimlerdeki değerleri (TL, kişi sayısı, %) "
                                "karşılaştırılabilir kılmak için ölçeklendirilmiştir; mutlak değerler için "
                                "Başvuru Listesi sekmesindeki tabloya bakın."
                            )
                    with g8:
                        if "gelir_histogram" in grafikler:
                            st.plotly_chart(grafikler["gelir_histogram"], use_container_width=True)

                    if "donem_karsilastirma" in grafikler:
                        st.plotly_chart(grafikler["donem_karsilastirma"], use_container_width=True)

            # -------------------- BAŞVURU LİSTESİ (İncelendi işaretleme) --------------------
            with tab_liste:
                st.caption("İncelendi kutucuğunu işaretleyip **Değişiklikleri Kaydet**'e basın.")
                display_cols = [c for c in df.columns if not c.startswith("Belge:")]
                edit_df = df[display_cols].copy()
                if "İncelendi" in edit_df.columns:
                    edit_df["İncelendi"] = edit_df["İncelendi"].apply(lambda v: str(v).strip() == "Evet")

                edited = st.data_editor(
                    edit_df,
                    use_container_width=True,
                    hide_index=True,
                    disabled=[c for c in display_cols if c != "İncelendi"],
                    column_config={
                        "İncelendi": st.column_config.CheckboxColumn("İncelendi", default=False),
                    },
                    key="editor",
                )

                if st.button("💾 Değişiklikleri Kaydet", type="primary"):
                    degisen = 0
                    for i in range(len(edit_df)):
                        eski = edit_df.iloc[i]["İncelendi"]
                        yeni = edited.iloc[i]["İncelendi"]
                        if eski != yeni:
                            tc_no = edit_df.iloc[i].get("T.C. Kimlik No", "")
                            try:
                                _update_review_status(tc_no, "Evet" if yeni else "Hayır")
                                degisen += 1
                            except Exception as e:
                                st.error(f"{tc_no} güncellenemedi: {e}")
                    if degisen:
                        st.success(f"{degisen} kayıt güncellendi.")
                        _fetch_all_rows.clear()
                        _fetch_admin_dashboard.clear()
                        st.rerun()
                    else:
                        st.info("Değişiklik bulunamadı.")

                st.markdown("#### 📥 Dışa Aktar")
                st.caption("Görüntülediğiniz listeden bağımsız olarak, indirmek istediğiniz veriyi burada seçin.")
                dl_col1, dl_col2 = st.columns(2)
                with dl_col1:
                    if "Dönem" in df_tum.columns:
                        dl_donemler = ["Tümü"] + sorted(df_tum["Dönem"].dropna().unique().tolist(), reverse=True)
                    else:
                        dl_donemler = ["Tümü"]
                    indirilecek_donem = st.selectbox("İndirilecek Dönem", dl_donemler, key="indir_donem")
                with dl_col2:
                    if "Form Tipi" in df_tum.columns:
                        dl_form_tipi_serisi = df_tum["Form Tipi"].dropna().astype(str).str.strip()
                        dl_form_tipleri = sorted(dl_form_tipi_serisi[dl_form_tipi_serisi != ""].unique().tolist())
                    else:
                        dl_form_tipleri = []
                    if not dl_form_tipleri:
                        dl_form_tipleri = list(FORM_TIPI_GORUNEN.values())
                    indirilecek_form_tipi = st.selectbox("İndirilecek Form Tipi", dl_form_tipleri, key="indir_form_tipi")

                if st.button("📊 Excel Oluştur", use_container_width=True):
                    export_df = df_tum.copy()
                    if indirilecek_donem != "Tümü" and "Dönem" in export_df.columns:
                        export_df = export_df[export_df["Dönem"] == indirilecek_donem]
                    if "Form Tipi" in export_df.columns:
                        export_df = export_df[export_df["Form Tipi"] == indirilecek_form_tipi]
                        export_df = export_df.dropna(axis=1, how="all")
                        export_df = export_df.loc[
                            :, ~(export_df.astype(str).apply(lambda s: s.str.strip()) == "").all()
                        ]
                    export_display_cols = [c for c in export_df.columns if not c.startswith("Belge:")]
                    veri_df = export_df[export_display_cols].copy()

                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                        veri_df.to_excel(writer, index=False, sheet_name="Basvurular")

                        # -------- Özet Pivot sayfası (statik, hazır özet tablolar) --------
                        # NOT: "T.C. Kimlik No" sadece Tam Anket/Kısa Form'da var, Belge
                        # Gönderme'de yok — bu yüzden her form tipinde ortak olan
                        # "Öğrenci Adı Soyadı" sayım için kullanılır (KeyError'u önler).
                        ozet_sheet_yazildi = False
                        if "Dönem" in veri_df.columns and "Cinsiyet" in veri_df.columns and "Öğrenci Adı Soyadı" in veri_df.columns:
                            pivot1 = pd.pivot_table(
                                veri_df, index="Dönem", columns="Cinsiyet",
                                values="Öğrenci Adı Soyadı", aggfunc="count", fill_value=0,
                            )
                            pivot1.to_excel(writer, sheet_name="Özet Pivot", startrow=1)
                            ozet_sheet_yazildi = True
                        if "Bölüm" in veri_df.columns:
                            pivot2 = (
                                veri_df["Bölüm"].value_counts().rename("Başvuru Sayısı").to_frame()
                            )
                            baslangic_satiri = len(pivot1) + 5 if ozet_sheet_yazildi else 1
                            pivot2.to_excel(writer, sheet_name="Özet Pivot", startrow=baslangic_satiri)

                        ws = writer.sheets["Basvurular"]
                        from openpyxl.worksheet.table import Table, TableStyleInfo
                        from openpyxl.utils import get_column_letter

                        n_satir, n_sutun = veri_df.shape
                        if n_satir > 0 and n_sutun > 0:
                            son_hucre = f"{get_column_letter(n_sutun)}{n_satir + 1}"
                            tablo = Table(displayName="BasvuruTablosu", ref=f"A1:{son_hucre}")
                            tablo.tableStyleInfo = TableStyleInfo(
                                name="TableStyleMedium9", showRowStripes=True,
                                showFirstColumn=False, showLastColumn=False,
                            )
                            ws.add_table(tablo)

                            for i, kolon in enumerate(veri_df.columns, start=1):
                                uzunluk = max(len(str(kolon)), veri_df[kolon].astype(str).str.len().max() if n_satir else 0)
                                ws.column_dimensions[get_column_letter(i)].width = min(max(uzunluk + 2, 10), 40)

                            for kolon_adi in ["Babanın Aylık Geliri (TL)", "Annenin Aylık Geliri (TL)",
                                              "Okumakta Olan Kardeş Sayısı"]:
                                if kolon_adi in veri_df.columns:
                                    col_idx = veri_df.columns.get_loc(kolon_adi) + 1
                                    harf = get_column_letter(col_idx)
                                    for satir in range(2, n_satir + 2):
                                        ws[f"{harf}{satir}"].number_format = "#,##0"

                    st.session_state["excel_buffer"] = buffer.getvalue()
                    guvenli_ad = f"{indirilecek_donem}_{indirilecek_form_tipi}".replace(" ", "_").replace("/", "-")
                    st.session_state["excel_dosya_adi"] = (
                        f"basvurular_{guvenli_ad}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                    )
                    st.session_state["excel_satir_sayisi"] = n_satir

                if st.session_state.get("excel_buffer"):
                    st.caption(f"Hazır: {st.session_state.get('excel_satir_sayisi', 0)} kayıt içeren dosya indirilmeye hazır.")
                    st.download_button(
                        "📥 Excel'i İndir (Tablo + Özet Pivot)",
                        data=st.session_state["excel_buffer"],
                        file_name=st.session_state.get("excel_dosya_adi", "basvurular.xlsx"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                st.caption(
                    "İndirilen dosyada 'Basvurular' sayfası filtrelenebilir bir Excel tablosu, "
                    "'Özet Pivot' sayfası ise dönem/cinsiyet/bölüm bazlı hazır özet tablolar içerir. "
                    "Kendi dinamik pivot tablonuzu oluşturmak isterseniz: tabloyu seçip "
                    "Excel'de Ekle → PivotTable kullanabilirsiniz."
                )

                # -------------------- KAYIT SİLME (kırmızı buton + onay) --------------------
                st.divider()
                st.markdown("#### 🗑️ Kayıt Silme")
                st.caption(
                    "Silmek istediğiniz kaydın yanındaki kırmızı butona basın — kayıt listeden kaldırılır "
                    "(henüz silinmez). Ardından **Silme İşlemini Uygula**'ya basıp onaylayınca kalıcı olarak silinir."
                )

                if "silinecek_kayitlar" not in st.session_state:
                    st.session_state.silinecek_kayitlar = set()
                if "silme_basarili_sayisi" in st.session_state:
                    n = st.session_state.pop("silme_basarili_sayisi")
                    if n:
                        st.success(f"{n} kayıt silindi.")

                gorunur_satirlar = [
                    (
                        str(r.get("T.C. Kimlik No", "")),
                        str(r.get("Dönem", "")),
                        str(r.get("Öğrenci Adı Soyadı", "—")),
                        str(r.get("Bölüm", "—")),
                    )
                    for _, r in df.iterrows()
                    if (str(r.get("T.C. Kimlik No", "")), str(r.get("Dönem", ""))) not in st.session_state.silinecek_kayitlar
                ]

                if not gorunur_satirlar:
                    st.info("Gösterilecek kayıt yok.")
                else:
                    for i, (tc_no, donem_deger, ad, bolum) in enumerate(gorunur_satirlar):
                        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                        c1.write(ad)
                        c2.write(bolum)
                        c3.write(donem_deger)
                        if c4.button("🗑️", key=f"kaldir_{i}_{tc_no}_{donem_deger}", help="Listeden kaldır"):
                            st.session_state.silinecek_kayitlar.add((tc_no, donem_deger))
                            st.rerun()

                if st.session_state.silinecek_kayitlar:
                    st.warning(f"{len(st.session_state.silinecek_kayitlar)} kayıt silinmek üzere işaretlendi.")
                    col_uygula, col_vazgec = st.columns(2)
                    with col_uygula:
                        if st.button("🗑️ Silme İşlemini Uygula", type="primary", use_container_width=True):
                            st.session_state["silme_onay_bekliyor"] = True
                    with col_vazgec:
                        if st.button("İşaretleri Temizle", use_container_width=True):
                            st.session_state.silinecek_kayitlar = set()
                            st.rerun()

                if st.session_state.get("silme_onay_bekliyor"):
                    _silme_onay_dialogu()

            # -------------------- EVRAK KLASÖRLERİ --------------------
            with tab_evrak:
                if "Drive Klasör Linki" in df.columns:
                    for _, row in df.iterrows():
                        durum = "✅ İncelendi" if str(row.get("İncelendi", "")).strip() == "Evet" else "⏳ Bekliyor"
                        st.markdown(
                            f"- **{row.get('Öğrenci Adı Soyadı', '—')}** ({durum}) → "
                            f"[Drive Klasörünü Aç]({row.get('Drive Klasör Linki', '#')})"
                        )

        if st.button("Çıkış Yap"):
            st.session_state.admin_authed = False
            st.rerun()
