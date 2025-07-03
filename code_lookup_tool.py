
import streamlit as st
import pandas as pd
from difflib import get_close_matches

st.set_page_config(page_title="Part Code Lookup", layout="wide")

@st.cache_data
def load_mapping():
    df = pd.read_excel("mapping.xlsx")
    df.columns = df.columns.str.strip()
    df['Legacy_LC'] = df['Legacy Code'].str.lower()
    df['New_LC'] = df['New Code'].str.lower()
    return df[['Legacy Code', 'New Code', 'Legacy_LC', 'New_LC']].dropna()

def find_exact_match(df, code):
    code_lc = code.lower()
    if code_lc in df['Legacy_LC'].values:
        row = df[df['Legacy_LC'] == code_lc].iloc[0]
        return row['Legacy Code'], row['New Code'], "Legacy", 100

    if code_lc in df['New_LC'].values:
        row = df[df['New_LC'] == code_lc].iloc[0]
        return row['Legacy Code'], row['New Code'], "Current", 100

    return None, None, None, 0

def find_fuzzy_matches(df, code, n=5, cutoff=0.6):
    code_lc = code.lower()
    all_codes_lc = pd.concat([df['Legacy_LC'], df['New_LC']]).dropna().unique()
    close = get_close_matches(code_lc, all_codes_lc, n=n, cutoff=cutoff)
    results = []
    for match in close:
        row = df[(df['Legacy_LC'] == match) | (df['New_LC'] == match)].iloc[0]
        match_type = "Legacy" if row['Legacy_LC'] == match else "Current"
        results.append({
            "Matched Code": row['Legacy Code'] if match_type == "Legacy" else row['New Code'],
            "Legacy Code": row['Legacy Code'],
            "Current Code": row['New Code'],
            "Match Type": match_type
        })
    return results

st.title("🔁 Legacy ↔ Current Part Code Lookup")

df_map = load_mapping()

st.subheader("🔍 Single Code Lookup")
user_code = st.text_input("Enter a legacy or current part code").strip()

if user_code:
    legacy, current, match_type, confidence = find_exact_match(df_map, user_code)
    if legacy and current:
        st.markdown(
    f"<div style='padding: 0.5em; background-color: #e6ffe6; border-left: 5px solid #33cc33;'>"
    f"<strong>Match found:</strong> {match_type} code "
    f"(confidence {confidence}%)</div>",
    unsafe_allow_html=True
)
        col1, col2 = st.columns(2)
        col1.markdown(f"**Legacy Code:** `{legacy}`")
        col2.markdown(f"**Current Code:** `{current}`")
        col1.button("📋 Copy Legacy", on_click=st.session_state.setdefault, args=("copy", legacy))
        col2.button("📋 Copy Current", on_click=st.session_state.setdefault, args=("copy", current))
    else:
        st.markdown(
    "<div style='padding: 0.5em; background-color: #fff5cc; border-left: 5px solid #ffcc00;'>"
    "<strong>No exact match found.</strong> Here are some close suggestions:</div>",
    unsafe_allow_html=True
)
        fuzzy_matches = find_fuzzy_matches(df_map, user_code)
        if fuzzy_matches:
            fuzzy_df = pd.DataFrame(fuzzy_matches)
            st.dataframe(fuzzy_df)
        else:
            st.markdown(
    "<div style='padding: 0.5em; background-color: #ffe6e6; border-left: 5px solid #ff3333;'>"
    "<strong>No similar codes found.</strong></div>",
    unsafe_allow_html=True
)

st.divider()
st.subheader("📄 Bulk Lookup (CSV Upload)")
bulk_file = st.file_uploader("Upload CSV with column 'Code' for bulk lookup", type=["csv"], key="bulk")
if bulk_file:
    df_bulk = pd.read_csv(bulk_file)
    df_bulk['Code'] = df_bulk['Code'].astype(str)
    results = []

    for code in df_bulk['Code']:
        legacy, current, match_type, confidence = find_exact_match(df_map, code)
        if not legacy and not current:
            close = get_close_matches(code.lower(), pd.concat([df_map['Legacy_LC'], df_map['New_LC']]).dropna().unique(), n=1, cutoff=0.6)
            if close:
                row = df_map[(df_map['Legacy_LC'] == close[0]) | (df_map['New_LC'] == close[0])].iloc[0]
                legacy, current = row['Legacy Code'], row['New Code']
                match_type = "Fuzzy"
                confidence = 80
        results.append({
            "Input Code": code,
            "Match Type": match_type or "Not Found",
            "Legacy Code": legacy or "",
            "Current Code": current or "",
            "Confidence": confidence
        })

    st.download_button("📥 Download Results", pd.DataFrame(results).to_csv(index=False), "lookup_results.csv", "text/csv")
    st.dataframe(pd.DataFrame(results))
