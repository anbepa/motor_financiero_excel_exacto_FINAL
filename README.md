# Motor Financiero Determinístico — ZIP FINAL (sin pandas)

✅ **Evita el error** `numpy.core.multiarray failed to import` porque **NO usa pandas**.

## Ejecutar (recomendado)
Usa un entorno limpio con Python 3.11:

```bash
python -m venv .venv
source .venv/bin/activate   # mac/linux
# .venv\Scripts\activate  # windows

pip install -r requirements.txt
streamlit run app.py
```

## Abonos
En la UI puedes ingresar abonos por fecha:
- Abono Capital
- Abono Int Remuneratorio
- Abono Int Moratorio

> El motor aplica las reglas Excel que compartiste:
> - Días 30/360 estricto con excepciones (31, Feb 28/29)
> - VF() equivalente con capitalización diaria y redondeo a 2 decimales por paso
> - Recálculo por abono a capital **solo desde el día siguiente**
> - Acumulados = SUMA(causaciones) - SUMA(abonos a interés) (según fórmulas)

