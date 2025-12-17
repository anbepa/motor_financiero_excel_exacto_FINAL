from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from utils.rounding import D, r2, r6
from utils.days import dias_360_excel


# ======================================================
# Modelos
# ======================================================

@dataclass
class RateRange:
    start: date
    end: date | None
    rate: Decimal

@dataclass
class Inputs:
    capital_inicial: Decimal
    fecha_vcto_neto: date
    fecha_vcto_total: date
    fecha_actual: date
    tasas_rem_vars: list[dict] # list of dict(start, end, rate)
    tasas_mora_vars: list[dict] # list of dict(start, end, rate)


@dataclass
class Abono:
    fecha: date
    abono_capital: Decimal = Decimal("0")
    abono_int_rem: Decimal = Decimal("0")
    abono_int_mor: Decimal = Decimal("0")


def _map_abonos(abonos: list[Abono]) -> dict[date, Abono]:
    """
    Si llega más de un registro por fecha, se acumula.
    (En Excel podrías sumar varias filas el mismo día).
    """
    m: dict[date, Abono] = {}
    for a in abonos:
        if a.fecha not in m:
            m[a.fecha] = Abono(
                fecha=a.fecha,
                abono_capital=D(a.abono_capital),
                abono_int_rem=D(a.abono_int_rem),
                abono_int_mor=D(a.abono_int_mor),
            )
        else:
            m[a.fecha].abono_capital = D(m[a.fecha].abono_capital) + D(a.abono_capital)
            m[a.fecha].abono_int_rem = D(m[a.fecha].abono_int_rem) + D(a.abono_int_rem)
            m[a.fecha].abono_int_mor = D(m[a.fecha].abono_int_mor) + D(a.abono_int_mor)
    return m


def _lookup_rate(f: date, ranges: list[dict]) -> Decimal:
    for r in ranges:
        start = r["start"]
        end = r["end"]
        # Inclusive range check
        if end:
            if start <= f <= end:
                return r["rate"]
        else:
            # If no end date, assumes valid from start onwards?
            # Or invalid? Based on "rango inicio fin" requirement, maybe strictly range.
            # But let's follow the previous logic: if end is missing, valid indefinitely (or single day?)
            # Usually end is required for range. If User fills auto-end-of-month, it has end.
            if start <= f:
                 return r["rate"]
    return Decimal("0")

def _get_tasas_dia(f: date, rem_vars: list[dict], mora_vars: list[dict]) -> tuple[Decimal, Decimal]:
    """
    Retorna (tasa_rem, tasa_mora) vigentes para la fecha f usando listas independientes.
    """
    tr = _lookup_rate(f, rem_vars)
    tm = _lookup_rate(f, mora_vars)
    return tr, tm


# ======================================================
# Helpers financieros (Excel-exacto)
# ======================================================

def _vf_equivalente_excel(rate_ea: Decimal, dias: int, base: Decimal) -> Decimal:
    """
    Equivalente a VF(rate; dias/360;; -base) con redondeo intermedio.
    La plantilla anida VF cuando dias>1. Para replicarlo:
    aplicamos 1 día repetido 'dias' veces, redondeando cada paso a 2 dec.
    """
    if dias <= 0:
        return r2(base)

    one_day_factor = (Decimal("1") + rate_ea) ** (Decimal("1") / Decimal("360"))
    # IMPORTANTE: En el motor original, para dias>1 se iteraba.
    # Con tasa variable, 'rate_ea' es la del día del cálculo.
    # Si dias > 1 (acumulado), asumimos que la tasa NO cambió DENTRO de esos 'dias' 
    # porque el loop principal avanza de 1 en 1, así que M suele ser 1.
    # Si M fuera > 1, técnicamente usaríamos la tasa de ese 'día de causación'.
    
    acc = r2(base)
    for _ in range(int(dias)):
        acc = r2(acc * one_day_factor)
    return acc


def _tasa_diaria_mora_excel(tasa_ea_mora: Decimal) -> Decimal:
    """
    En tu Excel la tasa mora diaria sale de:
    ((1+EA)^(1/12)-1)/30
    y se redondea a 6 decimales ANTES de usarla.
    """
    raw = ((Decimal("1") + tasa_ea_mora) ** (Decimal("1") / Decimal("12")) - Decimal("1")) / Decimal("30")
    return r6(raw)


# ======================================================
# 1) Remuneratorio (Excel exacto por fórmula)
# ======================================================

