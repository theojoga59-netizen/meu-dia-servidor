from flask import Flask, request, jsonify
import urllib.request
import urllib.error
import json
import os
import time
import ast
import threading
from datetime import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
).strip()

MODELO_GEMINI = "gemini-3.8-flash"

ARQUIVO_PROPRIO = os.path.abspath(__file__)

PASTA_BASE = os.path.dirname(
    ARQUIVO_PROPRIO
)

ARQUIVO_BACKUP = os.path.join(
    PASTA_BASE,
    "server.py.backup"
)

ARQUIVO_NOVO = os.path.join(
    PASTA_BASE,
    "server.py.novo"
)

ARQUIVO_ANALISE = os.path.join(
    PASTA_BASE,
    "ultima_analise.json"
)

INTERVALO_AUTO_ANALISE = 6 * 60 * 60

ULTIMA_ANALISE = {
    "executada": False,
    "hora": None,
    "resultado": None,
    "erro": None
}

LOCK_ANALISE = threading.Lock()


# ============================================================
# UTILITÁRIOS
# ============================================================

def agora():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def salvar_json(caminho, dados):
    try:
        with open(
            caminho,
            "w",
            encoding="utf-8"
        ) as arquivo:
            json.dump(
                dados,
                arquivo,
                ensure_ascii=False,
                indent=2
            )

        return True

    except Exception:
        return False


def carregar_json(caminho):
    try:
        if not os.path.exists(caminho):
            return None

        with open(
            caminho,
            "r",
            encoding="utf-8"
        ) as arquivo:
            return json.load(arquivo)

    except Exception:
        return None


def ler_proprio_codigo():
    try:
        with open(
            ARQUIVO_PROPRIO,
            "r",
            encoding="utf-8"
        ) as arquivo:
            return arquivo.read()

    except Exception as erro:
        raise RuntimeError(
            "Não consegui ler meu próprio código: "
            + str(erro)
        )


def validar_python(codigo):
    try:
        ast.parse(codigo)

        return {
            "ok": True,
            "erro": None
        }

    except SyntaxError as erro:

        return {
            "ok": False,
            "erro": (
                "Erro de sintaxe na linha "
                + str(erro.lineno)
                + ": "
                + str(erro.msg)
            )
        }

    except Exception as erro:

        return {
            "ok": False,
            "erro": str(erro)
        }


# ============================================================
# GEMINI
# ============================================================

