-- ============================================================
-- BarberSync — Full Database Schema  (34 tables)
-- PostgreSQL / Supabase compatible
-- Run this in the Supabase SQL editor.
-- For development: disable RLS on each table or add permissive policies.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================

DO $$ BEGIN CREATE TYPE appointment_status AS ENUM (
    'pending','confirmed','completed','no_show',
    'cancelled_by_customer','cancelled_by_shop','late_cancel'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE reputation_event_type AS ENUM (
    'no_show','late_cancel','completed','good_review','manual_adjustment'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE stock_movement_type AS ENUM (
    'restock','usage','adjustment','waste'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE shortage_draft_status AS ENUM (
    'draft','sent','completed'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE notification_channel AS ENUM (
    'email','sms','in_app'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE notification_status AS ENUM (
    'pending','sent','delivered','failed'
); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================
-- GROUP 1: IDENTITY & ACCESS
-- ============================================================

CREATE TABLE IF NOT EXISTS persons (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name                   VARCHAR(160) NOT NULL,
    email                       VARCHAR(255) NOT NULL UNIQUE,
    phone                       VARCHAR(32)  NOT NULL UNIQUE,
    password_hash               VARCHAR(255) NOT NULL,
    has_accepted_privacy_notice BOOLEAN      NOT NULL DEFAULT FALSE,
    has_accepted_marketing      BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verified_at           TIMESTAMPTZ,
    last_login_at               TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_name   VARCHAR(64)  NOT NULL UNIQUE,
    description VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

INSERT INTO roles (role_name, description) VALUES
    ('customer', 'Randevu alan müşteri'),
    ('barber',   'Hizmet veren berber'),
    ('owner',    'İşletme sahibi / yöneticisi')
ON CONFLICT (role_name) DO NOTHING;

CREATE TABLE IF NOT EXISTS person_roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id   UUID NOT NULL REFERENCES persons(id),
    role_id     UUID NOT NULL REFERENCES roles(id),
    shop_id     UUID,
    granted_by  UUID REFERENCES persons(id),
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id           UUID NOT NULL REFERENCES persons(id),
    session_token_hash  VARCHAR(255) NOT NULL,
    ip_address          TEXT,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    issued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id   UUID NOT NULL REFERENCES persons(id),
    token_hash  VARCHAR(255) NOT NULL,
    used        BOOLEAN     NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id              BIGSERIAL PRIMARY KEY,
    person_id       UUID REFERENCES persons(id),
    ip_address      TEXT,
    attempted_email VARCHAR(255),
    was_successful  BOOLEAN     NOT NULL DEFAULT FALSE,
    failure_reason  TEXT,
    attempted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retain_until    TIMESTAMPTZ
);

-- ============================================================
-- GROUP 2: TENANT (SHOP)
-- ============================================================

CREATE TABLE IF NOT EXISTS shops (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_person_id             UUID NOT NULL REFERENCES persons(id),
    legal_name                  VARCHAR(255) NOT NULL,
    display_name                VARCHAR(160) NOT NULL,
    tax_identification_number   VARCHAR(32)  UNIQUE,
    controller_contact_email    VARCHAR(255),
    controller_contact_phone    VARCHAR(32),
    address_line1               VARCHAR(255),
    address_line2               VARCHAR(255),
    city                        VARCHAR(128),
    postal_code                 VARCHAR(16),
    country_code                CHAR(2)      NOT NULL DEFAULT 'TR',
    timezone                    VARCHAR(64)  NOT NULL DEFAULT 'Europe/Istanbul',
    business_hours              JSONB        NOT NULL DEFAULT '{}',
    is_accepting_appointments   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_active                   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

DO $$ BEGIN
    ALTER TABLE person_roles ADD CONSTRAINT fk_person_roles_shop
        FOREIGN KEY (shop_id) REFERENCES shops(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS manager_profiles (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id               UUID NOT NULL REFERENCES persons(id),
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    job_title               VARCHAR(128),
    has_financial_access    BOOLEAN NOT NULL DEFAULT FALSE,
    has_staff_admin_access  BOOLEAN NOT NULL DEFAULT FALSE,
    termination_date        DATE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ
);

-- ============================================================
-- GROUP 3: SERVICE CATALOG
-- ============================================================

CREATE TABLE IF NOT EXISTS service_categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id     UUID NOT NULL REFERENCES shops(id),
    name        VARCHAR(128) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS services (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                     UUID NOT NULL REFERENCES shops(id),
    service_category_id         UUID NOT NULL REFERENCES service_categories(id),
    name                        VARCHAR(160)     NOT NULL,
    description                 TEXT,
    default_duration_minutes    INTEGER          NOT NULL DEFAULT 30,
    base_price                  NUMERIC(10,2)    NOT NULL DEFAULT 0,
    is_active                   BOOLEAN          NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

-- ============================================================
-- GROUP 4: RESERVATION PIPELINE
-- ============================================================

CREATE TABLE IF NOT EXISTS barber_profiles (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id                   UUID NOT NULL REFERENCES persons(id),
    shop_id                     UUID NOT NULL REFERENCES shops(id),
    display_name                VARCHAR(160),
    bio                         TEXT,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    termination_date            DATE,
    is_accepting_appointments   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS barber_services (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    barber_profile_id           UUID NOT NULL REFERENCES barber_profiles(id),
    service_id                  UUID NOT NULL REFERENCES services(id),
    override_price              NUMERIC(10,2),
    override_duration_minutes   INTEGER,
    is_active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ,
    UNIQUE(barber_profile_id, service_id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                 UUID             NOT NULL REFERENCES shops(id),
    customer_person_id      UUID             NOT NULL REFERENCES persons(id),
    barber_person_id        UUID             NOT NULL REFERENCES persons(id),
    status                  appointment_status NOT NULL DEFAULT 'pending',
    scheduled_start         TIMESTAMPTZ      NOT NULL,
    scheduled_end           TIMESTAMPTZ      NOT NULL,
    actual_start            TIMESTAMPTZ,
    actual_end              TIMESTAMPTZ,
    total_price_snapshot    NUMERIC(10,2)    NOT NULL DEFAULT 0,
    customer_notes          TEXT,
    internal_notes          TEXT,
    created_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS appointment_status_history (
    id                      BIGSERIAL PRIMARY KEY,
    appointment_id          UUID NOT NULL REFERENCES appointments(id),
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    from_status             appointment_status,
    to_status               appointment_status NOT NULL,
    changed_by_person_id    UUID REFERENCES persons(id),
    reason                  VARCHAR(255),
    changed_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS appointment_services (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id              UUID    NOT NULL REFERENCES appointments(id),
    service_id                  UUID    NOT NULL REFERENCES services(id),
    barber_profile_id           UUID    REFERENCES barber_profiles(id),
    duration_minutes_snapshot   INTEGER NOT NULL,
    display_order               SMALLINT NOT NULL DEFAULT 0,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS appointment_reference_images (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id          UUID         NOT NULL REFERENCES appointments(id),
    shop_id                 UUID         NOT NULL REFERENCES shops(id),
    storage_uri             VARCHAR(1024) NOT NULL,
    file_type               VARCHAR(64),
    uploaded_by_person_id   UUID         NOT NULL REFERENCES persons(id),
    uploaded_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    retain_until            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ============================================================
-- GROUP 5: REPUTATION
-- ============================================================

CREATE TABLE IF NOT EXISTS customer_profiles (
    person_id                   UUID PRIMARY KEY REFERENCES persons(id),
    reputation_score            SMALLINT    NOT NULL DEFAULT 100
                                    CHECK (reputation_score >= 0 AND reputation_score <= 100),
    total_appointments_count    INTEGER     NOT NULL DEFAULT 0,
    total_no_shows_count        INTEGER     NOT NULL DEFAULT 0,
    preferred_language          CHAR(2)     NOT NULL DEFAULT 'tr',
    notes_for_barber            TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reputation_events (
    id                      BIGSERIAL PRIMARY KEY,
    customer_person_id      UUID NOT NULL REFERENCES persons(id),
    shop_id                 UUID REFERENCES shops(id),
    appointment_id          UUID REFERENCES appointments(id),
    event_type              reputation_event_type NOT NULL,
    score_delta             SMALLINT NOT NULL,
    reason                  VARCHAR(255),
    performed_by_person_id  UUID REFERENCES persons(id),
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_shop_reputations (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_person_id      UUID NOT NULL REFERENCES persons(id),
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    appointments_count      INTEGER     NOT NULL DEFAULT 0,
    no_show_count           INTEGER     NOT NULL DEFAULT 0,
    last_event_at           TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(customer_person_id, shop_id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id      UUID     NOT NULL REFERENCES appointments(id),
    shop_id             UUID     NOT NULL REFERENCES shops(id),
    barber_person_id    UUID     NOT NULL REFERENCES persons(id),
    reviewer_person_id  UUID     NOT NULL REFERENCES persons(id),
    rating              SMALLINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment             TEXT,
    is_moderated        BOOLEAN      NOT NULL DEFAULT FALSE,
    submitted_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ
);

-- ============================================================
-- GROUP 6: INVENTORY
-- ============================================================

CREATE TABLE IF NOT EXISTS product_categories (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id     UUID NOT NULL REFERENCES shops(id),
    name        VARCHAR(128) NOT NULL,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS suppliers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id         UUID NOT NULL REFERENCES shops(id),
    name            VARCHAR(160) NOT NULL,
    contact_name    VARCHAR(160),
    contact_email   VARCHAR(255),
    contact_phone   VARCHAR(32),
    address         TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS products (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    product_category_id     UUID NOT NULL REFERENCES product_categories(id),
    preferred_supplier_id   UUID REFERENCES suppliers(id),
    sku                     VARCHAR(64)   NOT NULL,
    name                    VARCHAR(160)  NOT NULL,
    description             TEXT,
    unit_of_measure         VARCHAR(32)   NOT NULL DEFAULT 'adet',
    min_threshold           NUMERIC(12,3) NOT NULL DEFAULT 0,
    reorder_quantity        NUMERIC(12,3) NOT NULL DEFAULT 0,
    unit_cost               NUMERIC(10,2),
    current_stock           NUMERIC(12,3) NOT NULL DEFAULT 0,
    is_active               BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    deleted_at              TIMESTAMPTZ,
    UNIQUE(shop_id, sku)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id                      BIGSERIAL PRIMARY KEY,
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    product_id              UUID NOT NULL REFERENCES products(id),
    movement_type           stock_movement_type NOT NULL,
    quantity_delta          NUMERIC(12,3) NOT NULL,
    appointment_id          UUID REFERENCES appointments(id),
    performed_by_person_id  UUID REFERENCES persons(id),
    notes                   VARCHAR(255),
    performed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shortage_drafts (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                     UUID NOT NULL REFERENCES shops(id),
    generated_at                TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    generated_by_person_id      UUID REFERENCES persons(id),
    status                      shortage_draft_status NOT NULL DEFAULT 'draft',
    reviewed_at                 TIMESTAMPTZ,
    reviewed_by_person_id       UUID REFERENCES persons(id),
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS shortage_draft_items (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shortage_draft_id           UUID NOT NULL REFERENCES shortage_drafts(id),
    product_id                  UUID NOT NULL REFERENCES products(id),
    current_stock_snapshot      NUMERIC(12,3) NOT NULL,
    min_threshold_snapshot      NUMERIC(12,3) NOT NULL,
    recommended_quantity        NUMERIC(12,3) NOT NULL,
    preferred_supplier_id       UUID REFERENCES suppliers(id),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- GROUP 7: ANALYTICS
-- ============================================================

CREATE TABLE IF NOT EXISTS barber_performance_snapshots (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                 UUID NOT NULL REFERENCES shops(id),
    barber_person_id        UUID NOT NULL REFERENCES persons(id),
    period_year             SMALLINT NOT NULL,
    period_month            SMALLINT NOT NULL CHECK (period_month >= 1 AND period_month <= 12),
    appointments_completed  INTEGER      NOT NULL DEFAULT 0,
    appointments_scheduled  INTEGER      NOT NULL DEFAULT 0,
    total_revenue           NUMERIC(12,2) NOT NULL DEFAULT 0,
    no_show_rate            NUMERIC(5,4)  NOT NULL DEFAULT 0,
    cancellation_rate       NUMERIC(5,4)  NOT NULL DEFAULT 0,
    average_rating          NUMERIC(3,2),
    is_bonus_eligible       BOOLEAN      NOT NULL DEFAULT FALSE,
    generated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(shop_id, barber_person_id, period_year, period_month)
);

CREATE TABLE IF NOT EXISTS noshow_predictions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    appointment_id          UUID NOT NULL REFERENCES appointments(id),
    predicted_probability   NUMERIC(5,4) NOT NULL
                                CHECK (predicted_probability >= 0 AND predicted_probability <= 1),
    model_version           VARCHAR(64),
    feature_snapshot        JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS data_deletion_requests (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id               UUID NOT NULL REFERENCES persons(id),
    requested_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by_person_id   UUID REFERENCES persons(id),
    completed_at            TIMESTAMPTZ,
    rejection_reason        TEXT,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- GROUP 8: KVKK COMPLIANCE
-- ============================================================

CREATE TABLE IF NOT EXISTS privacy_notice_versions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_label       VARCHAR(16)  NOT NULL,
    language            CHAR(2)      NOT NULL DEFAULT 'tr',
    content_markdown    TEXT         NOT NULL,
    is_active           BOOLEAN      NOT NULL DEFAULT FALSE,
    effective_from      TIMESTAMPTZ  NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

INSERT INTO privacy_notice_versions (version_label, language, content_markdown, is_active, effective_from)
VALUES (
    'v1.0', 'tr',
    '# Gizlilik Bildirimi

KVKK (6698 Sayılı Kanun) kapsamında toplanan kişisel verileriniz (isim, e-posta, telefon, randevu geçmişi) yalnızca hizmet sunumu amacıyla işlenmektedir. Verileriniz üçüncü taraflarla paylaşılmaz. İstediğiniz zaman verilerinizin silinmesini talep edebilirsiniz.',
    TRUE, NOW()
) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS consent_logs (
    id                          BIGSERIAL PRIMARY KEY,
    person_id                   UUID NOT NULL REFERENCES persons(id),
    shop_id                     UUID REFERENCES shops(id),
    consent_type                VARCHAR(64) NOT NULL,
    privacy_notice_version_id   UUID REFERENCES privacy_notice_versions(id),
    granted_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address                  TEXT,
    user_agent                  VARCHAR(512)
);

CREATE TABLE IF NOT EXISTS notification_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id         UUID REFERENCES shops(id),
    template_key    VARCHAR(64)          NOT NULL,
    channel         notification_channel NOT NULL,
    language        CHAR(2)              NOT NULL DEFAULT 'tr',
    subject         VARCHAR(255),
    body_template   TEXT                 NOT NULL,
    is_active       BOOLEAN              NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS notifications (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id                 UUID REFERENCES shops(id),
    recipient_person_id     UUID NOT NULL REFERENCES persons(id),
    template_key            VARCHAR(64),
    channel                 notification_channel NOT NULL DEFAULT 'in_app',
    status                  notification_status  NOT NULL DEFAULT 'pending',
    related_entity_type     VARCHAR(64),
    related_entity_id       UUID,
    payload                 JSONB       NOT NULL DEFAULT '{}',
    scheduled_at            TIMESTAMPTZ,
    delivered_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retain_until            TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                  BIGSERIAL PRIMARY KEY,
    shop_id             UUID REFERENCES shops(id),
    active_person_id    UUID REFERENCES persons(id),
    action              VARCHAR(128) NOT NULL,
    entity_type         VARCHAR(64)  NOT NULL,
    entity_id           UUID,
    before_state        JSONB,
    after_state         JSONB,
    ip_address          VARCHAR(64),
    user_agent          VARCHAR(512),
    occurred_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    retain_until        TIMESTAMPTZ
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_appointments_shop_id        ON appointments(shop_id);
CREATE INDEX IF NOT EXISTS idx_appointments_customer       ON appointments(customer_person_id);
CREATE INDEX IF NOT EXISTS idx_appointments_barber         ON appointments(barber_person_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled_start ON appointments(scheduled_start);
CREATE INDEX IF NOT EXISTS idx_reputation_events_customer  ON reputation_events(customer_person_id);
CREATE INDEX IF NOT EXISTS idx_products_shop_id            ON products(shop_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product     ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient     ON notifications(recipient_person_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_shop              ON audit_log(shop_id);
