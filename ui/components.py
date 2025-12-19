import streamlit as st
from datetime import date
from decimal import Decimal
from utils.rounding import D, r2

def number_money(label, value, key):
    return st.number_input(label, value=float(value), step=1000.0, format="%.2f", key=key)

def number_rate_decimal(label, value, key):
    return st.number_input(label, value=float(value), step=0.000001, format="%.6f", key=key)

def number_rate_percent(label, value, key):
    return st.number_input(label, value=float(value), step=0.01, format="%.2f", key=key)

def abonos_editor():
    st.subheader("Abonos")


    import pandas as pd

    # Helper function to get default empty dataframe
    def get_default_abonos_df():
        return pd.DataFrame(
            [{"Fecha": None, "Abono Capital": 0.0, "Abono Int Rem": 0.0, "Abono Int Mor": 0.0}]
        )

    # Initialize or ensure abonos is a DataFrame
    if "abonos" not in st.session_state:
        st.session_state["abonos"] = get_default_abonos_df()
    
    # Ensure it's a DataFrame (recover from list or dict state)
    val = st.session_state["abonos"]
    if not isinstance(val, pd.DataFrame):
        if isinstance(val, list):
            st.session_state["abonos"] = pd.DataFrame(val)
        else:
            # If it's a dict or something else unexpected, try to convert or reset
            try:
                # If it's a dict, maybe it's {index: {col: val}}, so from_dict might work
                st.session_state["abonos"] = pd.DataFrame.from_dict(val) if isinstance(val, dict) else get_default_abonos_df()
            except:
                st.session_state["abonos"] = get_default_abonos_df()

    # Sanitize Fecha column using methods safe for DataFrames
    df = st.session_state["abonos"]
    if "Fecha" in df.columns:
        # Convert to datetime objects where possible, coercion errors become NaT (None)
        # We process manually to ensure compatibility with DateColumn which expects date objects or None
        def parse_date_entry(val):
            if val is None or val == "":
                return None
            if isinstance(val, (date, datetime)):
                return val if isinstance(val, date) else val.date()
            if isinstance(val, str):
                v = val.strip()
                if not v:
                    return None
                try:
                    return date.fromisoformat(v)
                except ValueError:
                    try:
                        return datetime.strptime(v, "%d/%m/%Y").date()
                    except ValueError:
                        return None
            return None

        # Apply only if needed (check dtype or just apply safe mapping)
        st.session_state["abonos"]["Fecha"] = st.session_state["abonos"]["Fecha"].apply(parse_date_entry)

    def on_change_abonos():
        # Sync the widget state to the main abonos state
        state = st.session_state["abonos_editor_widget"]
        if state is not None:
             st.session_state["abonos"] = state

    edited = st.data_editor(
        st.session_state["abonos"],
        column_config={
            "Fecha": st.column_config.DateColumn(
                "Fecha",
                help="Seleccione la fecha del abono",
                format="DD/MM/YYYY"
            ),
            "Abono Capital": st.column_config.NumberColumn(
                "Abono Capital",
                min_value=0,
                format="$%.2f"
            ),
            "Abono Int Rem": st.column_config.NumberColumn(
                "Abono Int Rem",
                min_value=0,
                format="$%.2f"
            ),
            "Abono Int Mor": st.column_config.NumberColumn(
                "Abono Int Mor",
                min_value=0,
                format="$%.2f"
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        key="abonos_editor_widget",
        on_change=on_change_abonos
    )
    
    return edited


    return edited


    return edited


def tasas_editor():
    """
    Componente para editar las tasas separadas en dos tablas.
    """
    import pandas as pd
    from datetime import date, datetime
    import calendar

    # --- Helpers ---
    def get_end_of_month(d: date) -> date:
        if not d: return None
        try:
            last_day = calendar.monthrange(d.year, d.month)[1]
            return date(d.year, d.month, last_day)
        except:
            return None

    # --- Remuneratorio ---
    st.markdown("#### Histórico Tasas Remuneratorias")
    
    defaults_rem = {"Fecha Inicio": None, "Fecha Fin": None, "Tasa Rem EA (%)": 0.0}
    if "tasas_rem_vars" not in st.session_state:
        st.session_state["tasas_rem_vars"] = pd.DataFrame([defaults_rem])

    # data_editor uses the state directly
    edited_rem = st.data_editor(
        st.session_state["tasas_rem_vars"],
        column_config={
            "Fecha Inicio": st.column_config.DateColumn("Fecha Inicio", format="DD/MM/YYYY"),
            "Fecha Fin": st.column_config.DateColumn("Fecha Fin", format="DD/MM/YYYY"),
            "Tasa Rem EA (%)": st.column_config.NumberColumn("Tasa Rem EA (%)", format="%.4f", min_value=0.0)
        },
        num_rows="dynamic",
        use_container_width=True,
        key="tasas_rem_editor_widget"
    )
    
    if edited_rem is not None and not edited_rem.equals(st.session_state["tasas_rem_vars"]):
        # Clean data before saving
        for col in ["Fecha Inicio", "Fecha Fin"]:
            if col in edited_rem.columns:
                 edited_rem[col] = pd.to_datetime(edited_rem[col], errors='coerce').dt.date
        
        st.session_state["tasas_rem_vars"] = edited_rem
        # st.rerun() REMOVED to avoid double-reload feeling


    # --- Moratorio ---
    st.markdown("#### Histórico Tasas Usura/Mora")

    defaults_mora = {"Fecha Inicio": None, "Fecha Fin": None, "Tasa Mora EA (%)": 0.0}
    if "tasas_mora_vars" not in st.session_state:
        st.session_state["tasas_mora_vars"] = pd.DataFrame([defaults_mora])

    edited_mora = st.data_editor(
        st.session_state["tasas_mora_vars"],
        column_config={
            "Fecha Inicio": st.column_config.DateColumn("Fecha Inicio", format="DD/MM/YYYY"),
            "Fecha Fin": st.column_config.DateColumn("Fecha Fin", format="DD/MM/YYYY"),
            "Tasa Mora EA (%)": st.column_config.NumberColumn("Tasa Mora EA (%)", format="%.4f", min_value=0.0)
        },
        num_rows="dynamic",
        use_container_width=True,
        key="tasas_mora_editor_widget"
    )

    if edited_mora is not None and not edited_mora.equals(st.session_state["tasas_mora_vars"]):
        # Clean data before saving
        for col in ["Fecha Inicio", "Fecha Fin"]:
            if col in edited_mora.columns:
                 edited_mora[col] = pd.to_datetime(edited_mora[col], errors='coerce').dt.date
        
        st.session_state["tasas_mora_vars"] = edited_mora
        # st.rerun() REMOVED

    return None
