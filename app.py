import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Central-motor (TSV)", layout="wide")

st.title("Central-motor (v1)")
st.caption("Kontrakt: ID, Benämning, Meta • Tomma fält OK • Ingen validering • Ordningen betyder något")

DEFAULT_TSV = (
    "ID\tBenämning\tMeta\n"
    "1\tBelysning hall\t\n"
    "2\tVägguttag vardagsrum\t\n"
    "6-9\tSpis\t3-fas\n"
    "JFB\tGrupper 1–17\tJordfelsbrytare\n"
)

def parse_tsv(tsv_text: str) -> pd.DataFrame:
    # Läs TSV robust: accepterar både med/utan rubrikrad.
    tsv_text = (tsv_text or "").strip("\n\r\t ")
    if not tsv_text:
        return pd.DataFrame(columns=["ID", "Benämning", "Meta"])

    # Försök läsa med rubrik
    try:
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t", dtype=str)
    except Exception:
        df = pd.DataFrame()

    # Om det inte blev 3 kolumner, läs utan rubrik och sätt kolumnnamn
    if df.shape[1] != 3:
        df = pd.read_csv(io.StringIO(tsv_text), sep="\t", header=None, dtype=str)
        # Fyll/trimma till exakt 3 kolumner
        while df.shape[1] < 3:
            df[df.shape[1]] = ""
        if df.shape[1] > 3:
            df = df.iloc[:, :3]
        df.columns = ["ID", "Benämning", "Meta"]
    else:
        # Se till att kolumnnamnen är exakt våra (om användaren skrivit något annat)
        df = df.iloc[:, :3]
        df.columns = ["ID", "Benämning", "Meta"]

    # Normalisera
    df = df.fillna("")
    df["ID"] = df["ID"].astype(str).str.strip()
    df["Benämning"] = df["Benämning"].astype(str).str.strip()
    df["Meta"] = df["Meta"].astype(str).str.strip()
    return df

def df_to_tsv(df: pd.DataFrame, include_header: bool = True) -> str:
    out = df.copy()
    for col in ["ID", "Benämning", "Meta"]:
        if col not in out.columns:
            out[col] = ""
    out = out[["ID", "Benämning", "Meta"]].fillna("").astype(str)
    return out.to_csv(sep="\t", index=False, header=include_header, lineterminator="\n")

left, right = st.columns([1, 1], gap="large")

with left:
    st.subheader("1) Klistra in TSV")
    raw = st.text_area(
        "TSV (tab-separerat). Gärna med rubrikrad: ID, Benämning, Meta",
        value=DEFAULT_TSV,
        height=260,
    )
    include_header = st.checkbox("Inkludera rubrikrad vid export", value=True)

    df = parse_tsv(raw)

    st.divider()
    st.subheader("3) Export")
    tsv_out = df_to_tsv(df, include_header=include_header)

    st.text_area("TSV ut (kopiera)", value=tsv_out, height=200)
    st.download_button(
        label="Ladda ner TSV",
        data=tsv_out.encode("utf-8"),
        file_name="central.tsv",
        mime="text/tab-separated-values",
        use_container_width=True,
    )

with right:
    st.subheader("2) Redigera tabellen")
    st.caption("Du kan ändra celler direkt. Lägg till rader via + längst ner i tabellen.")
    edited = st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("ID", help="Fri text: 15.3, 6-9, Kabel 12, Spis..."),
            "Benämning": st.column_config.TextColumn("Benämning", help="Fri beskrivning"),
            "Meta": st.column_config.TextColumn("Meta", help="Valfritt: 10A, 1.5mm², JFB1, fas, kabelnr..."),
        },
        key="editor",
    )

    # Sync tillbaka till export
    df = edited.fillna("").astype(str)
    st.caption("Tips: håll 'Meta' som kommatecken-separerad fri text i v1 (t.ex. `10A, 1.5mm², JFB1`).")
