"use strict";

(function configurarEscaner(global) {
    const FORMATOS = Object.freeze([
        "aztec",
        "codabar",
        "code_39",
        "code_93",
        "code_128",
        "data_matrix",
        "ean_8",
        "ean_13",
        "itf",
        "pdf417",
        "qr_code",
        "upc_a",
        "upc_e",
    ]);

    function mensajeError(error) {
        const nombre = String(error?.name || "");

        if (
            nombre === "NotAllowedError"
            || nombre === "SecurityError"
        ) {
            return (
                "Permiso de c\u00e1mara rechazado. "
                + "Habil\u00edtalo en el navegador."
            );
        }

        if (
            nombre === "NotFoundError"
            || nombre === "DevicesNotFoundError"
        ) {
            return (
                "No encontramos una c\u00e1mara "
                + "disponible."
            );
        }

        if (
            nombre === "NotReadableError"
            || nombre === "TrackStartError"
        ) {
            return (
                "La c\u00e1mara est\u00e1 siendo usada "
                + "por otra aplicaci\u00f3n."
            );
        }

        if (nombre === "OverconstrainedError") {
            return (
                "La c\u00e1mara no admite la "
                + "configuraci\u00f3n solicitada."
            );
        }

        return (
            "No fue posible iniciar la c\u00e1mara. "
            + "Revisa los permisos del navegador."
        );
    }

    class EscanerCodigos {
        constructor({
            video,
            alDetectar,
            alInformar,
        }) {
            this.video = video;
            this.alDetectar = alDetectar;
            this.alInformar = alInformar;
            this.activo = false;
            this.flujo = null;
            this.detector = null;
            this.lector = null;
            this.controles = null;
            this.fotograma = null;
            this.bloqueado = false;
        }

        informar(mensaje, error = false) {
            this.alInformar?.(mensaje, error);
        }

        async iniciar() {
            this.detener();

            if (!global.isSecureContext) {
                this.informar(
                    "La c\u00e1mara requiere una "
                    + "conexi\u00f3n HTTPS segura.",
                    true,
                );
                return false;
            }

            if (
                !navigator.mediaDevices
                || !navigator.mediaDevices.getUserMedia
            ) {
                this.informar(
                    "Este navegador no permite acceder "
                    + "a la c\u00e1mara.",
                    true,
                );
                return false;
            }

            this.video.muted = true;
            this.video.autoplay = true;
            this.video.setAttribute(
                "playsinline",
                "",
            );

            try {
                if ("BarcodeDetector" in global) {
                    await this.iniciarNativo();
                } else {
                    await this.iniciarZxing();
                }

                return true;
            } catch (error) {
                this.detener();
                this.informar(
                    mensajeError(error),
                    true,
                );
                return false;
            }
        }

        async iniciarNativo() {
            let soportados = FORMATOS;

            if (
                typeof global.BarcodeDetector
                    .getSupportedFormats
                === "function"
            ) {
                soportados = await global
                    .BarcodeDetector
                    .getSupportedFormats();
            }

            const formatos = FORMATOS.filter(
                (formato) =>
                    soportados.includes(formato)
            );

            this.detector = formatos.length
                ? new global.BarcodeDetector({
                    formats: formatos,
                })
                : new global.BarcodeDetector();

            this.flujo = await navigator
                .mediaDevices
                .getUserMedia({
                    audio: false,
                    video: {
                        facingMode: {
                            ideal: "environment",
                        },
                        width: {
                            ideal: 1280,
                        },
                        height: {
                            ideal: 720,
                        },
                    },
                });

            this.video.srcObject = this.flujo;
            await this.video.play();

            this.activo = true;
            this.informar(
                "Alinea el c\u00f3digo dentro "
                + "del marco.",
            );
            this.detectarNativo();
        }

        async iniciarZxing() {
            if (
                !global.ZXingBrowser
                || !global.ZXingBrowser
                    .BrowserMultiFormatReader
            ) {
                throw new Error(
                    "ZXing no est\u00e1 disponible."
                );
            }

            this.lector = new global
                .ZXingBrowser
                .BrowserMultiFormatReader();

            this.activo = true;
            this.informar(
                "Alinea el c\u00f3digo dentro "
                + "del marco.",
            );

            this.controles = await this.lector
                .decodeFromConstraints(
                    {
                        audio: false,
                        video: {
                            facingMode: {
                                ideal: "environment",
                            },
                            width: {
                                ideal: 1280,
                            },
                            height: {
                                ideal: 720,
                            },
                        },
                    },
                    this.video,
                    (resultado) => {
                        if (
                            resultado
                            && this.activo
                        ) {
                            const texto =
                                typeof resultado
                                    .getText
                                === "function"
                                    ? resultado.getText()
                                    : resultado.text;

                            this.detectado(texto);
                        }
                    },
                );
        }

        async detectarNativo() {
            if (
                !this.activo
                || !this.detector
            ) {
                return;
            }

            if (this.video.readyState >= 2) {
                try {
                    const resultados =
                        await this.detector.detect(
                            this.video
                        );

                    if (resultados.length) {
                        this.detectado(
                            resultados[0].rawValue
                        );
                        return;
                    }
                } catch (_error) {
                    this.informar(
                        "Mant\u00e9n el c\u00f3digo "
                        + "estable y con buena luz.",
                    );
                }
            }

            if (this.activo) {
                this.fotograma =
                    global.requestAnimationFrame(
                        () => this.detectarNativo()
                    );
            }
        }

        detectado(valor) {
            if (
                this.bloqueado
                || !this.activo
            ) {
                return;
            }

            const codigo = String(
                valor || ""
            ).trim();

            if (!codigo) {
                return;
            }

            this.bloqueado = true;

            Promise.resolve(
                this.alDetectar?.(codigo)
            ).finally(() => {
                global.setTimeout(() => {
                    this.bloqueado = false;
                }, 700);
            });
        }

        detener() {
            this.activo = false;
            this.bloqueado = false;

            if (this.fotograma) {
                global.cancelAnimationFrame(
                    this.fotograma
                );
                this.fotograma = null;
            }

            try {
                this.controles?.stop();
            } catch (_error) {
                // El lector ya estaba detenido.
            }

            this.controles = null;

            this.flujo
                ?.getTracks()
                .forEach(
                    (pista) => pista.stop()
                );
            this.flujo = null;

            this.video?.srcObject
                ?.getTracks?.()
                .forEach(
                    (pista) => pista.stop()
                );

            if (this.video) {
                this.video.pause();
                this.video.srcObject = null;
            }

            this.detector = null;
            this.lector = null;
        }
    }

    global.NexuEscaner = Object.freeze({
        crear(opciones) {
            return new EscanerCodigos(
                opciones
            );
        },
    });
}(window));
