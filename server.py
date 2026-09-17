from flask import Flask, request, jsonify
import urllib.request
import urllib.error
import json
import os
import time
from datetime import datetime

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODELOS_GEMINI = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash"
]

MAX_TENTATIVAS_POR_MODELO = 2
TEMPOS_ESPERA = [3, 7]


def agora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fazer_requisicao_gemini(modelo, prompt):
    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + modelo
        + ":generateContent"
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
        ]
    }

    corpo = json.dumps(dados).encode("utf-8")

    requisicao = urllib.request.Request(
        url,
        data=corpo,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            requisicao,
            timeout=60
        ) as resposta:

            texto = resposta.read().decode("utf-8")

            dados_resposta = json.loads(texto)

        candidatos = dados_resposta.get(
            "candidates",
            []
        )

        if not candidatos:
            return {
                "ok": False,
                "temporario": False,
                "erro": "O Gemini não retornou candidatos."
            }

        partes = (
            candidatos[0]
            .get("content", {})
            .get("parts", [])
        )

        textos = []

        for parte in partes:
            if "text" in parte:
                textos.append(
                    str(parte["text"])
                )

        resposta_final = "\n".join(
            textos
        ).strip()

        if not resposta_final:
            return {
                "ok": False,
                "temporario": False,
                "erro": "O Gemini retornou uma resposta vazia."
            }

        return {
            "ok": True,
            "resposta": resposta_final,
            "modelo": modelo
        }

    except urllib.error.HTTPError as erro:

        try:
            detalhe = erro.read().decode(
                "utf-8"
            )
        except Exception:
            detalhe = str(erro)

        temporario = erro.code in [
            429,
            500,
            502,
            503,
            504
        ]

        return {
            "ok": False,
            "temporario": temporario,
            "codigo_http": erro.code,
            "erro": (
                "Erro HTTP "
                + str(erro.code)
                + ": "
                + detalhe
            )
        }

    except urllib.error.URLError as erro:

        return {
            "ok": False,
            "temporario": True,
            "erro": (
                "Erro de conexão com o Gemini: "
                + str(erro)
            )
        }

    except TimeoutError:

        return {
            "ok": False,
            "temporario": True,
            "erro": "Tempo limite de conexão com o Gemini."
        }

    except Exception as erro:

        return {
            "ok": False,
            "temporario": False,
            "erro": str(erro)
        }


def chamar_gemini(pergunta, contexto=""):

    if not GEMINI_API_KEY:
        return {
            "ok": False,
            "erro": (
                "GEMINI_API_KEY não configurada "
                "no Render."
            )
        }

    prompt = (
        "Você é a inteligência artificial "
        "do aplicativo Meu Dia.\n"
        "Responda sempre em português do Brasil.\n"
        "Seja clara, útil e objetiva.\n\n"
        "Contexto do aplicativo:\n"
        + str(contexto)
        + "\n\n"
        "Pergunta do usuário:\n"
        + str(pergunta)
    )

    erros = []

    for modelo in MODELOS_GEMINI:

        for tentativa in range(
            MAX_TENTATIVAS_POR_MODELO
        ):

            resultado = fazer_requisicao_gemini(
                modelo,
                prompt
            )

            if resultado.get("ok"):
                return resultado

            erro = resultado.get(
                "erro",
                "Erro desconhecido."
            )

            erros.append(
                modelo
                + " -> "
                + erro
            )

            if resultado.get("temporario"):

                if tentativa < (
                    MAX_TENTATIVAS_POR_MODELO - 1
                ):

                    tempo = TEMPOS_ESPERA[
                        min(
                            tentativa,
                            len(TEMPOS_ESPERA) - 1
                        )
                    ]

                    time.sleep(tempo)

                    continue

            break

    return {
        "ok": False,
        "erro": (
            "Não foi possível obter resposta "
            "de nenhum modelo do Gemini.\n\n"
            + "\n".join(erros)
        )
    }


@app.route("/")
def inicio():

    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "mensagem": (
            "Servidor funcionando corretamente!"
        ),
        "gemini_configurado": bool(
            GEMINI_API_KEY
        ),
        "ia_desenvolvedora": True,
        "modelos": MODELOS_GEMINI,
        "hora": agora()
    })


@app.route("/status")
def status():

    return jsonify({
        "servidor": "Meu Dia",
        "status": "online",
        "gemini_configurado": bool(
            GEMINI_API_KEY
        ),
        "ia_desenvolvedora": True,
        "modelos": MODELOS_GEMINI,
        "hora": agora()
    })