def chamar_gemini(
    prompt,
    usar_pesquisa=False
):
    if not GEMINI_API_KEY:

        return {
            "ok": False,
            "erro": (
                "GEMINI_API_KEY não configurada "
                "no Render."
            )
        }

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + MODELO_GEMINI
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

    if usar_pesquisa:

        dados["tools"] = [
            {
                "google_search": {}
            }
        ]

    corpo = json.dumps(
        dados
    ).encode("utf-8")

    requisicao = urllib.request.Request(
        url,
        data=corpo,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    ultima_mensagem = ""

    for tentativa in range(3):

        try:

            with urllib.request.urlopen(
                requisicao,
                timeout=120
            ) as resposta:

                texto = resposta.read().decode(
                    "utf-8"
                )

                dados_resposta = json.loads(
                    texto
                )

            candidatos = dados_resposta.get(
                "candidates",
                []
            )

            if not candidatos:

                return {
                    "ok": False,
                    "erro": (
                        "O Gemini não retornou "
                        "nenhum candidato."
                    )
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
                        str(
                            parte["text"]
                        )
                    )

            resposta_final = "\n".join(
                textos
            ).strip()

            if not resposta_final:

                return {
                    "ok": False,
                    "erro": (
                        "O Gemini retornou "
                        "uma resposta vazia."
                    )
                }

            return {
                "ok": True,
                "resposta": resposta_final,
                "modelo": MODELO_GEMINI
            }

        except urllib.error.HTTPError as erro:

            try:
                detalhe = (
                    erro.read()
                    .decode("utf-8")
                )

            except Exception:

                detalhe = str(erro)

            ultima_mensagem = (
                "Erro HTTP "
                + str(erro.code)
                + ": "
                + detalhe
            )

            if erro.code in [
                429,
                500,
                502,
                503,
                504
            ]:

                if tentativa < 2:

                    time.sleep(
                        3 * (tentativa + 1)
                    )

                    continue

            return {
                "ok": False,
                "erro": ultima_mensagem
            }

        except (
            urllib.error.URLError,
            TimeoutError
        ) as erro:

            ultima_mensagem = (
                "Erro temporário de conexão: "
                + str(erro)
            )

            if tentativa < 2:

                time.sleep(
                    3 * (tentativa + 1)
                )

                continue

            return {
                "ok": False,
                "erro": ultima_mensagem
            }

        except Exception as erro:

            return {
                "ok": False,
                "erro": str(erro)
            }

    return {
        "ok": False,
        "erro": ultima_mensagem
    }


# ============================================================
# PERGUNTAS NORMAIS
# ============================================================

def responder_pergunta(
    pergunta,
    contexto=""
):

    prompt = (
        "Você é a IA do aplicativo Meu Dia.\n"
        "Responda em português do Brasil.\n"
        "Seja clara, objetiva e útil.\n\n"
        "Contexto:\n"
        + contexto
        + "\n\n"
        "Pergunta:\n"
        + pergunta
    )

    return chamar_gemini(
        prompt,
        usar_pesquisa=False
    )


# ============================================================
# IA DESENVOLVEDORA
# ============================================================

def criar_prompt_de_analise(codigo):

    return """
Você é a IA Desenvolvedora oficial do projeto Meu Dia.

Sua função é cuidar tecnicamente do próprio servidor.

Você recebeu abaixo o código atual completo do seu próprio
server.py.

Analise o código procurando:

1. erros de programação;
2. erros de sintaxe;
3. problemas que podem causar queda do servidor;
4. problemas de segurança;
5. problemas de estabilidade;
6. problemas de desempenho;
7. problemas na comunicação com o Gemini;
8. problemas nas rotas Flask;
9. oportunidades reais de melhoria;
10. atualizações importantes das APIs utilizadas;
11. formas de tornar a IA Desenvolvedora mais robusta.

Você pode pesquisar informações atuais na Internet quando
isso for necessário.

IMPORTANTE:

Não invente problemas apenas para alterar o código.

Se o código estiver funcionando corretamente e não houver
uma atualização realmente necessária, diga isso claramente.

Sua resposta deve começar exatamente com:

DECISAO: ATUALIZAR

ou:

DECISAO: NAO_ATUALIZAR

Depois explique:

MOTIVO:
...

MUDANCAS:
...

RISCO:
...

Se decidir que deve atualizar, explique exatamente o que
deveria ser melhorado.

CÓDIGO ATUAL DO SERVIDOR:

""" + codigo


def analisar_proprio_servidor():

    global ULTIMA_ANALISE

    if not LOCK_ANALISE.acquire(
        blocking=False
    ):

        return {
            "ok": False,
            "erro": (
                "Uma análise já está "
                "em andamento."
            )
        }

    try:

        codigo = ler_proprio_codigo()

        prompt = criar_prompt_de_analise(
            codigo
        )

        resultado = chamar_gemini(
            prompt,
            usar_pesquisa=True
        )

        if not resultado.get("ok"):

            ULTIMA_ANALISE = {
                "executada": True,
                "hora": agora(),
                "resultado": None,
                "erro": resultado.get(
                    "erro"
                )
            }

            return resultado

        texto = resultado[
            "resposta"
        ]

        decisao = (
            "ATUALIZAR"
            if "DECISAO: ATUALIZAR"
            in texto.upper()
            else "NAO_ATUALIZAR"
        )

        resultado_final = {
            "ok": True,
            "decisao": decisao,
            "analise": texto,
            "modelo": resultado.get(
                "modelo"
            ),
            "hora": agora()
        }

        ULTIMA_ANALISE = {
            "executada": True,
            "hora": agora(),
            "resultado": resultado_final,
            "erro": None
        }

        salvar_json(
            ARQUIVO_ANALISE,
            ULTIMA_ANALISE
        )

        return resultado_final

    except Exception as erro:

        ULTIMA_ANALISE = {
            "executada": True,
            "hora": agora(),
            "resultado": None,
            "erro": str(erro)
        }

        return {
            "ok": False,
            "erro": str(erro)
        }

    finally:

        LOCK_ANALISE.release()


# ============================================================
# GERAÇÃO DE NOVA VERSÃO
# ============================================================

def gerar_nova_versao():

    codigo_atual = ler_proprio_codigo()

    analise = analisar_proprio_servidor()

    if not analise.get("ok"):

        return analise

    if analise.get(
        "decisao"
    ) != "ATUALIZAR":

        return {
            "ok": True,
            "atualizado": False,
            "mensagem": (
                "A IA analisou o próprio "
                "código e não encontrou "
                "uma atualização necessária."
            ),
            "analise": analise
        }

    prompt = """
Você é a IA Desenvolvedora do Meu Dia.

A análise anterior determinou que existe
uma atualização necessária.

Agora gere uma nova versão COMPLETA
do arquivo server.py.

REGRAS OBRIGATÓRIAS:

1. Retorne o arquivo COMPLETO.
2. Não retorne explicações.
3. Não use ```python.
4. Preserve as funções que já funcionam.
5. Preserve as rotas existentes.
6. Preserve GEMINI_API_KEY.
7. Preserve /saude.
8. Preserve /status.
9. Preserve /perguntar.
10. Preserve /desenvolvedora.
11. O arquivo precisa continuar sendo Flask.
12. Não remova funcionalidades sem motivo.
13. Corrija apenas o que realmente precisa
    ser corrigido.
14. O resultado precisa ser Python válido.

ANÁLISE:

""" + analise.get(
        "analise",
        ""
    ) + """

CÓDIGO ATUAL COMPLETO:

""" + codigo_atual

    resultado = chamar_gemini(
        prompt,
        usar_pesquisa=False
    )

    if not resultado.get("ok"):

        return resultado

    codigo_novo = resultado[
        "resposta"
    ].strip()

    if "```" in codigo_novo:

        partes = codigo_novo.split(
            "```"
        )

        if len(partes) >= 3:

            codigo_novo = partes[1]

            linhas = (
                codigo_novo.splitlines()
            )

            if linhas:

                primeira = (
                    linhas[0]
                    .strip()
                    .lower()
                )

                if primeira in [
                    "python",
                    "py"
                ]:

                    codigo_novo = "\n".join(
                        linhas[1:]
                    )

    codigo_novo = codigo_novo.strip()

    if not codigo_novo:

        return {
            "ok": False,
            "erro": (
                "A IA não gerou "
                "um código novo."
            )
        }

    validacao = validar_python(
        codigo_novo
    )

    if not validacao.get("ok"):

        return {
            "ok": False,
            "erro": (
                "A IA gerou código inválido. "
                "A versão atual não foi alterada.\n"
                + validacao.get(
                    "erro",
                    ""
                )
            )
        }

    try:

        with open(
            ARQUIVO_NOVO,
            "w",
            encoding="utf-8"
        ) as arquivo:

            arquivo.write(
                codigo_novo
            )

    except Exception as erro:

        return {
            "ok": False,
            "erro": (
                "Não consegui salvar "
                "a nova versão: "
                + str(erro)
            )
        }

    return {
        "ok": True,
        "atualizado": False,
        "nova_versao_pronta": True,
        "arquivo_novo": ARQUIVO_NOVO,
        "mensagem": (
            "Nova versão criada e validada. "
            "A versão atual ainda não foi "
            "substituída."
        ),
        "modelo": resultado.get(
            "modelo"
        ),
        "analise": analise.get(
            "analise"
        )
    }


# ============================================================
# BACKUP
# ============================================================

def criar_backup():

    try:

        codigo = ler_proprio_codigo()

        with open(
            ARQUIVO_BACKUP,
            "w",
            encoding="utf-8"
        ) as arquivo:

            arquivo.write(
                codigo
            )

        return {
            "ok": True,
            "arquivo": ARQUIVO_BACKUP
        }

    except Exception as erro:

        return {
            "ok": False,
            "erro": str(erro)
        }


# ============================================================
# APLICAÇÃO DA NOVA VERSÃO
# ============================================================

def aplicar_nova_versao():

    if not os.path.exists(
        ARQUIVO_NOVO
    ):

        return {
            "ok": False,
            "erro": (
                "Não existe uma nova "
                "versão preparada."
            )
        }

    try:

        with open(
            ARQUIVO_NOVO,
            "r",
            encoding="utf-8"
        ) as arquivo:

            codigo_novo = arquivo.read()

        validacao = validar_python(
            codigo_novo
        )

        if not validacao.get("ok"):

            return {
                "ok": False,
                "erro": (
                    "A nova versão "
                    "não passou na validação."
                )
            }

        backup = criar_backup()

        if not backup.get("ok"):

            return backup

        with open(
            ARQUIVO_PROPRIO,
            "w",
            encoding="utf-8"
        ) as arquivo:

            arquivo.write(
                codigo_novo
            )

        return {
            "ok": True,
            "aplicado": True,
            "mensagem": (
                "A nova versão foi aplicada. "
                "O backup da versão anterior "
                "foi criado."
            ),
            "backup": ARQUIVO_BACKUP
        }

    except Exception as erro:

        return {
            "ok": False,
            "erro": (
                "Erro ao aplicar atualização: "
                + str(erro)
            )
        }


# ============================================================
# ROTAS PRINCIPAIS
# ============================================================

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
        "auto_analise": True,
        "modelo": MODELO_GEMINI,
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
        "auto_analise": True,
        "modelo": MODELO_GEMINI,
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
        "auto_analise": True,
        "modelo": MODELO_GEMINI,
        "ultima_analise": ULTIMA_ANALISE,
        "hora": agora()
    })


