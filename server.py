import os
import json
import urllib.request
import urllib.error
from flask import Flask, jsonify, request

app = Flask(**name**)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

MODELO_GEMINI = "gemini-2.5-flash"

@app.route("/")
def inicio():
return jsonify({
"status": "online",
"servidor": "Meu Dia",
"gemini_configurado": bool(GEMINI_API_KEY),
"mensagem": "Servidor funcionando corretamente!"
})

@app.route("/status")
def status():
return jsonify({
"online": True,
"gemini_configurado": bool(GEMINI_API_KEY)
})

@app.route("/perguntar", methods=["POST"])
def perguntar():
try:
if not GEMINI_API_KEY:
return jsonify({
"erro": "A chave GEMINI_API_KEY não está configurada no Render."
}), 500

```
    dados = request.get_json(silent=True)

    if not dados:
        return jsonify({
            "erro": "Nenhum dado foi enviado."
        }), 400

    pergunta = str(dados.get("pergunta", "")).strip()
    contexto = str(dados.get("contexto", "")).strip()

    if not pergunta:
        return jsonify({
            "erro": "A pergunta está vazia."
        }), 400

    prompt = """
```

Você é o assistente de inteligência artificial do aplicativo Meu Dia.

Responda sempre em português do Brasil.

Pergunta do usuário:
""" + pergunta + """

Contexto do aplicativo Meu Dia:
""" + contexto + """

Use o contexto quando for útil.
Não invente informações.
Seja claro, natural e útil.
"""

```
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + MODELO_GEMINI + ":generateContent"

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

    dados_json = json.dumps(corpo).encode("utf-8")

    requisicao = urllib.request.Request(
        url,
        data=dados_json,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=60) as resposta:
            resposta_texto = resposta.read().decode("utf-8")

    except urllib.error.HTTPError as erro:
        corpo_erro = erro.read().decode("utf-8", errors="replace")

        try:
            erro_json = json.loads(corpo_erro)
            mensagem = erro_json.get("error", {}).get("message", "")

            if not mensagem:
                mensagem = corpo_erro

        except Exception:
            mensagem = corpo_erro

        return jsonify({
            "erro": "Erro do Gemini: " + mensagem
        }), erro.code

    resultado = json.loads(resposta_texto)

    candidatos = resultado.get("candidates", [])

    if not candidatos:
        return jsonify({
            "erro": "O Gemini não retornou uma resposta."
        }), 500

    conteudo = candidatos[0].get("content", {})
    partes = conteudo.get("parts", [])

    textos = []

    for parte in partes:
        texto = parte.get("text")

        if texto:
            textos.append(texto)

    resposta_final = "\n".join(textos).strip()

    if not resposta_final:
        return jsonify({
            "erro": "O Gemini retornou uma resposta vazia."
        }), 500

    return jsonify({
        "resposta": resposta_final
    })

except Exception as erro:
    return jsonify({
        "erro": "Erro interno do servidor: " + str(erro)
    }), 500
```

if **name** == "**main**":
port = int(os.environ.get("PORT", 10000))

```
app.run(
    host="0.0.0.0",
    port=port
)
```
