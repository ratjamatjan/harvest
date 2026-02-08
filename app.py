import io
import re
import unicodedata
from datetime import datetime

import pandas as pd
import streamlit as st


# --------------------------------------------------
# App config
# --------------------------------------------------
st.set_page_config(page_title="Central-motor (TSV)", layout="centered")

CONTRACT = "Kontrakt: ID, Benämning, Meta • Tomma fält OK • Ingen validering • Ordningen betyder något"


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
    return out.to_csv(
        sep="\t",
        index=False,
        header=include_header,
        lineterminator="\n",
    )


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


# --------------------------------------------------
# UI
# --------------------------------------------------
st.title("Central-motor")
st.caption(CONTRACT)

# Projektinfo
with st.expander("Projektinfo (för filnamn)", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        project_name = st.text_input(
            "Projektnamn",
            value=st.session_state.get("project_name", ""),
        )
    with col2:
        panel_name = st.text_input(
            "Central / blad (valfritt)",
            value=st.session_state.get("panel_name", ""),
        )

    st.session_state["project_name"] = project_name
    st.session_state["panel_name"] = panel_name

    st.toggle("Rubrik i export", value=True, key="include_header")


# TSV input state (start TOMT)
if "raw_tsv" not in st.session_state:
    st.session_state.raw_tsv = ""


tab_in, tab_out, tab_adv = st.tabs(
    ["IN (klistra/skriv)", "UT (preview/export)", "Avancerat"]
)

# --------------------------------------------------
# IN
# --------------------------------------------------
with tab_in:
    st.write("Klistra in eller skriv TSV här. (Tab mellan kolumner.)")

    st.session_state.raw_tsv = st.text_area(
        "TSV",
        value=st.session_state.raw_tsv,
        height=360,
        label_visibility="collapsed",
        placeholder="ID<TAB>Benämning<TAB>Meta",
    )

    if st.button("Rensa", use_container_width=True):
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

    tsv_out = df_to_tsv(
        df,
        include_header=st.session_state.get("include_header", True),
    )

    st.subheader("TSV ut")
    st.caption("Tryck på kopiera-ikonen i högra hörnet av rutan.")
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


# --------------------------------------------------
# Avancerat
# --------------------------------------------------
with tab_adv:
    st.write(
        "Använd bara om du verkligen vill redigera i tabell-form. "
        "(Mobil kan vara seg.)"
    )

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
    st.write(
        "Vill du ta med tabelländringar tillbaka till IN-fliken? "
        "Kopiera TSV:t nedan och klistra in där."
    )
    st.code(df_to_tsv(edited, include_header=True), language=None)
