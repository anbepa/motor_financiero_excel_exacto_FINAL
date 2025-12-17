import streamlit as st
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import pandas as pd
from services.engine import Inputs, Abono, motor_completo
from ui.components import number_money, number_rate_decimal, number_rate_percent, abonos_editor
from utils.days import get_end_of_month

st.set_page_config(page_title="Motor Financiero Determinístico", layout="wide")
st.title("Simulador cargos SAF")

# --- Configuration Mode ---
config_mode = st.radio("Configuración de la Obligación", ["Manual", "Automático"], horizontal=True)

if config_mode == "Automático":
    col_id, col_btn = st.columns([1, 1])
    with col_id:
        obligation_id = st.text_input("ID de la Obligación")
    with col_btn:
        st.write("")
        st.write("")
        load_btn = st.button("Cargar Datos")
    
    if load_btn and obligation_id:
        try:
            from services.db_client import get_obligation_by_id, get_active_usury_rate_for_date
            
            # 1. Fetch Obligation Data
            ob_data = get_obligation_by_id(obligation_id)
            
            if ob_data:
                # Map DB fields to State
                # Ensure we handle decimals and dates correctly
                principal = Decimal(str(ob_data['principal_balance']))
                
                # Handle potentially different date formats (DB usually returns date or datetime)
                def to_date(d):
                    if hasattr(d, 'date'): return d.date()
                    if isinstance(d, date): return d
                    # naive fallback
                    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()

                f_vcto_total = to_date(ob_data['total_due_date'])
                f_vcto_neto = to_date(ob_data['net_due_date'])
                rem_rate_val = float(ob_data['remunerative_rate'])
                
                today_date = date.today()

                # Update Session State for scalar fields
                st.session_state["capital"] = float(principal) # Widget expects float
                st.session_state["fvt"] = f_vcto_total
                st.session_state["fvn"] = f_vcto_neto
                st.session_state["fa"] = today_date
                
                # 2. Generate Remunerative Rates (Net Due Date -> Total Due Date)
                # Split by month
                rem_ranges = []
                current_start = f_vcto_neto
                # If Rem logic: Start at Net Due, End at Total Due.
                target_end = f_vcto_total
                
                # Safety check: if net > total, just use one range or swap? Usually net <= total.
                # If they are same, range is 0 days?
                if current_start < target_end:
                    while current_start < target_end:
                        # End of this segment is end of month OR target_end, whichever is first
                        eom = get_end_of_month(current_start)
                        
                        # Careful: get_end_of_month returns the last day of THAT month.
                        # If target_end is BEFORE eom, we stop at target_end.
                        # If target_end is AFTER eom, we stop at eom.
                        
                        current_end = min(eom, target_end)
                        
                        # Use previous day rule if strictly following "until"? 
                        # Usually "Fecha Fin" is inclusive in this app logic (engine uses <=).
                        
                        rem_ranges.append({
                            "Fecha Inicio": current_start,
                            "Fecha Fin": current_end,
                            "Tasa Rem EA (%)": rem_rate_val
                        })
                        
                        # Next start is current_end + 1 day
                        current_start = current_end + timedelta(days=1)
                else:
                     rem_ranges.append({
                        "Fecha Inicio": f_vcto_neto,
                        "Fecha Fin": f_vcto_total,
                        "Tasa Rem EA (%)": rem_rate_val
                    })

                st.session_state["tasas_rem_vars"] = pd.DataFrame(rem_ranges)
                
                # 3. Generate Moratory Rates (Total Due Date -> Current Date/Today)
                mora_ranges = []
                mora_start = f_vcto_total
                mora_end_global = today_date
                
                # OPTIMIZATION: Fetch ALL rates for the range at once
                if mora_start <= mora_end_global:
                    from services.db_client import get_usury_rates
                    # Fetch rates starting slightly before to ensure coverage
                    query_start = mora_start - timedelta(days=32) 
                    rates_data = get_usury_rates(query_start, mora_end_global)
                    
                    # Convert to efficient lookup structure (DataFrame)
                    if rates_data:
                        df_rates = pd.DataFrame(rates_data)
                        df_rates['start_date'] = pd.to_datetime(df_rates['start_date']).dt.date
                        df_rates = df_rates.sort_values('start_date')
                    else:
                        df_rates = pd.DataFrame(columns=['start_date', 'value'])

                    curr_m = mora_start
                    while curr_m <= mora_end_global:
                        eom = get_end_of_month(curr_m)
                        seg_end = min(eom, mora_end_global)
                        
                        # Efficiently find rate active at curr_m
                        # Last rate where start_date <= curr_m
                        val_rate = 0.0
                        if not df_rates.empty:
                            valid_rates = df_rates[df_rates['start_date'] <= curr_m]
                            if not valid_rates.empty:
                                val_rate = float(valid_rates.iloc[-1]['value'])
                        
                        mora_ranges.append({
                            "Fecha Inicio": curr_m,
                            "Fecha Fin": seg_end,
                            "Tasa Mora EA (%)": val_rate
                        })
                        
                        curr_m = seg_end + timedelta(days=1)
                        
                st.session_state["tasas_mora_vars"] = pd.DataFrame(mora_ranges)
                
                st.success("Datos cargados correctamente desde BD.")
                # st.rerun() # Ensure clean rerun

        except Exception as e:
            st.error(f"Error cargando datos: {e}")
            st.error(f"Detalle: {str(e)}")


