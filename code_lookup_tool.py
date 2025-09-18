import streamlit as st
import pandas as pd
from difflib import get_close_matches

st.set_page_config(page_title="Part Code Lookup", layout="wide")

@st.cache_data
def load_mapping():
    df = pd.read_excel("mapping.xlsx")
    df.columns = df.columns.str.strip()

    # Ensure Notes exists & is string
    if 'Notes' not in df.columns:
        df['Notes'] = ""
    df['Legacy Code'] = df['Legacy Code'].astype(str)
    df['New Code'] = df['New Code'].astype(str)
    df['Notes'] = df['Notes'].fillna("").astype(str)

    # Move any "Note: ..." from Legacy Code into Notes, then blank Legacy Code
    note_mask = df['Legacy Code'].str.strip().str.lower().str.startswith('note:')
    df.loc[note_mask & (df['Notes'].str.strip() == ""), 'Notes'] = df.loc[note_mask, 'Legacy Code']
    df.loc[note_mask, 'Legacy Code'] = ""

    # Lowercase helpers
    df['Legacy_LC'] = df['Legacy Code'].str.lower()
    df['New_LC'] = df['New Code'].str.lower()

    # Keep core columns; don't drop rows just because Notes is empty
    return df[['Legacy Code', 'New Code', 'Notes', 'Legacy_LC', 'New_LC']].dropna(subset=['Legacy Code', 'New Code'])

def find_exact_match(df, code):
    """Return (legacy, current, match_type, confidence, notes) or Nones if not found."""
    code_lc = code.lower()
    if code_lc in df['Legacy_LC'].values:
        row = df[df['Legacy_LC'] == code_lc].iloc[0]
        return row['Legacy Code'], row['New Code'], "Legacy", 100, row['Notes']
    if code_lc in df['New_LC'].values:
        row = df[df['New_LC'] == code_lc].iloc[0]
        return row['Legacy Code'], row['New Code'], "Current", 100, row['Notes']
    return None, None, None, 0, ""

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

# NEW: duplicate check based on whatever the user typed (legacy OR new)
def get_multiples_if_mnp_by_input(df, user_code):
    if not user_code:
        return None
    key = str(user_code).strip().lower()
    hits = df[(df['Legacy_LC'] == key) | (df['New_LC'] == key)]
    if len(hits) > 1 and hits['New Code'].str.upper().str.startswith('MNP').any():
        return hits[['Legacy Code', 'New Code', 'Notes']].drop_duplicates().reset_index(drop=True)
    return None

st.title("🔁 Legacy ↔ Current Part Code Lookup")

df_map = load_mapping()

st.subheader("🔍 Single Code Lookup")
user_code = st.text_input("Enter a legacy or current part code").strip()

if user_code:
    legacy, current, match_type, confidence, note = find_exact_match(df_map, user_code)
    if legacy is not None and current is not None and match_type:
        # Success banner (full-width)
        st.markdown(
            f"<div style='padding: 0.5em; background-color: #e6ffe6; border-left: 5px solid #33cc33;'>"
            f"<strong>Match found:</strong> {match_type} code (confidence {confidence}%)</div>",
            unsafe_allow_html=True
        )

        # Two aligned columns
        col1, col2 = st.columns(2)

        # Duplicate check now based on the *entered* code
        dups = get_multiples_if_mnp_by_input(df_map, user_code)

        if dups is not None:
            with col1:
                st.markdown("**Legacy Code:**")
                st.code("Duplicates found please see below", line_numbers=False)
            with col2:
                st.markdown("**Current Code:**")
                st.code("Duplicates found please see below", line_numbers=False)

            st.markdown(
                "<div style='padding: 0.5em; background-color: #fff5cc; border-left: 5px solid #ffcc00;'>"
                "<strong>Multiple returned, use region specific.</strong></div>",
                unsafe_allow_html=True
            )
            st.dataframe(dups, use_container_width=True)

        else:
            # Non-duplicate: show aligned code blocks + Notes (if present)
            with col1:
                st.markdown("**Legacy Code:**")
                st.code(legacy if legacy else "(none)", line_numbers=False)
            with col2:
                st.markdown("**Current Code:**")
                st.code(current, line_numbers=False)

            if note and note.strip():
                st.markdown("**Notes:**")
                st.code(note.strip(), line_numbers=False)

    else:
        st.markdown(
            "<div style='padding: 0.5em; background-color: #fff5cc; border-left: 5px solid #ffcc00;'>"
            "<strong>No exact match found.</strong> Here are some close suggestions:</div>",
            unsafe_allow_html=True
        )
        fuzzy_matches = find_fuzzy_matches(df_map, user_code)
        if fuzzy_matches:
            fuzzy_df = pd.DataFrame(fuzzy_matches)
            st.dataframe(fuzzy_df, use_container_width=True)
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
    df_bulk.columns = df_bulk.columns.str.strip()
    col_candidates = [
        'Code', 'code', 'part code', 'Part Code', 'Part_Code',
        'codes', 'Codes', 'SKU', 'Order Code', 'order code', 'Order_Code'
    ]
    matched_col = next((col for col in df_bulk.columns if col.lower() in [c.lower() for c in col_candidates]), None)

    if not matched_col:
        st.error("❌ CSV must contain a column like 'Code'. Found columns: " + ", ".join(df_bulk.columns))
    else:
        df_bulk['Code'] = df_bulk[matched_col].astype(str)
        results = []

        for code in df_bulk['Code']:
            legacy, current, match_type, confidence, note = find_exact_match(df_map, code)

            # Expand multiples based on the *entered* value
            expanded = False
            dups = get_multiples_if_mnp_by_input(df_map, code)
            if dups is not None:
                for _, r in dups.iterrows():
                    results.append({
                        "Input Code": code,
                        "Match Type": "Multiple",
                        "Legacy Code": r["Legacy Code"],
                        "Current Code": r["New Code"],
                        "Notes": r["Notes"],
                        "Confidence": confidence,
                        "Note": "Multiple returned, use region specific."
                    })
                expanded = True

            if not expanded:
                results.append({
                    "Input Code": code,
                    "Match Type": match_type or "Not Found",
                    "Legacy Code": legacy or "",
                    "Current Code": current or "",
                    "Notes": note if (legacy is not None and current is not None and match_type) else "",
                    "Confidence": confidence,
                    "Note": ""
                })

        df_results = pd.DataFrame(
            results,
            columns=["Input Code", "Match Type", "Legacy Code", "Current Code", "Notes", "Confidence", "Note"]
        )
        st.download_button(
            "📥 Download Results",
            df_results.to_csv(index=False),
            "lookup_results.csv",
            "text/csv"
        )
        st.dataframe(df_results, use_container_width=True)