@app.route("/saude")
def saude():

    return jsonify({
        "ok": True,
        "servidor": "Meu Dia",
        "status": "online",
        "gemini_configurado": bool(
            GEMINI_API_KEY
        ),
        "ia_desenvolvedora": True,
        "modelos": MODELOS_GEMINI,
        "hora": agora()
    })


@app.route(
    "/perguntar",
    methods=["POST"]
)
def perguntar():

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

        if not pergunta:

            return jsonify({
                "ok": False,
                "resposta": (
                    "Digite uma pergunta."
                )
            }), 400

        resultado = chamar_gemini(
            pergunta,
            contexto
        )

        if not resultado.get("ok"):

            return jsonify({
                "ok": False,
                "resposta": (
                    "Não consegui falar "
                    "com a IA agora."
                ),
                "erro": resultado.get(
                    "erro"
                )
            }), 503

        return jsonify({
            "ok": True,
            "resposta": resultado[
                "resposta"
            ],
            "modelo": resultado[
                "modelo"
            ]
        })

    except Exception as erro:

        return jsonify({
            "ok": False,
            "resposta": "Erro no servidor.",
            "erro": str(erro)
        }), 500


@app.route("/desenvolvedora")
def desenvolvedora():

    return """
<!DOCTYPE html>
<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>IA Desenvolvedora - Meu Dia</title>

<style>

body {
    background: #101010;
    color: white;
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 1000px;
    margin: auto;
}

.card {
    background: #1d1d1d;
    padding: 20px;
    margin-bottom: 20px;
    border-radius: 12px;
}

h1,
h2 {
    margin-top: 0;
}

input,
textarea {

    width: 100%;

    box-sizing: border-box;

    background: #0b0b0b;

    color: white;

    border: 1px solid #444;

    border-radius: 8px;

    padding: 12px;

    margin-top: 8px;

    margin-bottom: 15px;
}

textarea {
    min-height: 250px;
}

button {

    padding: 12px 18px;

    border: 0;

    border-radius: 8px;

    cursor: pointer;

    font-weight: bold;

    margin: 4px;
}

.analisar {
    background: #2196f3;
    color: white;
}

.gerar {
    background: #4caf50;
    color: white;
}

pre {

    background: #050505;

    padding: 15px;

    border-radius: 8px;

    white-space: pre-wrap;

    word-break: break-word;

    overflow-x: auto;
}

#status {

    padding: 12px;

    background: #292929;

    border-radius: 8px;
}

</style>

</head>

<body>

<div class="container">

<h1>
🤖 IA Desenvolvedora — Meu Dia
</h1>

<div class="card">

<div id="status">
Verificando servidor...
</div>

</div>

<div class="card">

<label>
Nome do arquivo
</label>

<input
    id="arquivo"
    value="MainActivity.kt"
>

<label>
Código do arquivo
</label>

<textarea
    id="codigo"
    placeholder="Cole aqui o código completo..."
></textarea>

<label>
O que a IA deve fazer?
</label>

<textarea
    id="instrucoes"
    placeholder="Exemplo: encontre os erros e gere o arquivo completo corrigido."
></textarea>

<button
    class="analisar"
    onclick="analisar()"
>
🔎 Analisar código
</button>

<button
    class="gerar"
    onclick="gerar()"
>
🛠️ Gerar código corrigido
</button>

</div>

<div class="card">

<h2>
Análise
</h2>

<pre id="resultado">
Nenhuma análise ainda.
</pre>

</div>

<div class="card">

<h2>
Código gerado
</h2>

<pre id="codigoGerado">
Nenhum código gerado ainda.
</pre>

</div>

</div>

<script>

async function verificar() {

    try {

        const resposta = await fetch(
            "/saude"
        );

        const dados =
            await resposta.json();

        document.getElementById(
            "status"
        ).textContent =
            "Servidor: "
            + dados.status
            + " | Gemini configurado: "
            + dados.gemini_configurado
            + " | Modelos disponíveis: "
            + dados.modelos.join(", ");

    } catch (erro) {

        document.getElementById(
            "status"
        ).textContent =
            "Erro ao conectar ao servidor.";

    }

}


async function analisar() {

    const arquivo =
        document.getElementById(
            "arquivo"
        ).value;

    const codigo =
        document.getElementById(
            "codigo"
        ).value;

    if (!codigo.trim()) {

        alert(
            "Cole o código primeiro."
        );

        return;
    }

    document.getElementById(
        "resultado"
    ).textContent =
        "Analisando...";

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/analisar",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        arquivo: arquivo,
                        codigo: codigo
                    })
                }
            );

        const dados =
            await resposta.json();

        document.getElementById(
            "resultado"
        ).textContent =
            dados.analise
            || dados.erro
            || "Nenhuma resposta.";

    } catch (erro) {

        document.getElementById(
            "resultado"
        ).textContent =
            "Erro: "
            + erro;

    }

}


async function gerar() {

    const arquivo =
        document.getElementById(
            "arquivo"
        ).value;

    const codigo =
        document.getElementById(
            "codigo"
        ).value;

    const instrucoes =
        document.getElementById(
            "instrucoes"
        ).value;

    if (!codigo.trim()) {

        alert(
            "Cole o código primeiro."
        );

        return;
    }

    document.getElementById(
        "codigoGerado"
    ).textContent =
        "Gerando código...";

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/gerar",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        arquivo: arquivo,
                        codigo: codigo,
                        instrucoes: instrucoes
                    })
                }
            );

        const dados =
            await resposta.json();

        document.getElementById(
            "codigoGerado"
        ).textContent =
            dados.codigo
            || dados.erro
            || "Nenhum código foi gerado.";

    } catch (erro) {

        document.getElementById(
            "codigoGerado"
        ).textContent =
            "Erro: "
            + erro;

    }

}


verificar();

</script>

</body>

</html>
"""


