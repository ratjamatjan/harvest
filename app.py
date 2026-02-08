import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Central-motor (TSV)", layout="centered")

CONTRACT = "Kontrakt: ID, Benämning, Meta • Tomma fält OK • Ingen validering • Ordningen betyder något"

DEFAULT_TSV = (
    "ID\tBenämning\tMeta\n"
    "1\tBelysning hall\t\n"
    "2\tVägguttag vardagsrum\t\n"
    "6-9\tSpis\t3-fas\n"
    "JFB\tGrupper 1–17\tJordfelsbrytare\n"
)

def parse_tsv(tsv_text: str) -> pd.DataFrame:
    tsv_text = (tsv_text or "").strip("\n\r ")
    if not tsv_text:
        return pd.DataFrame(columns=["ID", "Benämning", "Meta"])

    # Försök läsa med rubrik
    try:
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t", dtype=str)
    except Exception:
        df = pd.DataFrame()

    # Om inte exakt 3 kolumner: läs utan rubrik
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

# --- Header (mobil)
st.title("Central-motor")
st.caption(CONTRACT)

if "raw_tsv" not in st.session_state:
    st.session_state.raw_tsv = DEFAULT_TSV

tab_in, tab_out, tab_adv = st.tabs(["IN (klistra/skriv)", "UT (preview/export)", "Avancerat"])

# --- IN: stor editor (mobilvänlig)
with tab_in:
    st.write("Klistra in eller skriv TSV här. (Tab mellan kolumner.)")
    st.session_state.raw_tsv = st.text_area(
        "TSV",
        value=st.session_state.raw_tsv,
        height=360,
        label_visibility="collapsed",
        placeholder="ID<TAB>Benämning<TAB>Meta",
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Rensa", use_container_width=True):
            st.session_state.raw_tsv = "ID\tBenämning\tMeta\n"
            st.rerun()
    with col2:
        if st.button("Exempel", use_container_width=True):
            st.session_state.raw_tsv = DEFAULT_TSV
            st.rerun()
    with col3:
        include_header = st.toggle("Rubrik i export", value=True)

# Vi parsar en gång och återanvänder i UT/Avancerat
df = parse_tsv(st.session_state.raw_tsv)
# include_header behöver finnas även om man inte varit i tab_in ännu
include_header = st.session_state.get("Rubrik i export", True)
# Streamlit toggle sparas inte automatiskt med label; vi tar en säkrare approach:
# Om användaren varit i tab_in så finns toggle-värdet i "include_header" variabeln där.
# Men på vissa mobiler kan tabs rendera om. Därför erbjuder vi togglen igen i UT.
# (se nedan)

# --- UT: preview + copy/export (one tap)
with tab_out:
    st.subheader("Preview")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    include_header_out = st.toggle("Rubrik i export", value=True)
    tsv_out = df_to_tsv(df, include_header=include_header_out)

    st.subheader("TSV ut")
    st.caption("Tryck på kopiera-ikonen i högra hörnet av rutan.")
    # st.code har inbyggd copy-knapp (bra på mobil)
    st.code(tsv_out, language=None)

    st.download_button(
        "Ladda ner central.tsv",
        data=tsv_out.encode("utf-8"),
        file_name="central.tsv",
        mime="text/tab-separated-values",
        use_container_width=True,
    )

# --- Avancerat: data_editor vid behov (men inte default på mobil)
with tab_adv:
    st.write("Använd bara om du verkligen vill redigera i tabell-form. (Mobil kan vara seg.)")
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
    st.write("Uppdatera TSV i IN-fliken med detta om du vill:")
    st.code(df_to_tsv(edited, include_header=True), language=None)
