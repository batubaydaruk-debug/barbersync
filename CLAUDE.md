# BarberSync — CLAUDE.md

## Proje Özeti

BarberSync, Türkiye'deki berberler için geliştirilmiş bir yönetim bilgi sistemidir (MIS). Temel sorunu çözer: müşterilerin randevuya gelmemesi (no-show). Bunu itibar puanlaması ve ileride AI destekli tahminlerle gerçekleştirir.

**Hedef kullanıcılar:** Berberler (randevu yönetimi), müşteriler (randevu alma), işletme sahipleri (genel yönetim).

---

## Teknoloji Yığını

| Katman | Araç |
|---|---|
| Frontend | Python 3.10+, Streamlit |
| Veritabanı | PostgreSQL via Supabase (supabase-py 2.x) |
| Auth | Özel bcrypt (Supabase Auth kullanılmıyor) |
| AI (planlanan) | Google Gemini API — no-show tahminleri |
| Secrets | `.streamlit/secrets.toml` → `[supabase]` url / key |

---

## Çalıştırma Komutları

```bash
# Uygulamayı başlat
streamlit run app.py

# Testleri çalıştır
pytest
```

---

## Proje Yapısı

```
barbersync/
├── app.py                  # Giriş / kayıt (tüm roller)
├── db.py                   # Veritabanı katmanı — tüm Supabase çağrıları burada
├── schema.sql              # Referans şema (gerçek DB ile senkronize)
├── pages/
│   ├── 1_Randevu_Al.py     # Müşteri: randevu al + geçmişi gör
│   ├── 2_Berber_Paneli.py  # Berber: randevuları yönet + hizmet ekle
│   └── 3_Itibar_Skorum.py  # Müşteri: itibar skorunu gör
└── .streamlit/
    └── secrets.toml        # Supabase credentials (.gitignore'da)
```

---

## Veritabanı Şeması (Özet)

Gerçek Supabase DB'de 6 tablo vardır:

| Tablo | Açıklama |
|---|---|
| `persons` | Tüm kullanıcılar — role: `customer`, `barber`, `owner` |
| `shops` | Dükkanlar — `owner_person_id` → persons |
| `barbers` | persons × shops bağlantısı — bir kişi birden fazla dükkanda çalışabilir |
| `services` | Hizmetler — `barber_id` → **barbers.id** (persons.id değil!) |
| `appointments` | Randevular — `customer_person_id`, `barber_person_id` → persons |
| `reputation_scores` | İtibar geçmişi (yedek) — skor uygulama katmanında hesaplanır |

**Kritik FK:** `services.barber_id` → `barbers.id` (barbers tablosu, persons değil).

---

## db.py API (Tüm Sayfaların Kullandığı Fonksiyonlar)

```python
# Auth
login_user(email, password) → (user_dict | None, error | None)
register_user(full_name, email, phone, password, role) → (user_dict | None, error | None)

# Shops
list_shops() → list[dict]  # id, display_name
get_or_create_shop_for_owner(owner_person_id, display_name) → dict

# Barbers
list_barbers(shop_id) → list[dict]  # barber_id, person_id, full_name, specialty
get_barber_by_person(person_id) → dict | None
register_barber(person_id, shop_id, specialty) → dict

# Services  — barber_id = barbers.id
list_services(barber_id, only_active=True) → list[dict]
create_service(barber_id, name, duration_minutes, price) → dict

# Appointments
available_slots(barber_person_id, for_date, duration_min) → list[time]  # naive time objeleri
create_appointment(customer_person_id, barber_person_id, shop_id, service_id,
                   starts_at, duration_min, price, notes) → dict  # ValueError on conflict
list_my_appointments(person_id, role) → list[dict]  # role: "customer" | "barber"
update_appointment_status(appointment_id, status, cancelled_by=None) → None

# Reputation
reputation_for(customer_person_id) → dict  # score, tier, total_count, completed_count, no_show_count, late_cancel_count
```

---

## İtibar Skoru Hesabı

| Olay | Puan |
|---|---|
| Başlangıç | 100 |
| Tamamlanan randevu | +2 |
| No-show | −15 |
| Geç iptal (randevuya <2 saat kala, müşteri) | −5 |

**Seviyeler:** Güvenilir (85+) · Normal (60–84) · Riskli (30–59) · Kara liste (0–29) · Yeni (hiç randevu yok)

---

## Kodlama Standartları

- **Type hints** zorunlu — `str | None`, `list[dict]`, vb.
- **Soft-delete** — `persons.deleted_at` doldurulur; kayıt silinmez (KVKK Madde 7 uyumu).
- `db.py`'de yalnızca Supabase çağrıları bulunur — iş mantığı sayfa dosyalarında değil, `db.py`'de tutulur.
- Yeni tablo veya sütun eklendiğinde `schema.sql` güncellenmeli.
- Supabase join alias söz dizimi: `"barber:persons!appointments_barber_person_id_fkey(full_name)"` — FK adı belirtilmezse çift FK yüzünden hata alınır.
- `available_slots` naive `time` nesneleri döner — `datetime.combine(date, time)` uyumluluğu için.

---

## Çalışma Saatleri & Slot Yapısı

- Çalışma: 09:00–18:00 (naive, UTC varsayımı)
- Slot adımı: 30 dakika
- Geçerli slot: `slot_baslangic + hizmet_suresi <= 18:00` ve çakışan onaylı/bekleyen randevu yok

---

## Planlanan Özellikler (AI)

- Google Gemini API ile no-show olasılık tahmini (müşteri itibar skoru + geçmiş birleştirilerek)
- Berber panelinde "Riskli Randevular" uyarısı

---

## Güvenlik Notu

Supabase RLS (Row Level Security) tüm tablolarda **kapalı**. Bu bir demo ortamı için kabul edilebilir, canlı ortamda her tablo için RLS politikaları yazılmalıdır.
