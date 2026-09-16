from flask import Flask, jsonify, request
import os
import urllib.request
import urllib.error
import json

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


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
        "gemini_configurado": bool(GEMINI_API_KEY)
    })


@app.route("/perguntar", methods=["POST"])
def perguntar():

    print("========================================")
    print("PEDIDO RECEBIDO EM /perguntar")
    print("========================================")

    if not GEMINI_API_KEY:
        print("ERRO: GEMINI_API_KEY nao configurada.")

        return jsonify({
            "erro": "A chave GEMINI_API_KEY nao esta configurada no servidor."
        }), 500

    try:
        dados = request.get_json(silent=True) or {}

        pergunta = str(dados.get("pergunta", "")).strip()
        contexto = str(dados.get("contexto", "")).strip()

        print("Pergunta recebida:", pergunta)

        if not pergunta:
            return jsonify({
                "erro": "Nenhuma pergunta foi enviada."
            }), 400

        prompt = f"""
Voce e a inteligencia artificial do aplicativo Meu Dia.

Responda em portugues do Brasil, de forma clara, amigavel e objetiva.

Pergunta do usuario:
{pergunta}

Informacoes do Meu Dia:
{contexto}

Use essas informacoes quando forem uteis para responder.
"""

        modelo = "gemini-3.6-flash"

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + modelo
            + ":generateContent?key="
            + GEMINI_API_KEY
        )

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

        dados_envio = json.dumps(corpo).encode("utf-8")

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

                print("RESPOSTA DO GOOGLE:")
                print(resposta_texto)

                resposta_json = json.loads(resposta_texto)

                candidatos = resposta_json.get("candidates", [])

                if not candidatos:
                    print("O GEMINI NAO RETORNOU CANDIDATOS.")

                    return jsonify({
                        "erro": "O Gemini nao retornou uma resposta.",
                        "detalhes": resposta_texto
                    }), 500

                conteudo = candidatos[0].get(
                    "content",
                    {}
                )

                partes = conteudo.get(
                    "parts",
                    []
                )

                if not partes:
                    print("O GEMINI NAO RETORNOU PARTES DE TEXTO.")

                    return jsonify({
                        "erro": "O Gemini nao retornou texto.",
                        "detalhes": resposta_texto
                    }), 500

                texto = partes[0].get(
                    "text",
                    ""
                ).strip()

                if not texto:
                    return jsonify({
                        "erro": "O Gemini retornou uma resposta vazia.",
                        "detalhes": resposta_texto
                    }), 500

                print("SUCESSO! GEMINI RESPONDEU.")

                return jsonify({
                    "resposta": texto
                })

        except urllib.error.HTTPError as erro:

            corpo_erro = erro.read().decode(
                "utf-8",
                errors="replace"
            )

            print("========================================")
            print("ERRO DO GOOGLE")
            print("CODIGO:", erro.code)
            print("RESPOSTA:", corpo_erro)
            print("========================================")

            try:

                erro_json = json.loads(corpo_erro)

                mensagem = (
                    erro_json
                    .get("error", {})
                    .get("message", "")
                )

            except Exception:

                mensagem = corpo_erro

            if not mensagem:
                mensagem = "Erro desconhecido do Google."

            return jsonify({
                "erro": mensagem
            }), erro.code

        except Exception as erro:

            print("========================================")
            print("ERRO AO ACESSAR O GEMINI")
            print(str(erro))
            print("========================================")

            return jsonify({
                "erro": str(erro)
            }), 500

    except Exception as erro:

        print("========================================")
        print("ERRO INTERNO DO SERVIDOR")
        print(str(erro))
        print("========================================")

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

    app.run(
        host="0.0.0.0",
        port=porta
    )
