"use strict";

(function configurarNumeros(global) {
    function textoLimpio(valor) {
        return String(valor ?? "")
            .trim()
            .replace(/\u00a0/g, "")
            .replace(/\s+/g, "")
            .replace(/[^\d.,()+-]/g, "");
    }

    function normalizarSigno(texto) {
        if (
            texto.startsWith("(")
            && texto.endsWith(")")
        ) {
            return `-${texto.slice(1, -1)}`;
        }

        return texto.startsWith("+")
            ? texto.slice(1)
            : texto;
    }

    function normalizarMoneda(valor) {
        if (
            typeof valor === "number"
            && Number.isFinite(valor)
        ) {
            return String(valor);
        }

        let texto = normalizarSigno(
            textoLimpio(valor)
        );

        if (!texto) {
            throw new Error(
                "Ingresa un monto válido."
            );
        }

        const coma = texto.lastIndexOf(",");
        const punto = texto.lastIndexOf(".");
        let separadorDecimal = null;

        if (coma >= 0 && punto >= 0) {
            separadorDecimal = coma > punto
                ? ","
                : ".";
        } else if (coma >= 0) {
            const agrupado = /^[+-]?\d{1,3}(,\d{3})+$/
                .test(texto);

            separadorDecimal = agrupado
                ? null
                : ",";
        } else if (punto >= 0) {
            const agrupado = /^[+-]?\d{1,3}(\.\d{3})+$/
                .test(texto);

            separadorDecimal = agrupado
                ? null
                : ".";
        }

        if (separadorDecimal) {
            const posicion = texto.lastIndexOf(
                separadorDecimal
            );
            const entero = texto
                .slice(0, posicion)
                .replace(/[.,]/g, "");
            const decimales = texto
                .slice(posicion + 1)
                .replace(/[.,]/g, "");

            texto = decimales
                ? `${entero}.${decimales}`
                : entero;
        } else {
            texto = texto.replace(/[.,]/g, "");
        }

        if (!/^-?\d+(\.\d+)?$/.test(texto)) {
            throw new Error(
                "Ingresa un monto válido."
            );
        }

        const numero = Number(texto);

        if (!Number.isFinite(numero)) {
            throw new Error(
                "El monto est? fuera del rango permitido."
            );
        }

        return texto;
    }

    function numeroMoneda(valor) {
        return Number(normalizarMoneda(valor));
    }

    global.NexuNumeros = Object.freeze({
        normalizarMoneda,
        numeroMoneda,
    });
}(window));