st.subheader("Configuración de la Obligación")
c1, c2, c3 = st.columns(3)
with c1:
    # Key 'capital' is already set in Session State above, 
    # but number_money sets key='capital'. Streamlit warns if we set default value AND key 
    # when key is already in session_state. 
    # If key is in session state, 'value' arg is ignored.
    capital = number_money("Capital Obligación", 0.0, "capital")
    fecha_vcto_neto = st.date_input("Fecha Vcto Neto", value=datetime.strptime("2025-11-25","%Y-%m-%d").date(), key="fvn")
with c2:
    # Removed single inputs
    fecha_vcto_total = st.date_input("Fecha Vcto Total", value=datetime.strptime("2025-12-01","%Y-%m-%d").date(), key="fvt")
with c3:
    # Removed single inputs
    fecha_actual = st.date_input("Fecha Actual/Corte", value=datetime.strptime("2025-12-16","%Y-%m-%d").date(), key="fa")

st.divider()

st.divider()
c_abonos, c_tasas = st.columns([1, 1])

with c_abonos:
    ab_rows = abonos_editor()

with c_tasas:
    from ui.components import tasas_editor
    tasas_editor() # Doesn't return rows anymore, updates session state directly

def parse_tasas_variables():
    # from services.engine import TasaChange (Removed)
    import pandas as pd

    # We need to construct a "master" list of changes or handle them separately in engine.
    # The current engine expects a list of TasaChange with specific dates.
    # But now we hold TWO separate lists of ranges.
    # To avoid rewriting the entire engine structure just yet, we can create a TasaChange object
    # for EVERY day in the ranges? No, that's inefficient.
    # Better: Update Inputs/Engine to accept "tasas_rem_vars" and "tasas_mora_vars" separately.
    # BUT, to stick to "TasaChange" request without big engine refactor, we can produce TasaChange objects.
    # HOWEVER, TasaChange currently couples Rem & Mora in one object per date. This is tricky if ranges overlap differently.
    # If ranges are different, we can't easily use "TasaChange" as (date, rem, mora).
    #
    # PROVISIONALLY: We will modify engine.py to accept separate lists if needed, OR we stick to the user request.
    # User asked for "gestor de tasa se maneje remuneratio y mora mora separados".
    # This implies independent timelines.
    # So we MUST decouple them in the Engine inputs.
    
    # Let's read the dataframes
    df_rem = st.session_state.get("tasas_rem_vars", pd.DataFrame())
    df_mora = st.session_state.get("tasas_mora_vars", pd.DataFrame())
    
    # Helper to parse DF to list of dicts with standarized keys/values
    def parse_df(df, rate_key):
        out = []
        if isinstance(df, list): df = pd.DataFrame(df)
        if df.empty: return []
        
        for _, r in df.iterrows():
            f_ini = r.get("Fecha Inicio")
            f_fin = r.get("Fecha Fin")
            try:
                rate_str = str(r.get(rate_key, 0)).replace(",", ".")
                rate_val = Decimal(rate_str) / Decimal("100")
            except:
                rate_val = Decimal("0")
                
            # Date parsing
            d_ini = None
            if isinstance(f_ini, (date, datetime)): d_ini = f_ini if isinstance(f_ini, date) else f_ini.date()
            else:
                 try: d_ini = datetime.strptime(str(f_ini).strip(), "%Y-%m-%d").date()
                 except: pass
            
            d_fin = None
            if f_fin and str(f_fin).strip() not in ["", "None", "NaT"]:
                 if isinstance(f_fin, (date, datetime)): d_fin = f_fin if isinstance(f_fin, date) else f_fin.date()
                 else:
                     try: d_fin = datetime.strptime(str(f_fin).strip(), "%Y-%m-%d").date()
                     except: pass
            
            if d_ini:
                out.append({"start": d_ini, "end": d_fin, "rate": rate_val})
        return out

    list_rem = parse_df(df_rem, "Tasa Rem EA (%)")
    list_mora = parse_df(df_mora, "Tasa Mora EA (%)")
    
    return list_rem, list_mora