# ============================================================
# PERGUNTAR À IA
# ============================================================

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

        resultado = responder_pergunta(
            pergunta,
            contexto
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
            "erro": str(erro)
        }), 500


# ============================================================
# IA DESENVOLVEDORA - PAINEL
# ============================================================

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

button {
    padding: 14px 20px;
    border: 0;
    border-radius: 8px;
    cursor: pointer;
    font-weight: bold;
    margin: 5px;
}

.analisar {
    background: #2196f3;
    color: white;
}

.gerar {
    background: #4caf50;
    color: white;
}

.aplicar {
    background: #ff9800;
    color: black;
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
    padding: 15px;
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

<h2>
🧠 Desenvolvimento automático
</h2>

<p>
A IA pode analisar o próprio código
do servidor e procurar melhorias.
</p>

<button
    class="analisar"
    onclick="analisarServidor()"
>
🔎 Analisar meu próprio código
</button>

<button
    class="gerar"
    onclick="gerarAtualizacao()"
>
🛠️ Criar atualização
</button>

<button
    class="aplicar"
    onclick="aplicarAtualizacao()"
>
🚀 Aplicar atualização preparada
</button>

</div>

<div class="card">

<h2>
📋 Resultado da análise
</h2>

<pre id="resultado">
Nenhuma análise executada.
</pre>

</div>

<div class="card">

<h2>
📦 Atualização
</h2>

<pre id="atualizacao">
Nenhuma atualização preparada.
</pre>

</div>

</div>

<script>

async function verificar() {

    try {

        const resposta =
            await fetch("/saude");

        const dados =
            await resposta.json();

        document.getElementById(
            "status"
        ).textContent =
            "Servidor: "
            + dados.status
            + " | Gemini: "
            + dados.gemini_configurado
            + " | IA Desenvolvedora: "
            + dados.ia_desenvolvedora
            + " | Modelo: "
            + dados.modelo;

    } catch (erro) {

        document.getElementById(
            "status"
        ).textContent =
            "Erro ao conectar ao servidor.";

    }

}


async function analisarServidor() {

    document.getElementById(
        "resultado"
    ).textContent =
        "A IA está lendo e analisando o próprio código...";

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/analisar-servidor",
                {
                    method: "POST"
                }
            );

        const dados =
            await resposta.json();

        document.getElementById(
            "resultado"
        ).textContent =
            dados.analise
            || dados.erro
            || JSON.stringify(
                dados,
                null,
                2
            );

    } catch (erro) {

        document.getElementById(
            "resultado"
        ).textContent =
            "Erro: "
            + erro;

    }

}


