from flask import Flask, jsonify, request
import os
import urllib.request
import urllib.error
import json
import time
import random

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Modelos em ordem de tentativa.
# Se um estiver temporariamente indisponivel,
# o servidor tenta automaticamente o proximo.
MODELOS_GEMINI = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite"
]

# Quantas tentativas serao feitas para cada modelo.
TENTATIVAS_POR_MODELO = 2

# Erros que normalmente indicam problema temporario.
ERROS_TEMPORARIOS = [
    408,
    429,
    500,
    502,
    503,
    504
]


@app.route("/")
def inicio():
    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "mensagem": "Servidor funcionando corretamente!",
        "gemini_configurado": bool(GEMINI_API_KEY)
    })


@app.route("/status")
def status():
    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "gemini_configurado": bool(GEMINI_API_KEY),
        "modelos": MODELOS_GEMINI
    })


def montar_url(modelo):
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + modelo
        + ":generateContent?key="
        + GEMINI_API_KEY
    )


def enviar_para_gemini(modelo, dados_envio):

    url = montar_url(modelo)

    ultimo_erro = None

    for tentativa in range(
        1,
        TENTATIVAS_POR_MODELO + 1
    ):

        print("========================================")
        print("MODELO:", modelo)
        print(
            "TENTATIVA:",
            tentativa,
            "DE",
            TENTATIVAS_POR_MODELO
        )
        print("========================================")

        requisicao = urllib.request.Request(
            url,
            data=dados_envio,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:

            with urllib.request.urlopen(
                requisicao,
                timeout=60
            ) as resposta_http:

                resposta_texto = resposta_http.read().decode(
                    "utf-8",
                    errors="replace"
                )

                print("SUCESSO COM O MODELO:", modelo)

                return resposta_texto

        except urllib.error.HTTPError as erro:

            ultimo_erro = erro

            corpo_erro = erro.read().decode(
                "utf-8",
                errors="replace"
            )

            print("========================================")
            print("ERRO DO GOOGLE")
            print("MODELO:", modelo)
            print("CODIGO:", erro.code)
            print("RESPOSTA:", corpo_erro)
            print("========================================")

            # Se nao for um erro temporario,
            # nao adianta ficar repetindo.
            if erro.code not in ERROS_TEMPORARIOS:
                raise erro

            # Se ainda houver outra tentativa neste modelo,
            # espera um pouco e tenta novamente.
            if tentativa < TENTATIVAS_POR_MODELO:

                espera = (
                    (2 ** (tentativa - 1))
                    + random.uniform(0.5, 1.5)
                )

                print(
                    "Erro temporario.",
                    "Nova tentativa em",
                    round(espera, 1),
                    "segundos."
                )

                time.sleep(espera)

                continue

            # Acabaram as tentativas deste modelo.
            print(
                "MODELO",
                modelo,
                "NAO RESPONDEU."
            )

            return None

        except urllib.error.URLError as erro:

            ultimo_erro = erro

            print("========================================")
            print("ERRO DE CONEXAO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))
            print("========================================")

            if tentativa < TENTATIVAS_POR_MODELO:

                espera = (
                    (2 ** (tentativa - 1))
                    + random.uniform(0.5, 1.5)
                )

                print(
                    "Tentando novamente em",
                    round(espera, 1),
                    "segundos."
                )

                time.sleep(espera)

                continue

            return None

        except Exception as erro:

            ultimo_erro = erro

            print("========================================")
            print("ERRO DESCONHECIDO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))
            print("========================================")

            return None

    return None


def extrair_resposta(resposta_texto):

    resposta_json = json.loads(
        resposta_texto
    )

    candidatos = resposta_json.get(
        "candidates",
        []
    )

    if not candidatos:
        return ""

    conteudo = candidatos[0].get(
        "content",
        {}
    )

    partes = conteudo.get(
        "parts",
        []
    )

    if not partes:
        return ""

    textos = []

    for parte in partes:

        texto_parte = parte.get(
            "text",
            ""
        )

        if texto_parte:
            textos.append(
                texto_parte
            )

    texto = "\n".join(
        textos
    ).strip()

    return texto


@app.route("/perguntar", methods=["POST"])
def perguntar():

    print("")
    print("========================================")
    print("PEDIDO RECEBIDO EM /perguntar")
    print("========================================")

    if not GEMINI_API_KEY:

        print(
            "ERRO: GEMINI_API_KEY nao configurada."
        )

        return jsonify({
            "erro": (
                "A chave GEMINI_API_KEY "
                "nao esta configurada no servidor."
            )
        }), 500

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        pergunta = str(
            dados.get(
                "pergunta",
                ""
            )
        ).strip()

        contexto = str(
            dados.get(
                "contexto",
                ""
            )
        ).strip()

        print(
            "Pergunta recebida:",
            pergunta
        )

        if not pergunta:

            return jsonify({
                "erro": (
                    "Nenhuma pergunta "
                    "foi enviada."
                )
            }), 400

        prompt = f"""
Voce e a inteligencia artificial
do aplicativo Meu Dia.

Responda em portugues do Brasil.

Seja clara, amigavel e objetiva.

Nao use asteriscos duplos.

Nao escreva textos desnecessarios.

Pergunta do usuario:
{pergunta}

Informacoes do Meu Dia:
{contexto}

Use essas informacoes quando forem
uteis para responder.
"""

        corpo = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        dados_envio = json.dumps(
            corpo
        ).encode(
            "utf-8"
        )

        resposta_texto = None
        modelo_usado = None

        # ==================================================
        # TENTA TODOS OS MODELOS AUTOMATICAMENTE
        # ==================================================

        for modelo in MODELOS_GEMINI:

            print("")
            print(
                "TENTANDO MODELO:",
                modelo
            )

            resposta_texto = enviar_para_gemini(
                modelo,
                dados_envio
            )

            if resposta_texto:

                try:

                    texto = extrair_resposta(
                        resposta_texto
                    )

                    if texto:

                        # Remove ** caso o modelo envie.
                        texto = texto.replace(
                            "**",
                            ""
                        ).strip()

                        modelo_usado = modelo

                        print("")
                        print(
                            "========================================"
                        )
                        print(
                            "RESPOSTA OBTIDA COM SUCESSO"
                        )
                        print(
                            "MODELO USADO:",
                            modelo_usado
                        )
                        print(
                            "========================================"
                        )

                        return jsonify({
                            "resposta": texto
                        })

                except Exception as erro:

                    print(
                        "Erro ao interpretar "
                        "resposta do modelo:",
                        str(erro)
                    )

            print(
                "Mudando automaticamente para "
                "o proximo modelo..."
            )

        # ==================================================
        # TODOS OS MODELOS FALHARAM
        # ==================================================

        print("")
        print(
            "========================================"
        )
        print(
            "TODOS OS MODELOS FALHARAM"
        )
        print(
            "========================================"
        )

        return jsonify({
            "erro": (
                "O servico de inteligencia "
                "artificial esta temporariamente "
                "indisponivel. Tente novamente."
            )
        }), 503

    except Exception as erro:

        print("")
        print(
            "========================================"
        )
        print(
            "ERRO INTERNO DO SERVIDOR"
        )
        print(
            str(erro)
        )
        print(
            "========================================"
        )

        return jsonify({
            "erro": str(erro)
        }), 500


if __name__ == "__main__":

    porta = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print("")
    print(
        "========================================"
    )
    print(
        "SERVIDOR MEU DIA INICIANDO"
    )
    print(
        "PORTA:",
        porta
    )
    print(
        "MODELOS DISPONIVEIS:"
    )

    for modelo in MODELOS_GEMINI:
        print(
            "-",
            modelo
        )

    print(
        "GEMINI CONFIGURADO:",
        bool(GEMINI_API_KEY)
    )

    print(
        "========================================"
    )

    app.run(
        host="0.0.0.0",
        port=porta
    )
