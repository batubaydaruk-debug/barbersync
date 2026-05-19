"""
BarberSync — Screen 4: Inventory Management
Product list, stock movements, shortage draft generation and approval.
"""
import streamlit as st
from modules.inventory import (
    list_products, get_low_stock,
    add_product, update_stock,
    generate_shortage_draft, list_shortage_drafts,
    get_draft_with_items, update_draft_status,
    list_categories, ensure_default_category,
    list_suppliers,
)

st.set_page_config(page_title="Envanter — BarberSync", page_icon="✂️", layout="wide")

# ── auth guard ────────────────────────────────────────────────────────────────
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("Bu sayfayı görüntülemek için giriş yapmanız gerekiyor.")
    st.page_link("app.py", label="Giriş Yap")
    st.stop()

user = st.session_state.user
if user["primary_role"] not in ("owner", "barber"):
    st.warning("Bu sayfa işletme sahipleri ve berberler içindir.")
    st.stop()

shop_id = user.get("shop_id")
if not shop_id:
    st.error("Bu hesaba bağlı bir işletme bulunamadı.")
    st.stop()

# ── sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown(f"**{user['full_name']}**")
role_label = "İşletme Sahibi" if user["primary_role"] == "owner" else "Berber"
st.sidebar.caption(role_label)
if st.sidebar.button("Çıkış Yap"):
    st.session_state.user = None
    st.rerun()

st.title("Envanter Yönetimi")