async function gerarAtualizacao() {

    document.getElementById(
        "atualizacao"
    ).textContent =
        "A IA está analisando o código e preparando uma nova versão...";

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/gerar-atualizacao",
                {
                    method: "POST"
                }
            );

        const dados =
            await resposta.json();

        document.getElementById(
            "atualizacao"
        ).textContent =
            JSON.stringify(
                dados,
                null,
                2
            );

    } catch (erro) {

        document.getElementById(
            "atualizacao"
        ).textContent =
            "Erro: "
            + erro;

    }

}


async function aplicarAtualizacao() {

    const confirmar =
        confirm(
            "A IA já preparou uma nova versão?\\n\\n"
            + "A versão atual terá um backup antes da substituição."
        );

    if (!confirmar) {
        return;
    }

    document.getElementById(
        "atualizacao"
    ).textContent =
        "Aplicando atualização...";

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/aplicar",
                {
                    method: "POST"
                }
            );

        const dados =
            await resposta.json();

        document.getElementById(
            "atualizacao"
        ).textContent =
            JSON.stringify(
                dados,
                null,
                2
            );

    } catch (erro) {

        document.getElementById(
            "atualizacao"
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


# ============================================================
# ROTAS DA IA DESENVOLVEDORA
# ============================================================

@app.route(
    "/desenvolvedora/analisar-servidor",
    methods=["POST"]
)
def rota_analisar_servidor():

    resultado = (
        analisar_proprio_servidor()
    )

    if not resultado.get("ok"):

        return jsonify(
            resultado
        ), 503

    return jsonify(
        resultado
    )


@app.route(
    "/desenvolvedora/gerar-atualizacao",
    methods=["POST"]
)
def rota_gerar_atualizacao():

    resultado = (
        gerar_nova_versao()
    )

    if not resultado.get("ok"):

        return jsonify(
            resultado
        ), 500

    return jsonify(
        resultado
    )


@app.route(
    "/desenvolvedora/aplicar",
    methods=["POST"]
)
def rota_aplicar():

    resultado = (
        aplicar_nova_versao()
    )

    if not resultado.get("ok"):

        return jsonify(
            resultado
        ), 500

    return jsonify(
        resultado
    )


@app.route(
    "/desenvolvedora/ultima-analise"
)
def ultima_analise():

    dados = carregar_json(
        ARQUIVO_ANALISE
    )

    if dados is None:

        dados = ULTIMA_ANALISE

    return jsonify({
        "ok": True,
        "analise": dados
    })


# ============================================================
# ANÁLISE AUTOMÁTICA
# ============================================================

def rotina_automatica():

    while True:

        try:

            time.sleep(
                INTERVALO_AUTO_ANALISE
            )

            analisar_proprio_servidor()

        except Exception:
            pass


def iniciar_rotina_automatica():

    thread = threading.Thread(
        target=rotina_automatica,
        daemon=True
    )

    thread.start()


# ============================================================
# ERROS
# ============================================================

@app.errorhandler(404)
def erro_404(erro):

    return jsonify({
        "ok": False,
        "erro": "Rota não encontrada."
    }), 404


@app.errorhandler(500)
def erro_500(erro):

    return jsonify({
        "ok": False,
        "erro": "Erro interno do servidor."
    }), 500


# ============================================================
# INICIALIZAÇÃO
# ============================================================

iniciar_rotina_automatica()


if __name__ == "__main__":

    porta = int(
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=porta
    )
