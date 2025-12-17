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
class Inputs:
    capital_inicial: Decimal
    tasa_ea_rem: Decimal          # decimal, e.g. 0.171263
    tasa_ea_mora: Decimal         # decimal, e.g. 0.2501 (EA usura)
    fecha_vcto_neto: date
    fecha_vcto_total: date
    fecha_actual: date


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

def calcular_remuneratorio_excel(inp: Inputs, abonos: list[Abono]):
    """
    Columnas alineadas a tu Excel:
    - L: Tasa Int. Remuneratorio
    - M: Días
    - N: Saldo Capital
    - O: Valor Futuro (Valor obligación)
    - P: Causación interés rem. diario
    - Q: Intereses Remu Acumulados
    - Y: Abono realizado a capital (columna amarilla)
    - Z: Abono realizado a interés Remuneratorio (columna amarilla)

    IMPORTANTÍSIMO (Excel):
    - El abono de HOY (Y,Z) NO afecta N/O/P/Q del mismo día.
      Afecta desde el día siguiente porque N usa Y del día anterior y
      Q resta SUM(Z13:Zfila-1).
    """
    abmap = _map_abonos(abonos)

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
        # L: Tasa
        # -------------------------
        L = inp.tasa_ea_rem

        # -------------------------
        # M: Días (según tu regla)
        # -------------------------
        if f == inp.fecha_vcto_neto:
            M = 0
        else:
            M = dias_360_excel(f, prev_fecha) if prev_fecha else 1

        # -------------------------
        # N: Saldo Capital (tu fórmula)
        #
        # =IFERROR(
        #   IF(OR($L93=" ";$L93<0;$M93<0)," ",
        #      IF(M93=0,$Q$8,
        #         IF(AND(M92=0,OR($M93>1,$M93=1)),N92,N92-Y92)
        #      )
        #   ),
        # " ")
        # -------------------------
        if L < 0 or M < 0:
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
        # O: Valor Futuro (Valor obligación)
        # (replicación práctica Excel con reglas día 31)
        # -------------------------
        if N is None:
            O = None
        else:
            if M == 0:
                O = r2(N)
            else:
                if f.day == 31:
                    # Excel fuerza 0 días => no crece
                    # si hubo abono capital anterior, usa N; si no, mantiene O anterior
                    O = r2(prev_O if (prev_Y <= 0) else N)
                else:
                    base_vf = (prev_O if (prev_Y <= 0) else N)
                    O = _vf_equivalente_excel(L, int(M), r2(base_vf))

        # -------------------------
        # P: Causación interés rem diario (tu lógica)
        # -------------------------
        if O is None or N is None:
            P = None
        else:
            if M == 0 or f.day == 31:
                P = r2(Decimal("0"))
            else:
                # Si N no cambió => O - O_prev
                # Si N cambió (por abono cap anterior) => O - N
                if prev_N is not None and r2(prev_N) == r2(N):
                    P = r2(O - (prev_O if prev_O is not None else N))
                else:
                    P = r2(O - N)

        # -------------------------
        # Y/Z: Abonos del día (NO afectan HOY, afectan mañana)
        # -------------------------
        a = abmap.get(f)
        Y = r2(D(a.abono_capital) if a else Decimal("0"))
        Z = r2(D(a.abono_int_rem) if a else Decimal("0"))

        # -------------------------
        # Q: Intereses Remu Acumulados
        # =IF($P93=" "," ", SUM($P$14:P93) - SUM($Z$13:Z92))
        # => resta hasta AYER (sum_z_hasta_ayer)
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

        # Actualizar “previos”
        prev_fecha = f
        prev_M = M
        prev_N = N
        prev_O = O
        prev_Y = Y

        # MUY IMPORTANTE: para el próximo día, el acumulado descuenta Z de HOY,
        # porque el Excel resta Z hasta fila anterior.
        sum_z_hasta_ayer += Z

        f = f + timedelta(days=1)

    # Estado final Rem:
    saldo_cap_final = r2(prev_N if prev_N is not None else inp.capital_inicial)

    # El interés rem final para “mostrar” debe ser el Q del último día (si existe).
    # Porque Q ya aplica EXACTAMENTE: SUM(P) - SUM(Z hasta ayer).
    interes_rem_final = r2(Decimal(str(filas[-1]["Intereses Remu Acumulados"]))
                        ) if filas and filas[-1]["Intereses Remu Acumulados"] != "" else Decimal("0")

    return filas, {
        "saldo_capital_final": saldo_cap_final,
        "interes_rem_final": interes_rem_final,
    }


# ======================================================
# 2) Moratorio (Excel exacto por fórmula)
# ======================================================

