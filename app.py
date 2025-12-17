import streamlit as st
from datetime import datetime, date
from decimal import Decimal
from services.engine import Inputs, Abono, motor_completo
from ui.components import number_money, number_rate_decimal, number_rate_percent, abonos_editor

st.set_page_config(page_title="Motor Financiero Determinístico", layout="wide")
st.title("Simulador cargos SAF")

st.subheader("Configuración de la Obligación")
c1, c2, c3 = st.columns(3)
with c1:
    capital = number_money("Capital Obligación", 41080600.00, "capital")
    fecha_vcto_neto = st.date_input("Fecha Vcto Neto", value=datetime.strptime("2025-11-25","%Y-%m-%d").date(), key="fvn")
with c2:
    tasa_rem = number_rate_decimal("Tasa Remuneratoria EA (Decimal)", 0.171263, "trem")
    fecha_vcto_total = st.date_input("Fecha Vcto Total", value=datetime.strptime("2025-12-01","%Y-%m-%d").date(), key="fvt")
with c3:
    tasa_mora_pct = number_rate_percent("Tasa Usura/Mora EA (%)", 25.01, "tmora")
    fecha_actual = st.date_input("Fecha Actual/Corte", value=datetime.strptime("2025-12-16","%Y-%m-%d").date(), key="fa")

st.divider()

ab_rows = abonos_editor()

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
    inp = Inputs(
        capital_inicial=Decimal(str(capital)),
        tasa_ea_rem=Decimal(str(tasa_rem)),
        tasa_ea_mora=Decimal(str(tasa_mora_pct))/Decimal("100"),
        fecha_vcto_neto=fecha_vcto_neto,
        fecha_vcto_total=fecha_vcto_total,
        fecha_actual=fecha_actual,
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