def parse_abonos(rows):
    out = []
    
    # If the rows come from data_editor as DataFrame, we might need to iterate differently
    # But usually Streamlit data_editor returns a DF if input was DF.
    import pandas as pd
    
    iterator = []
    if isinstance(rows, pd.DataFrame):
        # Convert to list of dicts to reuse logic, or iterate directly
        iterator = rows.to_dict(orient="records")
    elif isinstance(rows, list):
        iterator = rows
    else:
        return []

    def to_decimal(val):
        if val is None:
            return Decimal("0")
        s = str(val).strip()
        if not s or s.lower() in ["nan", "nat", "none", "null"]:
            return Decimal("0")
        try:
            return Decimal(s)
        except:
            return Decimal("0")

    for r in iterator:
        f = r.get("Fecha")
        if f is None or str(f).strip() == "" or str(f).strip().lower() == "nat":
            continue
        
        d = None
        if isinstance(f, (date, datetime)):
            d = f if isinstance(f, date) else f.date()
        else:
            # Fallback for string input just in case
            f_str = str(f).strip()
            # pandas sometimes gives NaT or nan
            if f_str.lower() in ["nat", "nan", "none"]:
                continue
                
            try:
                d = datetime.strptime(f_str, "%Y-%m-%d").date()
            except Exception:
                try:
                    d = datetime.strptime(f_str, "%d/%m/%Y").date()
                except Exception:
                    continue
        
        if not d:
            continue
            
        out.append(Abono(
            fecha=d,
            abono_capital=to_decimal(r.get("Abono Capital")),
            abono_int_rem=to_decimal(r.get("Abono Int Rem")),
            abono_int_mor=to_decimal(r.get("Abono Int Mor")),
        ))
    return out

if "calculation_result" not in st.session_state:
    st.session_state["calculation_result"] = None

btn = st.button("Recalcular Tabla", type="primary", use_container_width=True)

if btn:
    tasas_rem, tasas_mora = parse_tasas_variables()
    
    inp = Inputs(
        capital_inicial=Decimal(str(capital)),
        fecha_vcto_neto=fecha_vcto_neto,
        fecha_vcto_total=fecha_vcto_total,
        fecha_actual=fecha_actual,
        tasas_rem_vars=tasas_rem,
        tasas_mora_vars=tasas_mora
    )
    abonos = parse_abonos(ab_rows)

    rem, mora, state = motor_completo(inp, abonos)
    st.session_state["calculation_result"] = {
        "rem": rem,
        "mora": mora,
        "state": state
    }

if st.session_state["calculation_result"]:
    res = st.session_state["calculation_result"]
    rem = res["rem"]
    mora = res["mora"]
    state = res["state"]


    colA, colB = st.columns(2)
    with colA:
        st.subheader("Periodo de Causación de Intereses Remuneratorio")
        st.dataframe(rem, use_container_width=True, height=520)
        import csv, io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=rem[0].keys() if rem else [])
        w.writeheader()
        for row in rem:
            w.writerow(row)
        st.download_button("Descargar Remuneratorio (CSV)", data=buf.getvalue().encode("utf-8"), file_name="remuneratorio.csv", mime="text/csv", use_container_width=True)

    with colB:
        st.subheader("Periodo de Causación de Intereses Moratorios")
        st.dataframe(mora, use_container_width=True, height=520)
        import csv, io
        buf2 = io.StringIO()
        w2 = csv.DictWriter(buf2, fieldnames=mora[0].keys() if mora else [])
        w2.writeheader()
        for row in mora:
            w2.writerow(row)
        st.download_button("Descargar Moratorio (CSV)", data=buf2.getvalue().encode("utf-8"), file_name="moratorio.csv", mime="text/csv", use_container_width=True)

else:
    st.info("Configura parámetros y presiona **Recalcular Tabla**.")
