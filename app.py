/**
 * ÖĞRENCİ BAŞVURU FORMU — Apps Script Backend
 * ---------------------------------------------------------------
 * Kurulum:
 * 1) script.google.com > Yeni proje > bu kodun tamamını yapıştırın.
 * 2) Aşağıdaki SECRET_KEY değerini değiştirin (Streamlit secrets'taki
 *    APPS_SCRIPT_SECRET ile BİREBİR aynı olmalı).
 * 3) Üstte "Dağıt > Yeni dağıtım > Web uygulaması" seçin.
 *    - Yürüten kişi: Ben (Me)
 *    - Erişimi olanlar: Herkes (Anyone)
 * 4) Verilen /exec URL'sini Streamlit secrets'taki APPS_SCRIPT_URL'e yazın.
 * 5) İlk çalıştırmada Google izin ekranı çıkacaktır, hesabınızla onaylayın.
 *
 * NOT: Kodu her değiştirdiğinizde "Dağıt > Dağıtımları Yönet > Düzenle (kalem) >
 * Yeni sürüm > Dağıt" yapmanız gerekir; URL aynı kalır.
 */

const SECRET_KEY = "Buraya-Guclu-Bir-Anahtar-Yazin-2026"; // Streamlit ile BİREBİR aynı olmalı
const SHEET_NAME = "Basvurular";
const DONEMLER_SHEET_NAME = "Donemler";
const SORULAR_SHEET_NAME = "Sorular";
const DRIVE_ROOT_FOLDER_NAME = "Ogrenci Basvuru Evraklari";

// Yeni başvuru geldiğinde bildirim gönderilecek e-posta adres(ler)i.
// Birden fazla kişiye göndermek isterseniz virgülle ayırarak yazın:
// "biri@ornek.com,digeri@ornek.com"
const BILDIRIM_EPOSTA = "buraya-kendi-mailinizi-yazin@ornek.com";

function _getSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SHEET_NAME);
  }
  return sheet;
}

// -------------------- DÖNEMLER (Ekle / Düzenle / Sil / Aktif-Pasif + Form Tipi) --------------------
function _getDonemlerSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(DONEMLER_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(DONEMLER_SHEET_NAME);
    sheet.appendRow(["Dönem Adı", "Durum", "Form Tipi"]);
    sheet.appendRow(["2024-2025 Dönemi", "Pasif", "Tam"]); // "Tam" = Tam Anket, "Kisa" = Kısa Form
  }
  // Eski sürümden (Form Tipi sütunu olmayan) geliyorsa otomatik ekle
  if (sheet.getLastColumn() < 3) {
    sheet.getRange(1, 3).setValue("Form Tipi");
    const sonSatir = sheet.getLastRow();
    if (sonSatir > 1) {
      const varsayilanlar = [];
      for (let i = 1; i < sonSatir; i++) varsayilanlar.push(["Tam"]);
      sheet.getRange(2, 3, sonSatir - 1, 1).setValues(varsayilanlar);
    }
  }
  return sheet;
}

function _listDonemler() {
  const sheet = _getDonemlerSheet();
  const values = sheet.getDataRange().getValues();
  const rows = [];
  for (let i = 1; i < values.length; i++) {
    if (String(values[i][0]).trim() === "") continue;
    rows.push({
      ad: values[i][0],
      durum: values[i][1] || "Pasif",
      form_tipi: values[i][2] || "Tam",
    });
  }
  return rows;
}

function _getAktifDonem() {
  const donemler = _listDonemler();
  for (let i = 0; i < donemler.length; i++) {
    if (donemler[i].durum === "Aktif") return donemler[i];
  }
  return null;
}

function _getAktifDonemlerListesi() {
  return _listDonemler().filter(function (d) { return d.durum === "Aktif"; });
}

function _getAktifDonemAdi() {
  const aktif = _getAktifDonem();
  return aktif ? aktif.ad : null;
}

// -------------------- EK SORULAR (Ekle / Düzenle / Sil / Aktif-Pasif) --------------------
function _getSorularSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(SORULAR_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(SORULAR_SHEET_NAME);
    sheet.appendRow(["ID", "Soru Metni", "Tip", "Seçenekler", "Aktif", "Sıra"]);
  }
  return sheet;
}

