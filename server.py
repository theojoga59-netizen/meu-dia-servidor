```python
from flask import Flask, request, jsonify, render_template_string
import urllib.request
import urllib.error
import json
import os
import time
import uuid
from datetime import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODELO_RAPIDO = "gemini-3.8-flash"

MODELOS_RESERVA = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

TIMEOUT_NORMAL = 30
TIMEOUT_DESENVOLVEDORA = 90
TENTATIVAS_POR_MODELO = 1

# ============================================================
# ESTADO DA IA DESENVOLVEDORA
# ============================================================

estado_desenvolvedora = {
    "status": "pronta",
    "job_id": None,
    "mensagem": "IA Desenvolvedora pronta.",
    "resultado": None,
    "analise": None,
    "codigo_gerado": None,
    "arquivo": None,
    "autorizacao": False,
    "ultima_acao": None,
    "ultima_atualizacao": None,
    "testes": None
}


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def atualizar_estado(**kwargs):
    estado_desenvolvedora.update(kwargs)
    estado_desenvolvedora["ultima_atualizacao"] = agora()


def chamar_gemini(prompt, modelo=None, timeout=TIMEOUT_NORMAL):
    """
    Envia uma pergunta para a API Gemini.
    """

    if not GEMINI_API_KEY:
        return {
            "ok": False,
            "erro": "GEMINI_API_KEY não configurada no servidor."
        }

    if modelo is None:
        modelo = MODELO_RAPIDO

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + modelo
        + ":generateContent?key="
        + GEMINI_API_KEY
    )

    dados = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "low"
            }
        }
    }

    corpo = json.dumps(dados).encode("utf-8")

    requisicao = urllib.request.Request(
        url,
        data=corpo,
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            requisicao,
            timeout=timeout
        ) as resposta:

            texto = resposta.read().decode("utf-8")

            dados_resposta = json.loads(texto)

            candidatos = dados_resposta.get("candidates", [])

            if not candidatos:
                return {
                    "ok": False,
                    "erro": "Gemini não retornou candidatos."
                }

            partes = candidatos[0].get(
                "content", {}
            ).get(
                "parts", []
            )

            textos = []

            for parte in partes:
                if "text" in parte:
                    textos.append(parte["text"])

            resultado = "\n".join(textos).strip()

            if not resultado:
                return {
                    "ok": False,
                    "erro": "Gemini retornou uma resposta vazia."
                }

            return {
                "ok": True,
                "modelo": modelo,
                "resposta": resultado
            }

    except urllib.error.HTTPError as e:

        try:
            detalhe = e.read().decode("utf-8")
        except Exception:
            detalhe = str(e)

        return {
            "ok": False,
            "erro": f"Erro HTTP {e.code}: {detalhe}"
        }

    except Exception as e:

        return {
            "ok": False,
            "erro": str(e)
        }


def chamar_gemini_com_fallback(
    prompt,
    timeout=TIMEOUT_NORMAL,
    desenvolvedora=False
):
    """
    Tenta o modelo principal e depois modelos reserva.
    """

    modelos = [
        MODELO_RAPIDO
    ] + MODELOS_RESERVA

    ultimo_erro = "Nenhum modelo respondeu."

    for modelo in modelos:

        for tentativa in range(TENTATIVAS_POR_MODELO):

            resultado = chamar_gemini(
                prompt,
                modelo=modelo,
                timeout=timeout
            )

            if resultado.get("ok"):
                return resultado

            ultimo_erro = resultado.get(
                "erro",
                "Erro desconhecido."
            )

            time.sleep(0.5)

    return {
        "ok": False,
        "erro": ultimo_erro
    }


# ============================================================
# PROMPT NORMAL DO MEU DIA
# ============================================================

def criar_prompt_normal(pergunta, contexto):
    return f"""
Você é a IA do aplicativo Meu Dia.

Responda ao usuário em português do Brasil.

Seja útil, clara e direta.

Você recebeu o seguinte contexto do aplicativo:

{contexto}

Pergunta do usuário:

{pergunta}

Responda somente o necessário para ajudar o usuário.
"""


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "mensagem": "Servidor funcionando corretamente!",
        "gemini_configurado": bool(GEMINI_API_KEY),
        "ia_desenvolvedora": "ativa"
    })


# ============================================================
# STATUS
# ============================================================

@app.route("/status")
def status():

    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "gemini_configurado": bool(GEMINI_API_KEY),
        "ia_desenvolvedora": True
    })


@app.route("/saude")
def saude():

    return jsonify({
        "ok": True,
        "servidor": "Meu Dia",
        "gemini_configurado": bool(GEMINI_API_KEY),
        "hora": agora()
    })


# ============================================================
# PERGUNTAR
# ============================================================

@app.route("/perguntar", methods=["POST"])
def perguntar():

    try:

        dados = request.get_json(silent=True) or {}

        pergunta = str(
            dados.get("pergunta", "")
        ).strip()

        contexto = str(
            dados.get("contexto", "")
        ).strip()

        if not pergunta:

            return jsonify({
                "resposta": "Digite uma pergunta."
            }), 400

        prompt = criar_prompt_normal(
            pergunta,
            contexto
        )

        resultado = chamar_gemini_com_fallback(
            prompt,
            timeout=TIMEOUT_NORMAL
        )

        if not resultado.get("ok"):

            return jsonify({
                "resposta": (
                    "Não consegui falar com a IA agora. "
                    + resultado.get("erro", "")
                )
            }), 500

        return jsonify({
            "resposta": resultado["resposta"],
            "modelo": resultado.get("modelo")
        })

    except Exception as e:

        return jsonify({
            "resposta": "Erro no servidor.",
            "erro": str(e)
        }), 500


# ============================================================
# STATUS DA IA DESENVOLVEDORA
# ============================================================

@app.route("/desenvolvedora/status")
def desenvolvedora_status():

    return jsonify({
        "servidor": "Meu Dia",
        "ia_desenvolvedora": True,
        "estado": estado_desenvolvedora
    })


# ============================================================
# PAINEL DA IA DESENVOLVEDORA
# ============================================================

@app.route("/desenvolvedora")
def painel_desenvolvedora():

    html = """
<!DOCTYPE html>
<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>IA Desenvolvedora - Meu Dia</title>

<style>

body {
    font-family: Arial, sans-serif;
    background: #f2f2f2;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 900px;
    margin: auto;
    background: white;
    padding: 25px;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,.15);
}

h1 {
    margin-top: 0;
}

button {
    padding: 12px 18px;
    margin: 5px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
}

.analisar {
    background: #1976d2;
    color: white;
}

.gerar {
    background: #388e3c;
    color: white;
}

.autorizar {
    background: #7b1fa2;
    color: white;
}

.rejeitar {
    background: #d32f2f;
    color: white;
}

button:disabled {
    background: #999;
    cursor: not-allowed;
}

pre {
    white-space: pre-wrap;
    word-wrap: break-word;
    background: #111;
    color: #eee;
    padding: 15px;
    border-radius: 8px;
    overflow-x: auto;
}

.caixa {
    margin-top: 20px;
}

.status {
    padding: 12px;
    background: #eee;
    border-radius: 8px;
    margin-top: 10px;
}

</style>

</head>

<body>

<div class="container">

<h1>🤖 IA Desenvolvedora do Meu Dia</h1>

<p>
Envie um arquivo do projeto Android para a IA analisar.
</p>

<input
    type="file"
    id="arquivo"
    accept=".kt,.java,.xml,.gradle,.txt,.json"
>

<br><br>

<button
    class="analisar"
    onclick="analisarArquivo()"
>
🔍 Analisar código
</button>

<button
    id="botaoGerar"
    class="gerar"
    onclick="gerarCodigo()"
    disabled
>
🛠️ Gerar código
</button>

<button
    id="botaoAutorizar"
    class="autorizar"
    onclick="autorizar()"
    disabled
>
✅ Autorizar
</button>

<button
    id="botaoRejeitar"
    class="rejeitar"
    onclick="rejeitar()"
    disabled
>
❌ Rejeitar
</button>

<div class="caixa">

<h3>Status</h3>

<div id="status" class="status">
Pronta.
</div>

</div>

<div class="caixa">

<h3>Resultado da análise</h3>

<pre id="analise">
Nenhuma análise realizada ainda.
</pre>

</div>

<div class="caixa">

<h3>Código gerado</h3>

<pre id="codigo">
Nenhum código gerado ainda.
</pre>

</div>

</div>

<script>

let ultimaAnalise = null;
let ultimoArquivo = null;

async function analisarArquivo() {

    const input = document.getElementById("arquivo");

    if (!input.files.length) {

        alert("Escolha primeiro um arquivo.");

        return;
    }

    ultimoArquivo = input.files[0];

    const formulario = new FormData();

    formulario.append(
        "arquivo",
        ultimoArquivo
    );

    document.getElementById("status").innerText =
        "🔍 Analisando arquivo...";

    document.getElementById("botaoGerar").disabled = true;

    try {

        const resposta = await fetch(
            "/desenvolvedora/analisar-arquivo",
            {
                method: "POST",
                body: formulario
            }
        );

        const dados = await resposta.json();

        if (!resposta.ok) {

            throw new Error(
                dados.erro || "Erro na análise."
            );
        }

        ultimaAnalise = dados;

        document.getElementById("analise").innerText =
            dados.analise || "Sem análise.";

        document.getElementById("status").innerText =
            "✅ Análise concluída.";

        document.getElementById("botaoGerar").disabled =
            false;

    } catch (erro) {

        document.getElementById("status").innerText =
            "❌ Erro: " + erro.message;

    }
}


async function gerarCodigo() {

    if (!ultimaAnalise || !ultimoArquivo) {

        alert("Faça primeiro a análise.");

        return;
    }

    const formulario = new FormData();

    formulario.append(
        "arquivo",
        ultimoArquivo
    );

    formulario.append(
        "analise",
        ultimaAnalise.analise || ""
    );

    document.getElementById("status").innerText =
        "🛠️ Gerando código...";

    document.getElementById("botaoGerar").disabled =
        true;

    try {

        const resposta = await fetch(
            "/desenvolvedora/ger

