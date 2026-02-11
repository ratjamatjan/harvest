import io
import re
import unicodedata
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# --------------------------------------------------
# App config
# --------------------------------------------------
st.set_page_config(page_title="Central-motor (TSV)", layout="centered")

CONTRACT = "Kontrakt: ID, Benämning, Meta • Tomma fält OK • Ingen validering • Ordningen betyder något"

INTERPRETATION_PROMPT = """Tolka bilden som ett arbetsunderlag (inte slutdokumentation).

Leverera TSV med kolumner:
ID <TAB> Benämning <TAB> Meta

Regler:
- Identifiera logiska rader (grupper, kablar, funktioner).
- Behåll ordningen som på bilden.
- Hoppa inte över rader/gruppnummer. Om en rad är tom/oklar: skriv '-' i Benämning.
- ID är fri text (t.ex. 15.3, 6-9, Kabel 12, Spis). Om ID saknas i underlaget: skriv '-'.
- Benämning är fri, mänsklig beskrivning. Om Benämning saknas i underlaget: skriv '-'.
- Lägg teknisk info (säkring, area, JFB, fas, kabelnr, KNX, m.m.) i Meta om den är tydlig.
- Gissa inte. Lämna Meta tomt eller skriv '-' om du vill markera att det saknas.
- Om det finns rubriker/sektioner (t.ex. JFB, Central 1/2), lägg dem som egna rader.
"""


# --------------------------------------------------
# Helpers (funktioner som används av UI)
# --------------------------------------------------
def parse_tsv(tsv_text: str) -> pd.DataFrame:
    tsv_text = (tsv_text or "").strip("\n\r ")
    if not tsv_text:
        return pd.DataFrame(columns=["ID", "Benämning", "Meta"])

    try:
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t", dtype=str)
    except Exception:
        df = pd.DataFrame()

    if df.shape[1] != 3:
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t", header=None, dtype=str)
        while df.shape[1] < 3:
            df[df.shape[1]] = ""
        if df.shape[1] > 3:
            df = df.iloc[:, :3]
        df.columns = ["ID", "Benämning", "Meta"]
    else:
        df = df.iloc[:, :3]
        df.columns = ["ID", "Benämning", "Meta"]

    df = df.fillna("")
    for c in ["ID", "Benämning", "Meta"]:
        df[c] = df[c].astype(str).str.strip()

    return df


def df_to_tsv(df: pd.DataFrame, include_header: bool = True) -> str:
    out = df.copy()
    for col in ["ID", "Benämning", "Meta"]:
        if col not in out.columns:
            out[col] = ""
    out = out[["ID", "Benämning", "Meta"]].fillna("").astype(str)
    return out.to_csv(sep="\t", index=False, header=include_header, lineterminator="\n")


def slugify(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "projekt"

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-").lower()

    return text or "projekt"


def build_filename(project: str, panel: str) -> str:
    now = datetime.now()
    date_stamp = now.strftime("%Y-%m-%d")
    time_stamp = now.strftime("%H%M")

    p = slugify(project)
    c = slugify(panel) if panel.strip() else ""

    if c:
        return f"{p}__{c}__{date_stamp}__{time_stamp}.tsv"
    return f"{p}__{date_stamp}__{time_stamp}.tsv"


def build_report_pdf_bytes(df: pd.DataFrame, title: str) -> bytes:
    """
    Skapar PDF direkt (riktig .pdf) för mobil/desktop.
    Tar 2 kolumner: ID (Grupp nr) + Benämning (Gruppens omfattning).
    """
    rows = df[["ID", "Benämning"]].fillna("").astype(str).values.tolist()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    margin = 12 * mm
    x0 = margin
    x1 = page_w - margin
    y_top = page_h - margin

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Table geometry
    table_left = x0
    table_right = x1
    table_width = table_right - table_left
    col1_w = 18 * mm
    col2_w = table_width - col1_w

    header_h = 8 * mm
    row_h = 7 * mm
    gap_after_head = 6 * mm
    header_block_h = 16  # px-ish in reportlab points; we use simple offsets below

    def draw_page_header():
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x0, y_top, title or "Gruppförteckning")

        c.setFont("Helvetica", 9)
        c.setFillGray(0.3)
        c.drawString(x0, y_top - 12, "Automatiskt genererad från TSV")
        c.setFillGray(0)

        c.setFont("Helvetica", 9)
        c.setFillGray(0.3)
        c.drawRightString(x1, y_top, f"Datum: {date_str}")
        c.drawRightString(x1, y_top - 12, f"Rader: {len(rows)}")
        c.setFillGray(0)

    def draw_table_header(y):
        # Header background
        c.setFillGray(0.95)
        c.rect(table_left, y - header_h, table_width, header_h, stroke=0, fill=1)
        c.setFillGray(0)

        # Thick line under header
        c.setLineWidth(2)
        c.line(table_left, y - header_h, table_right, y - header_h)

        # Vertical divider (thin)
        c.setLineWidth(1)
        c.line(table_left + col1_w, y, table_left + col1_w, y - header_h)

        # Header text
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(table_left + col1_w / 2, y - header_h + 2.2 * mm, "Grupp nr")
        c.drawString(table_left + col1_w + 3 * mm, y - header_h + 2.2 * mm, "Gruppens omfattning")

    def draw_outer_box(y_top_box, y_bottom_box):
        c.setLineWidth(2)
        c.rect(table_left, y_bottom_box, table_width, y_top_box - y_bottom_box, stroke=1, fill=0)

    # First page
    draw_page_header()

    table_top = y_top - 30  # below header
    y = table_top
    box_top = table_top

    draw_table_header(y)
    y -= header_h

    footer_space = 12 * mm
    min_y = margin + footer_space

    c.setFont("Helvetica", 9)

    for gid, desc in rows:
        # Page break
        if y - row_h < min_y:
            # close box on current page
            draw_outer_box(box_top, y)

            c.showPage()
            # reset page coords
            page_w, page_h = A4
            x0 = margin
            x1 = page_w - margin
            y_top = page_h - margin

            draw_page_header()

            table_top = y_top - 30
            y = table_top
            box_top = table_top

            draw_table_header(y)
            y -= header_h

            c.setFont("Helvetica", 9)

        # Row lines
        c.setLineWidth(1)
        c.line(table_left, y - row_h, table_right, y - row_h)
        c.line(table_left + col1_w, y, table_left + col1_w, y - row_h)

        # Cell text
        gid_txt = (gid or "").strip()
        desc_txt = (desc or "").strip()

        # Minimalistisk: klipp långa texter (kan byggas ut till word-wrap senare)
        max_chars = 110
        if len(desc_txt) > max_chars:
            desc_txt = desc_txt[: max_chars - 1] + "…"

        c.drawCentredString(table_left + col1_w / 2, y - row_h + 2.2 * mm, gid_txt)
        c.drawString(table_left + col1_w + 3 * mm, y - row_h + 2.2 * mm, desc_txt)

        y -= row_h

    # Close final box
    draw_outer_box(box_top, y)

    c.save()
    return buf.getvalue()


# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("Central-motor")
st.caption(CONTRACT)

with st.expander("Projektinfo (för filnamn)", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input("Projektnamn", value=st.session_state.get("project_name", ""))
    with col2:
        panel_name = st.text_input("Central / blad (valfritt)", value=st.session_state.get("panel_name", ""))

    st.session_state["project_name"] = project_name
    st.session_state["panel_name"] = panel_name

    st.toggle("Rubrik i export", value=True, key="include_header")

if "raw_tsv" not in st.session_state:
    st.session_state.raw_tsv = ""

tab_in, tab_out, tab_adv = st.tabs(["IN (tolkning + TSV)", "UT (preview/export)", "Avancerat"])

# IN
with tab_in:
    st.subheader("1) Prompt till ChatGPT")
    st.caption("Kopiera detta och använd när du skickar in bilder.")
    st.code(INTERPRETATION_PROMPT, language=None)

    st.divider()

    st.subheader("2) Klistra in TSV")
    st.session_state.raw_tsv = st.text_area(
        "TSV",
        value=st.session_state.raw_tsv,
        height=300,
        label_visibility="collapsed",
        placeholder="ID<TAB>Benämning<TAB>Meta",
    )

    if st.button("Rensa TSV", use_container_width=True):
        st.session_state.raw_tsv = ""
        st.rerun()

# Parse once
df = parse_tsv(st.session_state.raw_tsv)

# UT
with tab_out:
    st.subheader("Preview")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    tsv_out = df_to_tsv(df, include_header=st.session_state.get("include_header", True))

    st.subheader("TSV ut")
    st.caption("Tryck på kopiera-ikonen i högra hörnet.")
    st.code(tsv_out, language=None)

    filename = build_filename(
        project=st.session_state.get("project_name", ""),
        panel=st.session_state.get("panel_name", ""),
    )
    st.caption(f"Filnamn: `{filename}`")

    st.download_button(
        "Ladda ner TSV",
        data=tsv_out.encode("utf-8"),
        file_name=filename,
        mime="text/tab-separated-values",
        use_container_width=True,
    )

    st.divider()
    st.subheader("Rapport (PDF)")

    if df.shape[0] == 0:
        st.caption("Ingen data att generera rapport från.")
    else:
        title = (st.session_state.get("project_name", "").strip() or "Gruppförteckning")
        pdf_bytes = build_report_pdf_bytes(df=df, title=title)

        report_pdf_name = build_filename(
            project=st.session_state.get("project_name", "") or "rapport",
            panel=(st.session_state.get("panel_name", "") or "") + "__rapport",
        ).replace(".tsv", ".pdf")

        st.download_button(
            "Ladda ner rapport (PDF)",
            data=pdf_bytes,
            file_name=report_pdf_name,
            mime="application/pdf",
            use_container_width=True,
        )

# Avancerat
with tab_adv:
    st.write("Endast om du verkligen vill redigera i tabellform (mobil kan vara seg).")

    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("ID"),
            "Benämning": st.column_config.TextColumn("Benämning"),
            "Meta": st.column_config.TextColumn("Meta"),
        },
        key="editor",
    )

    edited = edited.fillna("").astype(str)

    st.divider()
    st.write("Vill du ta med ändringar tillbaka till IN-fliken?")
    st.code(df_to_tsv(edited, include_header=True), language=None)