@app.route(
    "/desenvolvedora/analisar",
    methods=["POST"]
)
def analisar_codigo():

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        arquivo = str(
            dados.get(
                "arquivo",
                "arquivo.txt"
            )
        )

        codigo = str(
            dados.get(
                "codigo",
                ""
            )
        )

        if not codigo.strip():

            return jsonify({
                "ok": False,
                "erro": (
                    "Código não enviado."
                )
            }), 400

        prompt = (
            "Você é a IA Desenvolvedora "
            "do aplicativo Meu Dia.\n\n"

            "Analise o código abaixo procurando:\n"

            "- erros de sintaxe\n"
            "- erros de lógica\n"
            "- problemas de compilação\n"
            "- problemas de imports\n"
            "- problemas de estrutura\n"
            "- problemas que possam causar crash\n"
            "- problemas de compatibilidade\n"
            "- problemas de segurança\n\n"

            "Arquivo: "
            + arquivo
            + "\n\n"

            "Código:\n"
            + codigo
            + "\n\n"

            "Explique os problemas de forma clara "
            "em português do Brasil.\n"

            "Se houver erro, explique como corrigir."
        )

        resultado = chamar_gemini(
            prompt
        )

        if not resultado.get("ok"):

            return jsonify({
                "ok": False,
                "erro": resultado.get(
                    "erro"
                )
            }), 503

        return jsonify({
            "ok": True,
            "analise": resultado[
                "resposta"
            ],
            "modelo": resultado[
                "modelo"
            ]
        })

    except Exception as erro:

        return jsonify({
            "ok": False,
            "erro": str(erro)
        }), 500


@app.route(
    "/desenvolvedora/gerar",
    methods=["POST"]
)
def gerar_codigo():

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        arquivo = str(
            dados.get(
                "arquivo",
                "arquivo.txt"
            )
        )

        codigo = str(
            dados.get(
                "codigo",
                ""
            )
        )

        instrucoes = str(
            dados.get(
                "instrucoes",
                ""
            )
        )

        if not codigo.strip():

            return jsonify({
                "ok": False,
                "erro": (
                    "Código não enviado."
                )
            }), 400

        prompt = (
            "Você é a IA Desenvolvedora "
            "do aplicativo Meu Dia.\n\n"

            "Sua tarefa é corrigir o arquivo "
            "Android abaixo.\n\n"

            "REGRAS IMPORTANTES:\n"

            "1. O usuário vai substituir "
            "o arquivo inteiro.\n"

            "2. Devolva o arquivo COMPLETO "
            "corrigido.\n"

            "3. Nunca devolva somente um trecho.\n"

            "4. Preserve as partes que já "
            "estão funcionando.\n"

            "5. Corrija erros de sintaxe, "
            "imports, lógica e estrutura.\n"

            "6. Não invente arquivos que não "
            "foram solicitados.\n"

            "7. Retorne somente o conteúdo "

