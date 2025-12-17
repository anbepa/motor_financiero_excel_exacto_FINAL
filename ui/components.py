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
    st.caption("Ingresa abonos por fecha. El motor descuenta abonos a interés en el acumulado desde el día siguiente (igual que la fórmula SUMA()-SUMA(prev).)")

    if "abonos" not in st.session_state:
        st.session_state["abonos"] = [
            {"Fecha": "", "Abono Capital": 0.0, "Abono Int Rem": 0.0, "Abono Int Mor": 0.0},
        ]

    edited = st.data_editor(
        st.session_state["abonos"],
        num_rows="dynamic",
        use_container_width=True,
        key="abonos_editor",
    )
    st.session_state["abonos"] = edited
    return edited
