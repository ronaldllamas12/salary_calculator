import datetime
from flask import Flask, render_template, request
import traceback

from calculadora_nomina import (
    crear_estructura_inicial, calcular_liquidacion_manual
)
from constantes import (
    SUBSIDIO_TRANSPORTE, TRADUCCIONES_DIAS_SEMANA
)

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    resumen_html = None
    
    # Valores por defecto para el formulario
    fecha_inicio_default = "2025-01-01"
    fecha_fin_default = "2025-01-01"
    opciones_ciclo = [
        "1ER DIA", "2DO DIA", "1RA NOCHE", "2DA NOCHE", "1ER DESCANSO", "2DO DESCANSO"
    ]
    ciclo_inicio_default = "1ER DIA"
    deduccion_nombre_default = ""
    deduccion_valor_default = 0.0
    reajuste_ordinario_horas_default = 0.0

    if request.method == "POST":
        try:
            corte_inicio_str = request.form["fecha_inicio"]
            corte_fin_str = request.form["fecha_fin"]
            ciclo_inicio_seleccionado = request.form["ciclo_inicio"]
            deduccion_nombre = request.form["deduccion_nombre"]
            deduccion_valor = float(request.form["deduccion_valor"])
            horas_reajuste_manual = float(request.form["reajuste_ordinario_horas"])

            fecha_inicio = datetime.datetime.strptime(corte_inicio_str, "%Y-%m-%d")
            fecha_fin = datetime.datetime.strptime(corte_fin_str, "%Y-%m-%d")

            if fecha_fin <= fecha_inicio:
                raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio")
            
            delta = fecha_fin - fecha_inicio
            if delta.days > 90:
                raise ValueError("El rango de fechas no puede ser mayor a 90 días")

            # --- Lógica para generar detalle_horas (similar a actualizar_fechas_y_dias_semana en interfaz_grafica.py) ---
            liquidacion_detallada_web = crear_estructura_inicial()
            num_dias = delta.days + 1
            if num_dias > len(liquidacion_detallada_web):
                for i in range(len(liquidacion_detallada_web), num_dias):
                    liquidacion_detallada_web.append({
                        "fecha": "", "dia_semana": "", "tipo_turno": "",
                        "recargo_nocturno": 0.0, "extra_diurna": 0.0, "extra_nocturna": 0.0,
                        "festivo_diurno": 0.0, "festivo_nocturno": 0.0, "extra_festiva_diurna": 0.0,
                        "extra_festiva_nocturna": 0.0, "descanso_pagado": 0.0
                    })
            elif num_dias < len(liquidacion_detallada_web):
                liquidacion_detallada_web[:] = liquidacion_detallada_web[:num_dias]

            ciclo_base = ["DIURNO", "DIURNO", "NOCTURNO", "NOCTURNO", "DESCANSO", "DESCANSO"]
            mapeo_seleccion = {
                "1ER DIA": 0, "2DO DIA": 1, "1RA NOCHE": 2,
                "2DA NOCHE": 3, "1ER DESCANSO": 4, "2DO DESCANSO": 5
            }
            posicion_ciclo = mapeo_seleccion.get(ciclo_inicio_seleccionado, 0)

            for i, dia in enumerate(liquidacion_detallada_web):
                nueva_fecha = fecha_inicio + datetime.timedelta(days=i)
                dia["fecha"] = nueva_fecha.strftime("%Y-%m-%d")
                dia["dia_semana"] = TRADUCCIONES_DIAS_SEMANA.get(nueva_fecha.strftime("%A").upper(), nueva_fecha.strftime("%A").upper())
                posicion_actual = (posicion_ciclo + i) % len(ciclo_base)
                tipo_turno_ciclo = ciclo_base[posicion_actual]
                dia["tipo_turno"] = tipo_turno_ciclo
            # --- Fin de la lógica para generar detalle_horas ---

            ajuste_extra_nocturna = 0.0
            fecha_24_julio_2025 = datetime.datetime(2025, 7, 24).date()
            if fecha_inicio.date() <= fecha_24_julio_2025 <= fecha_fin.date():
                ajuste_extra_nocturna = 2.0

            resumen = calcular_liquidacion_manual(liquidacion_detallada_web, horas_reajuste_manual, ajuste_extra_nocturna)

            # Calcular deducciones
            total_dev_para_deducciones = resumen['total_devengado_sin_subsidio']
            deduccion_salud = total_dev_para_deducciones * 0.04
            deduccion_pension = total_dev_para_deducciones * 0.04
            total_deducciones = deduccion_salud + deduccion_pension + deduccion_valor
            neto_pagar = resumen['total_devengado'] - total_deducciones

            # Formatear resultados para HTML
            resumen_output = []
            resumen_output.append(f"\t--- LIQUIDACIÓN DE TURNOS ---\n\n")
            resumen_output.append(f"Periodo: {corte_inicio_str} a {corte_fin_str}\n")
            resumen_output.append(f"Inicio de ciclo seleccionado: {ciclo_inicio_seleccionado}\n")
            resumen_output.append("\n\t---- HORAS TOTALES ----\n\n")
            resumen_output.append(f"\nHoras ordinarias: {resumen['horas_ordinarias']:.2f}\n")
            resumen_output.append(f"\nRecargo nocturno: {resumen['horas_recargo_nocturno']:.2f}\n")
            resumen_output.append(f"\nExtra diurna: {resumen['horas_extra_diurna']:.2f}\n")
            resumen_output.append(f"\nExtra nocturna: {resumen['horas_extra_nocturna']:.2f}\n")
            resumen_output.append(f"\nFestivo trabajado diurno: {resumen['horas_festivo_diurno']:.2f}\n")
            resumen_output.append(f"\nFestivo trabajado nocturno: {resumen['horas_festivo_nocturno']:.2f}\n")
            resumen_output.append(f"\nExtra festiva diurna: {resumen['horas_extra_festiva_diurna']:.2f}\n")
            resumen_output.append(f"\nExtra festiva nocturna: {resumen['horas_extra_festiva_nocturna']:.2f}\n")
            resumen_output.append(f"\nHoras de descanso pagadas: {resumen['horas_descanso_pagado']:.2f}\n")
            if resumen['horas_reajuste_ordinario'] > 0:
                resumen_output.append(f"\nReajuste ordinario (por dos festivos en semana): {resumen['horas_reajuste_ordinario']}h\n")

            resumen_output.append("\n\n\t-- VALORES DEVENGADOS (COP) --\n\n")
            resumen_output.append(f"\nValor ordinarias: 💲 {resumen['valor_ordinarias']:.2f}\n")
            resumen_output.append(f"\nValor recargo nocturno: 💲 {resumen['valor_recargo_nocturno']:.2f}\n")
            resumen_output.append(f"\nValor extra diurna: 💲 {resumen['valor_extra_diurna']:.2f}\n")
            resumen_output.append(f"\nValor extra nocturna: 💲 {resumen['valor_extra_nocturna']:.2f}\n")
            resumen_output.append(f"\nValor festivo diurno: 💲 {resumen['valor_festivo_diurno']:.2f}\n")
            resumen_output.append(f"\nValor festivo nocturno:💲 {resumen['valor_festivo_nocturno']:.2f}\n")
            resumen_output.append(f"\nValor extra festiva diurna: 💲 {resumen['valor_extra_festiva_diurna']:.2f}\n")
            resumen_output.append(f"\nValor extra festiva nocturna: 💲{resumen['valor_extra_festiva_nocturna']:.2f}\n")
            resumen_output.append(f"\nValor descanso: ${resumen['valor_descanso']:.2f}\n")
            resumen_output.append(f"\nSubsidio de transporte:💲 {SUBSIDIO_TRANSPORTE:.2f}\n")
            if resumen['valor_reajuste_ordinario'] > 0:
                resumen_output.append(f"Valor reajuste ordinario: 💲{resumen['valor_reajuste_ordinario']:.2f}\n")
            resumen_output.append(f"\nTOTAL DEVENGADO: 💲 {resumen['total_devengado']:.2f}\n")

            resumen_output.append("\n\n\t--- DEDUCCIONES ---\n\n")
            resumen_output.append(f"Salud (4%): 💲 {deduccion_salud:.2f}\n")
            resumen_output.append(f"Pensión (4%): 💲{deduccion_pension:.2f}\n")
            if deduccion_nombre and deduccion_valor > 0:
                resumen_output.append(f"{deduccion_nombre}: 💲{deduccion_valor:.2f}\n")
            resumen_output.append(f"\nTotal deducciones: 💲 {total_deducciones:.2f}\n")
            resumen_output.append(f"\n\tNETO A PAGAR: 💲{neto_pagar:.2f}\n")

            resumen_html = "".join(resumen_output) # Eliminar la sección de detalle de horas por día

            # Actualizar valores por defecto para que persistan en el formulario
            fecha_inicio_default = corte_inicio_str
            fecha_fin_default = corte_fin_str
            ciclo_inicio_default = ciclo_inicio_seleccionado
            deduccion_nombre_default = deduccion_nombre
            deduccion_valor_default = deduccion_valor
            reajuste_ordinario_horas_default = horas_reajuste_manual

        except Exception as e:
            tb = traceback.format_exc()
            resumen_html = f"Se produjo un error: {e}\n\nDetalles:\n{tb}"

    return render_template(
        "index.html",
        fecha_inicio_default=fecha_inicio_default,
        fecha_fin_default=fecha_fin_default,
        opciones_ciclo=opciones_ciclo,
        ciclo_inicio_default=ciclo_inicio_default,
        deduccion_nombre_default=deduccion_nombre_default,
        deduccion_valor_default=deduccion_valor_default,
        reajuste_ordinario_horas_default=reajuste_ordinario_horas_default,
        resumen_html=resumen_html
    )

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
