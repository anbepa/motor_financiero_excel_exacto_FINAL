import streamlit as st
from datetime import datetime
from decimal import Decimal
from services.engine import Inputs, Abono, motor_completo
from ui.components import number_money, number_rate_decimal, number_rate_percent, abonos_editor

st.set_page_config(page_title="Motor Financiero Determinístico", layout="wide")
st.title("Motor Financiero Determinístico (Excel EXACTO)")
st.caption("Implementación basada en las fórmulas reales que compartiste (VF, días, acumulados, recálculo por abono a capital).")

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
    for r in rows:
        f = str(r.get("Fecha","")).strip()
        if not f:
            continue
        try:
            d = datetime.strptime(f, "%Y-%m-%d").date()
        except Exception:
            # intenta dd/mm/yyyy
            try:
                d = datetime.strptime(f, "%d/%m/%Y").date()
            except Exception:
                continue
        out.append(Abono(
            fecha=d,
            abono_capital=Decimal(str(r.get("Abono Capital",0) or 0)),
            abono_int_rem=Decimal(str(r.get("Abono Int Rem",0) or 0)),
            abono_int_mor=Decimal(str(r.get("Abono Int Mor",0) or 0)),
        ))
    return out

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

    st.success(f"Capital base mora (Saldo capital final + Int Rem final): {state['capital_base_mora']} | Tasa diaria mora: {state['tasa_diaria_mora']}")

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Periodo de Causación — Intereses Remuneratorios")
        st.dataframe(rem, use_container_width=True, height=520)
        import csv, io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=rem[0].keys() if rem else [])
        w.writeheader()
        for row in rem:
            w.writerow(row)
        st.download_button("Descargar Remuneratorio (CSV)", data=buf.getvalue().encode("utf-8"), file_name="remuneratorio.csv", mime="text/csv", use_container_width=True)

    with colB:
        st.subheader("Periodo de Causación — Intereses Moratorios")
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
