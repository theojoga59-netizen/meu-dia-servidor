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
    if not GEMINI_API_KEY:
        return jsonify({
            "erro": "A chave GEMINI_API_KEY não está configurada no servidor."
        }), 500

    try:
        dados = request.get_json(silent=True) or {}

        pergunta = str(dados.get("pergunta", "")).strip()
        contexto = str(dados.get("contexto", "")).strip()

        if not pergunta:
            return jsonify({
                "erro": "Nenhuma pergunta foi enviada."
            }), 400

        prompt = f"""
Você é a inteligência artificial do aplicativo Meu Dia.

Responda em português do Brasil, de forma clara, amigável e objetiva.

Pergunta do usuário:
{pergunta}

Informações do Meu Dia:
{contexto}

Use essas informações quando forem úteis para responder.
"""

        modelos = [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite"
        ]

        ultimo_erro = "Não foi possível obter resposta do Gemini."

        for modelo in modelos:
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

                    resposta_texto = resposta_http.read().decode("utf-8")
                    resposta_json = json.loads(resposta_texto)

                    candidatos = resposta_json.get("candidates", [])

                    if candidatos:
                        conteudo = candidatos[0].get("content", {})
                        partes = conteudo.get("parts", [])

                        if partes:
                            texto = partes[0].get("text", "").strip()

                            if texto:
                                return jsonify({
                                    "resposta": texto
                                })

                    ultimo_erro = "O Gemini não retornou texto."

            except urllib.error.HTTPError as erro:
                corpo_erro = erro.read().decode("utf-8", errors="replace")

                try:
                    erro_json = json.loads(corpo_erro)
                    mensagem = (
                        erro_json
                        .get("error", {})
                        .get("message", "")
                    )
                except Exception:
                    mensagem = corpo_erro

                ultimo_erro = mensagem or f"HTTP {erro.code}"

                if erro.code in (401, 403):
                    return jsonify({
                        "erro": "A chave Gemini não foi aceita pelo Google.",
                        "detalhes": ultimo_erro
                    }), erro.code

                if erro.code == 429:
                    return jsonify({
                        "erro": "O limite do Gemini foi atingido.",
                        "detalhes": ultimo_erro
                    }), 429

                continue

            except Exception as erro:
                ultimo_erro = str(erro)
                continue

        return jsonify({
            "erro": "Não foi possível obter uma resposta do Gemini.",
            "detalhes": ultimo_erro
        }), 500

    except Exception as erro:
        return jsonify({
            "erro": "Erro interno no servidor.",
            "detalhes": str(erro)
        }), 500


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=porta
    )
