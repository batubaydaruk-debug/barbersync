-- =====================================================
-- BarberSync — Supabase Şeması (Gerçek DB ile senkronize)
-- =====================================================

-- 1) persons: müşteri + berber + işletme sahibi tek tabloda, role ile ayrılır
create table if not exists persons (
    id            uuid primary key default gen_random_uuid(),
    full_name     varchar not null,
    email         varchar unique not null,
    phone         varchar unique,
    role          varchar not null default 'customer',
    password_hash text,
    created_at    timestamptz not null default now(),
    deleted_at    timestamptz  -- soft-delete (KVKK Madde 7)
);

-- 2) shops: dükkanlar (sahibi bir persons kaydıdır)
create table if not exists shops (
    id              uuid primary key default gen_random_uuid(),
    owner_person_id uuid not null references persons(id),
    display_name    varchar not null,
    phone           varchar,
    address         text,
    is_active       boolean not null default true,
    created_at      timestamptz not null default now()
);

-- 3) barbers: persons × shops bağlantı tablosu
create table if not exists barbers (
    id           uuid primary key default gen_random_uuid(),
    person_id    uuid not null references persons(id),
    shop_id      uuid not null references shops(id),
    specialty    varchar,
    is_available boolean not null default true,
    created_at   timestamptz not null default now()
);

create index if not exists idx_barbers_shop    on barbers(shop_id);
create index if not exists idx_barbers_person  on barbers(person_id);

-- 4) services: berbere ait hizmetler (barbers.id'ye bağlı)
create table if not exists services (
    id               uuid primary key default gen_random_uuid(),
    barber_id        uuid not null references barbers(id) on delete cascade,
    name             varchar not null,
    duration_minutes int not null check (duration_minutes > 0),
    price            numeric(10, 2) not null default 0,
    is_active        boolean not null default true,
    created_at       timestamptz not null default now()
);

create index if not exists idx_services_barber on services(barber_id);

-- 5) appointments: randevular
create table if not exists appointments (
    id                  uuid primary key default gen_random_uuid(),
    shop_id             uuid not null references shops(id),
    customer_person_id  uuid not null references persons(id),
    barber_person_id    uuid not null references persons(id),
    service_id          uuid references services(id),
    scheduled_start     timestamptz not null,
    scheduled_end       timestamptz not null,
    status              varchar not null default 'pending'
                        check (status in ('pending','confirmed','completed','cancelled','no_show')),
    total_price         numeric(10, 2),
    customer_notes      text,
    cancelled_at        timestamptz,
    cancelled_by        varchar check (cancelled_by in ('customer','barber')),
    created_at          timestamptz not null default now()
);

create index if not exists idx_appt_barber_time on appointments(barber_person_id, scheduled_start);
create index if not exists idx_appt_customer    on appointments(customer_person_id);
create index if not exists idx_appt_status      on appointments(status);

-- 6) reputation_scores: itibar puanı (uygulama katmanında hesaplanır, tablo yedek amaçlıdır)
create table if not exists reputation_scores (
    id                  bigserial primary key,
    customer_person_id  uuid not null references persons(id),
    shop_id             uuid references shops(id),
    score               smallint not null default 100 check (score >= 0 and score <= 100),
    total_appointments  int not null default 0,
    total_no_shows      int not null default 0,
    last_updated_at     timestamptz not null default now()
);

-- =====================================================
-- Skor hesaplama kuralları (uygulama katmanı, reputation_for fonksiyonu):
--   Başlangıç: 100
--   +2  tamamlanan randevu başına
--   -15 no-show başına
--   -5  geç iptal (randevuya 2 saatten az kala müşteri iptali) başına
--
-- Seviyeler:
--   85+ → Güvenilir  🟢
--   60–84 → Normal   🔵
--   30–59 → Riskli   🟡
--   0–29  → Kara liste 🔴
--   0 randevu → Yeni ⚪
-- =====================================================