def calcular_remuneratorio_excel(inp: Inputs, map_abonos: dict[date, Abono]):
    """
    Columnas alineadas a tu Excel:
    - L: Tasa Int. Remuneratorio (Variable)
    ...
    """
    # abmap already passed
    abmap = map_abonos
    
    filas: list[dict] = []

    # Para Q: SUM(P14:Pfila) - SUM(Z13:Zfila-1)
    sum_p_hasta_hoy = Decimal("0")
    sum_z_hasta_ayer = Decimal("0")

    prev_fecha: date | None = None
    prev_M: int | None = None
    prev_N: Decimal | None = None
    prev_O: Decimal | None = None
    prev_Y: Decimal = Decimal("0")  # Y del día anterior

    f = inp.fecha_vcto_neto
    while f <= inp.fecha_vcto_total:

        # -------------------------
        # L: Tasa (Variable Día a Día)
        # -------------------------
        # Obtenemos la tasa vigente para este día
        L_rem, _ = _get_tasas_dia(f, inp.tasas_rem_vars, inp.tasas_mora_vars)
        
        # En el Excel la columna L imprime la tasa vigente
        L = L_rem

        # -------------------------
        # M: Días (según tu regla)
        # -------------------------
        if f == inp.fecha_vcto_neto:
            M = 0
        else:
            M = dias_360_excel(f, prev_fecha) if prev_fecha else 1

        # -------------------------
        # N: Saldo Capital
        # -------------------------
        if M < 0: # L < 0 check removed as L is likely safe
            N = None
        elif M == 0:
            N = r2(inp.capital_inicial)
        else:
            if prev_M == 0 and (M >= 1):
                N = r2(prev_N if prev_N is not None else inp.capital_inicial)
            else:
                base_prev = prev_N if prev_N is not None else inp.capital_inicial
                N = r2(base_prev - (prev_Y or Decimal("0")))

        # -------------------------
        # O: Valor Futuro
        # -------------------------
        if N is None:
            O = None
        else:
            if M == 0:
                O = r2(N)
            else:
                if f.day == 31:
                    O = r2(prev_O if (prev_Y <= 0) else N)
                else:
                    base_vf = (prev_O if (prev_Y <= 0) else N)
                    O = _vf_equivalente_excel(L, int(M), r2(base_vf))

        # -------------------------
        # P: Causación interés rem diario
        # -------------------------
        if O is None or N is None:
            P = None
        else:
            if M == 0 or f.day == 31:
                P = r2(Decimal("0"))
            else:
                if prev_N is not None and r2(prev_N) == r2(N):
                    P = r2(O - (prev_O if prev_O is not None else N))
                else:
                    P = r2(O - N)

        # -------------------------
        # Y/Z: Abonos del día
        # -------------------------
        a = abmap.get(f)
        Y = r2(D(a.abono_capital) if a else Decimal("0"))
        Z = r2(D(a.abono_int_rem) if a else Decimal("0"))

        # -------------------------
        # Q: Intereses Remu Acumulados
        # -------------------------
        if P is None:
            Q = None
        else:
            sum_p_hasta_hoy += P
            Q = r2(sum_p_hasta_hoy - sum_z_hasta_ayer)

        filas.append({
            "Fecha": f.strftime("%d/%m/%Y"),
            "Tasa Int. Remuneratorio": float(L),
            "Días": int(M),
            "Saldo Capital": "" if N is None else float(N),
            "Valor Futuro (Valor obligación)": "" if O is None else float(O),
            "Causación intrés rem. Diario": "" if P is None else float(P),
            "Intereses Remu Acumulados": "" if Q is None else float(Q),
            "Abono realizado a capital": float(Y),
            "Abono realizado a interés Remuneratorio": float(Z),
        })

        prev_fecha = f
        prev_M = M
        prev_N = N
        prev_O = O
        prev_Y = Y
        sum_z_hasta_ayer += Z

        f = f + timedelta(days=1)

    saldo_cap_final = r2(prev_N if prev_N is not None else inp.capital_inicial)

    interes_rem_final = r2(Decimal(str(filas[-1]["Intereses Remu Acumulados"]))
                        ) if filas and filas[-1]["Intereses Remu Acumulados"] != "" else Decimal("0")

    return filas, {
        "saldo_capital_final": saldo_cap_final,
        "interes_rem_final": interes_rem_final,
    }


# ======================================================
# 2) Moratorio (Excel exacto por fórmula)
# ======================================================

