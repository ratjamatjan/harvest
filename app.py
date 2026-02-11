import io
import re
import unicodedata
import html
from datetime import datetime

import pandas as pd
import streamlit as st


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
# Helpers
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


def build_report_html(df: pd.DataFrame, title: str) -> str:
    # Rapport tar bara 2 kolumner: ID och Benämning
    rows = df[["ID", "Benämning"]].fillna("").astype(str).values.tolist()

    def esc(x: str) -> str:
        return html.escape(x or "")

    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{esc(title)}</title>
<style>
  @page {{ size: A4; margin: 0; }}
  body {{ margin:0; background:#fff; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; color:#000; }}
  .page {{ width: 210mm; min-height: 297mm; padding: 12mm; box-sizing: border-box; }}
  .head {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 6mm; }}
  h1 {{ margin:0; font-size:16px; font-weight:700; }}
  .meta {{ font-size:12px; color:#444; text-align:right; line-height:1.5; white-space:nowrap; }}
  .meta b {{ color:#000; font-weight:600; }}

  table {{ width:100%; border-collapse:collapse; table-layout:fixed; border:2px solid #000; font-size:12px; }}
  thead th {{
    border-right:1px solid #000;
    border-bottom:2px solid #000;
    padding:6px 8px;
    background:#f2f2f2;
    font-weight:700;
  }}
  thead th:last-child {{ border-right:0; }}
  tbody td {{
    border-right:1px solid #000;
    border-bottom:1px solid #000;
    padding:6px 8px;
    vertical-align:top;
    word-wrap:break-word;
  }}
  tbody tr:last-child td {{ border-bottom:0; }}
  tbody td:last-child {{ border-right:0; }}

  .col-group {{ width:18mm; text-align:center; }}
  .col-desc {{ width:auto; }}

  .printbar {{
    position: fixed; right: 12mm; bottom: 12mm;
    font-size: 12px; color:#444;
  }}
  .btn {{
    border:1px solid #ddd; padding:8px 10px; border-radius:10px;
    background:#fff; cursor:pointer;
  }}

  @media print {{
    .printbar {{ display:none; }}
  }}
</style>
</head>
<body>
  <div class="page">
    <div class="head">
      <div>
        <h1>{esc(title)}</h1>
        <div style="margin-top:2mm;font-size:12px;color:#444">Automatiskt genererad från TSV</div>
      </div>
      <div class="meta">
        <div>Datum: <b>{datetime.now().strftime("%Y-%m-%d")}</b></div>
        <div>Rader: <b>{len(rows)}</b></div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th class="col-group">Grupp nr</th>
          <th class="col-desc">Gruppens omfattning</th>
        </tr>
      </thead>
      <tbody>
        {''.join(f"<tr><td class='col-group'>{esc(r[0])}</td><td class='col-desc'>{esc(r[1])}</td></tr>" for r in rows)}
      </tbody>
    </table>

    <div class="printbar">
      <button class="btn" onclick="window.print()">Skriv ut / Spara som PDF</button>
    </div>
  </div>
</body>
</html>"""


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


# TSV input state (start tomt)
if "raw_tsv" not in st.session_state:
    st.session_state.raw_tsv = ""


tab_in, tab_out, tab_adv = st.tabs(["IN (tolkning + TSV)", "UT (preview/export)", "Avancerat"])


# --------------------------------------------------
# IN
# --------------------------------------------------
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


# --------------------------------------------------
# Parse once
# --------------------------------------------------
df = parse_tsv(st.session_state.raw_tsv)


# --------------------------------------------------
# UT
# --------------------------------------------------
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
    st.subheader("Rapport (PDF via utskrift)")

    if st.button("Generera rapport", use_container_width=True):
        title = (st.session_state.get("project_name", "").strip() or "Gruppförteckning")
        st.session_state["report_html"] = build_report_html(df=df, title=title)

    if "report_html" in st.session_state:
        report_html = st.session_state["report_html"]

        st.components.v1.html(report_html, height=900, scrolling=True)

        report_name = build_filename(
            project=st.session_state.get("project_name", "") or "rapport",
            panel=(st.session_state.get("panel_name", "") or "") + "__rapport",
        ).replace(".tsv", ".html")

        st.download_button(
            "Ladda ner rapport (HTML)",
            data=report_html.encode("utf-8"),
            file_name=report_name,
            mime="text/html",
            use_container_width=True,
        )


# --------------------------------------------------
# Avancerat
# --------------------------------------------------
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