tab_products, tab_add, tab_movement, tab_drafts = st.tabs(
    ["Ürünler", "Yeni Ürün Ekle", "Stok Hareketi", "Sipariş Taslakları"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Product List
# ─────────────────────────────────────────────────────────────────────────────
with tab_products:
    try:
        products  = list_products(shop_id)
        low_stock = get_low_stock(shop_id)
        low_ids   = {p["id"] for p in low_stock}
    except Exception as e:
        st.error(f"Ürünler yüklenemedi: {e}")
        products = []
        low_ids  = set()

    if not products:
        st.info("Henüz ürün eklenmemiş.")
    else:
        if low_ids:
            st.warning(f"⚠️ {len(low_ids)} ürün minimum stok seviyesinin altında!")

        col_headers = st.columns([3, 1, 1, 1, 1])
        col_headers[0].markdown("**Ürün Adı**")
        col_headers[1].markdown("**Stok**")
        col_headers[2].markdown("**Min.**")
        col_headers[3].markdown("**Birim**")
        col_headers[4].markdown("**Durum**")

        for p in products:
            cols = st.columns([3, 1, 1, 1, 1])
            cols[0].write(p["name"])
            cols[1].write(p.get("current_stock", 0))
            cols[2].write(p.get("min_threshold", 0))
            cols[3].write(p.get("unit", "—"))
            if p["id"] in low_ids:
                cols[4].error("Düşük")
            else:
                cols[4].success("Yeterli")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Add Product
# ─────────────────────────────────────────────────────────────────────────────
with tab_add:
    if user["primary_role"] != "owner":
        st.info("Ürün ekleme yalnızca işletme sahipleri tarafından yapılabilir.")
    else:
        try:
            categories = list_categories(shop_id)
            if not categories:
                default_cat = ensure_default_category(shop_id)
                categories  = [default_cat]
        except Exception:
            categories = []

        try:
            suppliers = list_suppliers(shop_id)
        except Exception:
            suppliers = []

        with st.form("form_add_product"):
            p_name     = st.text_input("Ürün Adı *")
            p_sku      = st.text_input("SKU / Barkod")
            p_unit     = st.text_input("Birim", value="adet")
            p_stock    = st.number_input("Başlangıç Stok", min_value=0, value=0, step=1)
            p_min      = st.number_input("Min. Eşik", min_value=0, value=5, step=1)
            p_cost     = st.number_input("Maliyet (TL)", min_value=0.0, value=0.0, step=0.5)

            cat_map = {c.get("name", c["id"]): c["id"] for c in categories}
            p_cat   = st.selectbox("Kategori", list(cat_map.keys())) if cat_map else None

            sup_map = {s.get("name", s["id"]): s["id"] for s in suppliers}
            p_sup   = st.selectbox("Tedarikçi (isteğe bağlı)", ["—"] + list(sup_map.keys()))

            submitted = st.form_submit_button("Ürün Ekle", type="primary")

        if submitted:
            if not p_name:
                st.error("Ürün adı zorunludur.")
            else:
                try:
                    add_product(
                        shop_id       = shop_id,
                        name          = p_name,
                        sku           = p_sku or None,
                        unit          = p_unit,
                        initial_stock = int(p_stock),
                        min_threshold = int(p_min),
                        cost_per_unit = p_cost,
                        category_id   = cat_map.get(p_cat) if p_cat else None,
                        supplier_id   = sup_map.get(p_sup) if p_sup and p_sup != "—" else None,
                        created_by    = user["id"],
                    )
                    st.success(f"'{p_name}' ürünü eklendi.")
                except Exception as exc:
                    st.error(str(exc))

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Stock Movement
# ─────────────────────────────────────────────────────────────────────────────
with tab_movement:
    try:
        products_mv = list_products(shop_id)
    except Exception:
        products_mv = []

    if not products_mv:
        st.info("Henüz ürün eklenmemiş.")
    else:
        prod_map = {p["name"]: p for p in products_mv}

        with st.form("form_movement"):
            chosen_prod  = st.selectbox("Ürün", list(prod_map.keys()))
            mv_type      = st.selectbox(
                "Hareket Türü",
                ["purchase", "usage", "adjustment", "waste"],
                format_func=lambda x: {
                    "purchase":   "Satın Alma (+)",
                    "usage":      "Kullanım (−)",
                    "adjustment": "Düzeltme",
                    "waste":      "Fire/Zayi (−)",
                }[x],
            )
            quantity     = st.number_input("Miktar", min_value=1, value=1, step=1)
            mv_notes     = st.text_input("Not (isteğe bağlı)")
            mv_submitted = st.form_submit_button("Hareketi Kaydet", type="primary")

        if mv_submitted:
            prod = prod_map[chosen_prod]
            delta = quantity if mv_type == "purchase" else -quantity
            if mv_type == "adjustment":
                delta = quantity  # can be negative via notes
            try:
                update_stock(
                    shop_id       = shop_id,
                    product_id    = prod["id"],
                    quantity_delta= delta,
                    movement_type = mv_type,
                    performed_by  = user["id"],
                    notes         = mv_notes or None,
                )
                st.success(f"Stok hareketi kaydedildi. (Δ {delta:+d})")
            except Exception as exc:
                st.error(str(exc))

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Shortage Drafts
# ─────────────────────────────────────────────────────────────────────────────
with tab_drafts:
    col_gen, col_list = st.columns([1, 2], gap="large")

    with col_gen:
        st.subheader("Yeni Taslak Oluştur")
        st.caption("Eksik stoklar için otomatik sipariş taslağı oluşturur.")
        if st.button("Taslak Oluştur", type="primary", use_container_width=True):
            try:
                draft = generate_shortage_draft(shop_id, generated_by=user["id"])
                if draft is None:
                    st.info("Stok altı ürün bulunamadı.")
                else:
                    st.success(f"Taslak oluşturuldu: #{draft['id'][:8]}…")
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))

    with col_list:
        st.subheader("Taslaklar")
        try:
            drafts = list_shortage_drafts(shop_id)
        except Exception as e:
            st.error(f"Taslaklar yüklenemedi: {e}")
            drafts = []

        if not drafts:
            st.info("Henüz taslak oluşturulmadı.")
        else:
            status_tr = {
                "draft":    "Taslak",
                "approved": "Onaylandı",
                "ordered":  "Sipariş Verildi",
                "received": "Teslim Alındı",
                "cancelled":"İptal",
            }
            NEXT_STATUS = {
                "draft":    "approved",
                "approved": "ordered",
                "ordered":  "received",
            }
            NEXT_LABEL = {
                "draft":    "Onayla",
                "approved": "Sipariş Verildi",
                "ordered":  "Teslim Alındı Olarak İşaretle",
            }

            for d in drafts:
                created = d.get("created_at", "")[:10]
                status  = d.get("status", "draft")
                label   = status_tr.get(status, status)
                with st.expander(f"#{d['id'][:8]}…  |  {created}  |  {label}"):
                    try:
                        detail = get_draft_with_items(d["id"])
                        items  = detail.get("items", [])
                        if items:
                            for item in items:
                                prod_name = (item.get("products") or {}).get("name", item.get("product_id", "—"))
                                st.write(f"- {prod_name}: {item['requested_quantity']} {item.get('unit','adet')}")
                        else:
                            st.write("Taslak kalemi bulunamadı.")
                    except Exception:
                        pass

                    if status in NEXT_STATUS and user["primary_role"] == "owner":
                        next_s = NEXT_STATUS[status]
                        next_l = NEXT_LABEL[status]
                        if st.button(next_l, key=f"draft_act_{d['id']}", type="primary"):
                            try:
                                update_draft_status(d["id"], next_s, user["id"])
                                st.success(f"Durum güncellendi: {status_tr.get(next_s, next_s)}")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