def calcular_moratorio_excel(inp: Inputs, abonos: list[Abono], saldo_capital_base: Decimal):
    """
    OJO: Ajuste importante (tu Excel):
    - El saldo capital inicial de mora (cuando Días=0) viene de $T$8.
      Eso representa CAPITAL (no capital + interés remuneratorio).
    """
    abmap = _map_abonos(abonos)

    tasa_diaria = _tasa_diaria_mora_excel(inp.tasa_ea_mora)

    filas: list[dict] = []

    # W (Intereses Mora Acumulados):
    # =IF($V99=" "," ", SUM($V$14:V99) - SUM($AA$13:AA98))
    sum_v_hasta_hoy = Decimal("0")     # acumulamos (en 2 dec) como termina mostrándose
    sum_aa_hasta_ayer = Decimal("0")   # abono a interés mora hasta ayer

    inicio = inp.fecha_vcto_total      # Excel incluye fila con Días=0 en vcto_total
    fin = inp.fecha_actual

    prev_fecha: date | None = None
    prev_T: int | None = None          # Días prev
    prev_U: Decimal | None = None      # Saldo Capital prev
    prev_Y: Decimal = Decimal("0")     # Abono cap del día anterior

    f = inicio
    while f <= fin:

        # -------------------------
        # S: Tasa mora diaria (en Excel se “busca” pero el resultado es este valor)
        # -------------------------
        S = tasa_diaria

        # -------------------------
        # T: Días
        # -------------------------
        if f == inp.fecha_vcto_total:
            T = 0
        else:
            T = dias_360_excel(f, prev_fecha) if prev_fecha else 1

        # -------------------------
        # U: Saldo Capital (tu fórmula)
        #
        # =IFERROR(
        #   IF(OR($S98=" ";$S98<0;$T98<0)," ",
        #      IF(T98=0,$T$8,
        #         IF(AND(T97=0,OR($T98>1,$T98=1)),U97,U97-Y97)
        #      )
        #   ),
        # " ")
        # -------------------------
        if S < 0 or T < 0:
            U = None
        elif T == 0:
            U = r2(saldo_capital_base)   # <-- ESTE ES EL AJUSTE (NO capital+int rem)
        else:
            if prev_T == 0 and (T >= 1):
                U = r2(prev_U if prev_U is not None else saldo_capital_base)
            else:
                base_prev = prev_U if prev_U is not None else saldo_capital_base
                U = r2(base_prev - (prev_Y or Decimal("0")))

        # -------------------------
        # V: Causación mora diario
        # =REDONDEAR(U * S * T; 6) con reglas día 31 => 0 y T=0 => 0
        # -------------------------
        if U is None:
            V = None
        else:
            if f.day == 31 or T == 0:
                V = r6(Decimal("0"))
            else:
                V = r6(U * S * Decimal(int(T)))

        # -------------------------
        # Y/AA: Abonos del día (NO afectan HOY, afectan mañana)
        # -------------------------
        a = abmap.get(f)
        Y = r2(D(a.abono_capital) if a else Decimal("0"))
        AA = r2(D(a.abono_int_mor) if a else Decimal("0"))

        # -------------------------
        # W: Intereses Mora Acumulados (exacto)
        # =SUM(V)-SUM(AA hasta ayer)
        # En Excel V se ve con 6 dec pero el acumulado se ve a 2 dec.
        # -------------------------
        if V is None:
            W = None
        else:
            sum_v_hasta_hoy += r2(V)   # acumulación mostrada
            W = r2(sum_v_hasta_hoy - sum_aa_hasta_ayer)

        filas.append({
            "Fecha": f.strftime("%d/%m/%Y"),
            "Tasa Int. Mora": float(S),
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

        # Igual que en Rem: lo de HOY se descuenta desde mañana
        sum_aa_hasta_ayer += AA

        f = f + timedelta(days=1)

    interes_mora_final = r2(Decimal(str(filas[-1]["Intereses Mora Acumulados"]))
                            ) if filas and filas[-1]["Intereses Mora Acumulados"] != "" else Decimal("0")

    return filas, {
        "tasa_diaria_mora": tasa_diaria,
        "saldo_capital_mora_final": r2(prev_U if prev_U is not None else saldo_capital_base),
        "interes_mora_final": interes_mora_final,
    }


# ======================================================
# 3) Motor completo (recalcula TODO siempre)
# ======================================================

def motor_completo(inp: Inputs, abonos: list[Abono]):
    """
    Este es el punto determinístico:
    - si metes abono en retrofecha,
      se vuelve a correr desde fecha_vcto_neto y todo se ajusta (rem y mora).
    """
    rem_rows, rem_state = calcular_remuneratorio_excel(inp, abonos)

    # AJUSTE: Mora arranca con CAPITAL (saldo_capital_final),
    # NO capital + interés remuneratorio.
    mora_rows, mora_state = calcular_moratorio_excel(
        inp,
        abonos,
        saldo_capital_base=rem_state["saldo_capital_final"],
    )

    state = {**rem_state, **mora_state}
    # Fix para app.py: exponer la base real usada para mora (que es capital solo, según ajuste)
    state["capital_base_mora"] = rem_state["saldo_capital_final"]
    return rem_rows, mora_rows, state