function _listSorular() {
  const sheet = _getSorularSheet();
  const values = sheet.getDataRange().getValues();
  const rows = [];
  for (let i = 1; i < values.length; i++) {
    if (String(values[i][1]).trim() === "") continue;
    rows.push({
      id: values[i][0],
      soru: values[i][1],
      tip: values[i][2] || "Kısa Metin",
      secenekler: values[i][3] || "",
      aktif: values[i][4] || "Hayır",
      sira: values[i][5] || 0,
    });
  }
  rows.sort(function (a, b) { return Number(a.sira) - Number(b.sira); });
  return rows;
}

// -------------------- DRIVE KLASÖRLERİ --------------------
function _getRootFolder() {
  const folders = DriveApp.getFoldersByName(DRIVE_ROOT_FOLDER_NAME);
  if (folders.hasNext()) return folders.next();
  return DriveApp.createFolder(DRIVE_ROOT_FOLDER_NAME);
}

function _getDonemFolder(donemAdi) {
  const root = _getRootFolder();
  const safeAdi = (donemAdi || "Donem Belirtilmemis").replace(/[\\/:*?"<>|]/g, "_");
  const folders = root.getFoldersByName(safeAdi);
  if (folders.hasNext()) return folders.next();
  return root.createFolder(safeAdi);
}

function _trashFolderFromUrl(url) {
  try {
    const match = String(url).match(/[-\w]{25,}/);
    if (match) {
      DriveApp.getFolderById(match[0]).setTrashed(true);
    }
  } catch (err) {
    // Klasör zaten yoksa veya erişilemiyorsa sessizce geç
  }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.secret !== SECRET_KEY) {
      return _json({ ok: false, error: "unauthorized" });
    }

    if (body.action === "update_review") {
      const sheet = _getSheet();
      const values = sheet.getDataRange().getValues();
      const headers = values[0];
      const tcCol = headers.indexOf("T.C. Kimlik No");
      const incelendiCol = headers.indexOf("İncelendi");
      if (tcCol === -1 || incelendiCol === -1) {
        return _json({ ok: false, error: "sütun bulunamadı" });
      }
      let found = false;
      for (let i = 1; i < values.length; i++) {
        if (String(values[i][tcCol]) === String(body.tc_no)) {
          sheet.getRange(i + 1, incelendiCol + 1).setValue(body.value);
          found = true;
          break;
        }
      }
      return _json({ ok: found });
    }

    if (body.action === "delete_row") {
      const sheet = _getSheet();
      const values = sheet.getDataRange().getValues();
      const headers = values[0];
      const tcCol = headers.indexOf("T.C. Kimlik No");
      const donemCol = headers.indexOf("Dönem");
      const klasorCol = headers.indexOf("Drive Klasör Linki");
      if (tcCol === -1) {
        return _json({ ok: false, error: "sütun bulunamadı" });
      }
      let found = false;
      for (let i = 1; i < values.length; i++) {
        const tcEslesiyor = String(values[i][tcCol]) === String(body.tc_no);
        const donemEslesiyor = donemCol === -1 || String(values[i][donemCol]) === String(body.donem);
        if (tcEslesiyor && donemEslesiyor) {
          if (klasorCol !== -1 && values[i][klasorCol]) {
            _trashFolderFromUrl(values[i][klasorCol]);
          }
          sheet.deleteRow(i + 1);
          found = true;
          break;
        }
      }
      return _json({ ok: found });
    }

    if (body.action === "sync_donemler") {
      const yeniListe = body.donemler || [];
      const sheet = _getDonemlerSheet();
      sheet.clear();
      sheet.appendRow(["Dönem Adı", "Durum", "Form Tipi"]);
      yeniListe.forEach(function (d) {
        const ad = String(d.ad || "").trim();
        if (ad !== "") {
          sheet.appendRow([
            ad,
            d.durum === "Aktif" ? "Aktif" : "Pasif",
            ["Kisa", "Belge"].indexOf(d.form_tipi) !== -1 ? d.form_tipi : "Tam",
          ]);
        }
      });
      sheet.getRange(1, 1, 1, 3).setFontWeight("bold");
      return _json({ ok: true });
    }

    if (body.action === "sync_sorular") {
      const yeniListe = body.sorular || [];
      const sheet = _getSorularSheet();
      sheet.clear();
      sheet.appendRow(["ID", "Soru Metni", "Tip", "Seçenekler", "Aktif", "Sıra"]);
      yeniListe.forEach(function (s, idx) {
        const soru = String(s.soru || "").trim();
        if (soru !== "") {
          sheet.appendRow([
            s.id || Utilities.getUuid(),
            soru,
            s.tip || "Kısa Metin",
            s.secenekler || "",
            s.aktif === "Aktif" ? "Aktif" : "Pasif",
            idx,
          ]);
        }
      });
      sheet.getRange(1, 1, 1, 6).setFontWeight("bold");
      return _json({ ok: true });
    }

    // -------------------- BAŞVURU GÖNDERİMİ --------------------
    // Artık birden fazla dönem aynı anda Aktif olabildiği için, hangi döneme
    // gönderildiği istemciden (body.donem_adi) alınır ve halen Aktif olduğu
    // doğrulanır. Bu, öğrencinin form seçim ekranında seçtiği dönemdir.
    const gonderilenDonemAdi = body.donem_adi;
    const aktifDonem = gonderilenDonemAdi
      ? _getAktifDonemlerListesi().find(function (d) { return d.ad === gonderilenDonemAdi; })
      : _getAktifDonem(); // eski istemciler için geriye dönük uyumluluk
    const aktifDonemAdi = aktifDonem ? aktifDonem.ad : null;
    if (!aktifDonemAdi) {
      return _json({ ok: false, error: "basvurular_kapali" });
    }

    const fields = body.fields || {};
    const files = body.files || {};
    const folderName = (body.folder_name || "isimsiz").replace(/[\\/:*?"<>|]/g, "_");

    // 1) Dosya varsa: dönem klasörü altında öğrenciye özel Drive klasörü oluştur
    //    (Tam Anket'te dosya olmadığı için gereksiz boş klasör oluşturulmaz)
    let studentFolder = null;
    const fileLinks = {};
    if (Object.keys(files).length > 0) {
      const donemFolder = _getDonemFolder(aktifDonemAdi);
      studentFolder = donemFolder.createFolder(folderName + "_" + new Date().getTime());
      Object.keys(files).forEach(function (key) {
        const f = files[key];
        const bytes = Utilities.base64Decode(f.data_b64);
        const blob = Utilities.newBlob(bytes, f.mimetype, f.filename);
        const driveFile = studentFolder.createFile(blob);
        fileLinks[key] = driveFile.getUrl();
      });
    }

    // 2) Sheet'e satır ekle — DEĞERLER SÜTUN ADINA GÖRE EŞLEŞTİRİLİR.
    //    (Form tipleri farklı alan setleri gönderdiği için, sadece pozisyona göre
    //    yazmak yanlış sütunlara veri kaymasına sebep olurdu; bu yüzden her değer
    //    kendi başlığının altına, isim eşleştirmesiyle yazılır. Yeni bir form tipi
    //    daha önce görülmemiş bir alan getirirse, sona otomatik yeni sütun eklenir.)
    const sheet = _getSheet();
    const fieldKeys = Object.keys(fields);
    const extraCols = ["Zaman Damgası", "Dönem", "İncelendi", "Drive Klasör Linki"];
    const fileCols = Object.keys(files).map(function (k) { return "Belge: " + k; });
    const buBasvurununBasliklari = fieldKeys.concat(extraCols).concat(fileCols);

    let mevcutBasliklar;
    if (sheet.getLastRow() === 0) {
      mevcutBasliklar = buBasvurununBasliklari;
      sheet.appendRow(mevcutBasliklar);
      sheet.getRange(1, 1, 1, mevcutBasliklar.length).setFontWeight("bold");
      sheet.setFrozenRows(1);
    } else {
      mevcutBasliklar = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
      const eksikBasliklar = buBasvurununBasliklari.filter(function (h) {
        return mevcutBasliklar.indexOf(h) === -1;
      });
      if (eksikBasliklar.length > 0) {
        sheet.getRange(1, mevcutBasliklar.length + 1, 1, eksikBasliklar.length).setValues([eksikBasliklar]);
        sheet.getRange(1, mevcutBasliklar.length + 1, 1, eksikBasliklar.length).setFontWeight("bold");
        mevcutBasliklar = mevcutBasliklar.concat(eksikBasliklar);
      }
    }

    const degerHaritasi = {};
    fieldKeys.forEach(function (k) { degerHaritasi[k] = fields[k]; });
    degerHaritasi["Zaman Damgası"] = body.timestamp || new Date().toISOString();
    degerHaritasi["Dönem"] = aktifDonemAdi;
    degerHaritasi["İncelendi"] = "Hayır";
    degerHaritasi["Drive Klasör Linki"] = studentFolder ? studentFolder.getUrl() : "";
    Object.keys(files).forEach(function (k) { degerHaritasi["Belge: " + k] = fileLinks[k] || ""; });

    const row = mevcutBasliklar.map(function (baslik) {
      return Object.prototype.hasOwnProperty.call(degerHaritasi, baslik) ? degerHaritasi[baslik] : "";
    });

    sheet.appendRow(row);

    // 3) Yöneticiye bildirim e-postası gönder (hata olursa başvuruyu etkilemesin diye ayrı try/catch)
    try {
      _bildirimEpostasiGonder(fields, aktifDonemAdi, studentFolder);
    } catch (mailErr) {
      // E-posta gönderilemezse sessizce geç, başvuru zaten kaydedildi.
    }

    return _json({ ok: true });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  try {
    const secret = e.parameter.secret;
    if (secret !== SECRET_KEY) {
      return _json({ ok: false, error: "unauthorized" });
    }

    if (e.parameter.action === "list_rows") {
      const sheet = _getSheet();
      const values = sheet.getDataRange().getValues();
      if (values.length < 2) {
        return _json({ ok: true, rows: [] });
      }
      const headers = values[0];
      const rows = values.slice(1).map(function (r) {
        const obj = {};
        headers.forEach(function (h, i) { obj[h] = r[i]; });
        return obj;
      });
      return _json({ ok: true, rows: rows });
    }

    if (e.parameter.action === "get_donemler") {
      return _json({ ok: true, donemler: _listDonemler() });
    }

    if (e.parameter.action === "get_aktif_donemler") {
      return _json({ ok: true, donemler: _getAktifDonemlerListesi() });
    }

    if (e.parameter.action === "get_settings") {
      const aktif = _getAktifDonem();
      return _json({
        ok: true,
        aktif: aktif ? "Evet" : "Hayır",
        donem: aktif ? aktif.ad : "",
        form_tipi: aktif ? aktif.form_tipi : "Tam",
      });
    }

    if (e.parameter.action === "get_sorular") {
      return _json({ ok: true, sorular: _listSorular() });
    }

    if (e.parameter.action === "get_sorular_aktif") {
      const hepsi = _listSorular().filter(function (s) { return s.aktif === "Aktif"; });
      return _json({ ok: true, sorular: hepsi });
    }

    return _json({ ok: false, error: "unknown_action" });
  } catch (err) {
    return _json({ ok: false, error: String(err) });
  }
}

// -------------------- BİLDİRİM E-POSTASI --------------------
function _bildirimEpostasiGonder(fields, donemAdi, studentFolder) {
  if (!BILDIRIM_EPOSTA || BILDIRIM_EPOSTA.indexOf("@ornek.com") !== -1) {
    return; // BILDIRIM_EPOSTA henüz ayarlanmamışsa gönderme
  }

  const adSoyad = fields["Öğrenci Adı Soyadı"] || "İsimsiz";
  const bolum = fields["Bölüm"] || "-";
  const email = fields["E-Posta Adresi"] || "-";
  const telefon = fields["Cep Telefon Numarası"] || "-";
  const klasorLinki = studentFolder ? studentFolder.getUrl() : "(Bu form tipinde belge yok)";

  const konu = "Yeni Burs Başvurusu: " + adSoyad;
  const govde =
    "Yeni bir öğrenci burs başvurusu alındı.\n\n" +
    "Ad Soyad: " + adSoyad + "\n" +
    "Bölüm: " + bolum + "\n" +
    "E-Posta: " + email + "\n" +
    "Telefon: " + telefon + "\n" +
    "Dönem: " + donemAdi + "\n" +
    "Evrak Klasörü: " + klasorLinki + "\n\n" +
    "Tüm başvuruları görmek için Google E-Tablonuzu veya yönetici panelini açabilirsiniz.";

  BILDIRIM_EPOSTA.split(",").forEach(function (adres) {
    const temizAdres = adres.trim();
    if (temizAdres) {
      MailApp.sendEmail(temizAdres, konu, govde);
    }
  });
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