def calcular_moratorio_excel(inp: Inputs, map_abonos: dict[date, Abono], saldo_capital_final_rem: Decimal, interes_rem_pendiente: Decimal) -> list[dict]:
    """
    Simulación EXACTA del Excel para interés moratorio.
    Arranca desde el día siguiente a FVT (o la fecha de corte anterior).
    """
    resultados = []
    
    # Fecha inicio mora: FVT + 1 día (En excel FVT es 1 nov, Start mora 1 nov??? 
    # Usualmente mora arranca tras vencimiento.
    # En el excel: Liq mora start = 1/12/2025 (FVT era 1/12/2025???) 
    # Si FVT=01/12, Mora empieza 01/12? No, usualmente el día sgte. 
    # PERO SEGUIMOS EL EXCEL: La primera fila es 01/12/2025.
    
    filas: list[dict] = []

    sum_v_hasta_hoy = Decimal("0")     
    sum_aa_hasta_ayer = Decimal("0")   

    inicio = inp.fecha_vcto_total      
    fin = inp.fecha_actual

    prev_fecha: date | None = None
    prev_T: int | None = None          
    prev_U: Decimal | None = None      
    prev_Y: Decimal = Decimal("0")     

    f = inicio
    
    # Para mostrar en el estado final la ÚLTIMA tasa usada
    last_tasa_diaria = Decimal("0")

    while f <= fin:

        # -------------------------
        # Tasa Variable del día
        # -------------------------
        _, L_mora_ea = _get_tasas_dia(f, inp.tasas_rem_vars, inp.tasas_mora_vars)
        
        # S: Tasa mora diaria variable
        S = _tasa_diaria_mora_excel(L_mora_ea)
        last_tasa_diaria = S

        # -------------------------
        # T: Días
        # -------------------------
        if f == inp.fecha_vcto_total:
            T = 0
        else:
            T = dias_360_excel(f, prev_fecha) if prev_fecha else 1

        # -------------------------
        # U: Saldo Capital
        # -------------------------
        # -------------------------
        # U: Saldo Capital
        # -------------------------
        if S < 0 or T < 0:
            U = None
        elif T == 0:
            U = r2(saldo_capital_final_rem)
        else:
            if prev_T == 0 and (T >= 1):
                U = r2(prev_U if prev_U is not None else saldo_capital_final_rem)
            else:
                base_prev = prev_U if prev_U is not None else saldo_capital_final_rem
                U = r2(base_prev - (prev_Y or Decimal("0")))

        # -------------------------
        # V: Causación mora diario
        # -------------------------
        if U is None:
            V = None
        else:
            if f.day == 31 or T == 0:
                V = r6(Decimal("0"))
            else:
                V = r6(U * S * Decimal(int(T)))

        # -------------------------
        # Y/AA: Abonos del día
        # -------------------------
        a = map_abonos.get(f)
        Y = r2(D(a.abono_capital) if a else Decimal("0"))
        AA = r2(D(a.abono_int_mor) if a else Decimal("0"))

        # -------------------------
        # W: Intereses Mora Acumulados
        # -------------------------
        if V is None:
            W = None
        else:
            sum_v_hasta_hoy += r2(V)
            W = r2(sum_v_hasta_hoy - sum_aa_hasta_ayer)

        filas.append({
            "Fecha": f.strftime("%d/%m/%Y"),
            "Tasa Int. Mora": float(S), # Mostramos la diaria usada ese día
            "Días": int(T),
            "Saldo Capital": "" if U is None else float(U),
            "Causación interés mora diario": "" if V is None else float(V),
            "Intereses Mora Acumulados": "" if W is None else float(W),
            "Abono realizado a capital": float(Y),
            "Abono realizado a interés Moratorio": float(AA),
        })

        prev_fecha = f
        prev_T = T
        prev_U = U
        prev_Y = Y
        sum_aa_hasta_ayer += AA

        f = f + timedelta(days=1)

    interes_mora_final = r2(Decimal(str(filas[-1]["Intereses Mora Acumulados"]))
                            ) if filas and filas[-1]["Intereses Mora Acumulados"] != "" else Decimal("0")

    return filas, {
        "tasa_diaria_mora": last_tasa_diaria, # La ultima usada
        "saldo_capital_mora_final": r2(prev_U if prev_U is not None else saldo_capital_final_rem),
        "interes_mora_final": interes_mora_final,
    }


# ======================================================
# 3) Motor completo (recalcula TODO siempre)
# ======================================================

def motor_completo(inp: Inputs, abonos: list[Abono]):
    """
    Este es el punto determinístico.
    """
    abmap = _map_abonos(abonos)
    
    # calcular_remuneratorio_excel returns: (list[dict], dict)
    rem_rows, rem_state_dict = calcular_remuneratorio_excel(inp, abmap)
    
    # Extract necessary values from returned state
    saldo_cap_final_rem = rem_state_dict.get("saldo_capital_final", Decimal("0"))
    
    # Check if we have total abonos in the state or need to sum them?
    # The dictionary returned (seen in line 251) is: {"saldo_capital_final": ..., "interes_rem_final": ...}
    # It does NOT verify total abonos, but maybe we don't strictly need them for the return signature?
    # The original return signature of motor_completo was (rows, rows, state).
    
    # We can reconstruct the full state to return
    # rem_state_dict currently misses 'total_abono_capital' etc if they were expected, 
    # but let's assume valid state for now.
    
    mora_rows, mora_state = calcular_moratorio_excel(
        inp,
        map_abonos=abmap,
        saldo_capital_final_rem=saldo_cap_final_rem,
        interes_rem_pendiente=Decimal("0")
    )

    state = {**rem_state_dict, **mora_state}
    state["capital_base_mora"] = saldo_cap_final_rem
    
    return rem_rows, mora_rows, state
