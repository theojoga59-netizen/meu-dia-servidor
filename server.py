from flask import Flask, jsonify, request, render_template_string
import os
import urllib.request
import urllib.error
import json
import time
import uuid
from datetime import datetime


# ============================================================
# SERVIDOR MEU DIA
# ============================================================

app = Flask(__name__)

SERVIDOR_NOME = "Meu Dia"

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
)


# ============================================================
# CONFIGURACAO DOS MODELOS
# ============================================================

MODELO_RAPIDO = "gemini-3.8-flash"

MODELOS_FALLBACK = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite"
]

NIVEL_PENSAMENTO_NORMAL = "low"

NIVEL_PENSAMENTO_DESENVOLVEDORA = "medium"

TIMEOUT_NORMAL = 30

TIMEOUT_DESENVOLVEDORA = 90

TENTATIVAS_POR_MODELO = 1

ERROS_TEMPORARIOS = [
    408,
    429,
    500,
    502,
    503,
    504
]

# Limite de arquivo enviado para analise.
# 5 MB e suficiente para os arquivos de codigo
# que vamos analisar nesta primeira etapa.
TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024


# ============================================================
# ESTADO DA IA DESENVOLVEDORA
# ============================================================

ESTADO_DESENVOLVEDORA = {
    "status": "pronta",
    "job_id": None,
    "ultima_acao": None,
    "ultima_atualizacao": None,
    "mensagem": "IA Desenvolvedora pronta.",
    "autorizacao": False,
    "testes": None,
    "resultado": None,
    "arquivo": None
}


# ============================================================
# DATA E HORA
# ============================================================

def agora():
    return datetime.utcnow().isoformat() + "Z"


# ============================================================
# URL GEMINI
# ============================================================

def montar_url(modelo):

    return (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + modelo
        + ":generateContent?key="
        + GEMINI_API_KEY
    )


# ============================================================
# CORPO DA REQUISICAO GEMINI
# ============================================================

def montar_corpo_gemini(
    texto,
    nivel_pensamento="low"
):

    return {
        "contents": [
            {
                "parts": [
                    {
                        "text": texto
                    }
                ]
            }
        ],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": nivel_pensamento
            }
        }
    }


# ============================================================
# EXTRAIR RESPOSTA
# ============================================================

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

        texto = parte.get(
            "text",
            ""
        )

        if texto:
            textos.append(texto)

    return "\n".join(
        textos
    ).strip()


# ============================================================
# ENVIAR PARA GEMINI
# ============================================================

def enviar_para_gemini(
    modelo,
    dados_envio,
    timeout
):

    url = montar_url(
        modelo
    )

    for tentativa in range(
        1,
        TENTATIVAS_POR_MODELO + 1
    ):

        print("")
        print("========================================")
        print("GEMINI")
        print("MODELO:", modelo)
        print("TENTATIVA:", tentativa)
        print("TIMEOUT:", timeout)
        print("========================================")

        requisicao = urllib.request.Request(
            url,
            data=dados_envio,
            headers={
                "Content-Type":
                    "application/json"
            },
            method="POST"
        )

        try:

            inicio = time.time()

            with urllib.request.urlopen(
                requisicao,
                timeout=timeout
            ) as resposta_http:

                resposta_texto = (
                    resposta_http
                    .read()
                    .decode(
                        "utf-8",
                        errors="replace"
                    )
                )

            duracao = round(
                time.time() - inicio,
                2
            )

            print(
                "Gemini respondeu em:",
                duracao,
                "segundos."
            )

            return resposta_texto

        except urllib.error.HTTPError as erro:

            corpo_erro = (
                erro
                .read()
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

            print("")
            print("========================================")
            print("ERRO GOOGLE")
            print("MODELO:", modelo)
            print("CODIGO:", erro.code)
            print("RESPOSTA:", corpo_erro)
            print("========================================")

            if erro.code not in ERROS_TEMPORARIOS:
                return None

            return None

        except urllib.error.URLError as erro:

            print("")
            print("========================================")
            print("ERRO DE CONEXAO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))
            print("========================================")

            return None

        except Exception as erro:

            print("")
            print("========================================")
            print("ERRO DESCONHECIDO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))
            print("========================================")

            return None

    return None


# ============================================================
# GEMINI NORMAL
# ============================================================

def chamar_gemini_normal(prompt):

    corpo = montar_corpo_gemini(
        prompt,
        NIVEL_PENSAMENTO_NORMAL
    )

    dados_envio = json.dumps(
        corpo
    ).encode("utf-8")

    modelos = [
        MODELO_RAPIDO
    ] + MODELOS_FALLBACK

    for modelo in modelos:

        resposta_texto = (
            enviar_para_gemini(
                modelo,
                dados_envio,
                TIMEOUT_NORMAL
            )
        )

        if not resposta_texto:
            continue

        try:

            texto = extrair_resposta(
                resposta_texto
            )

            if texto:

                return texto.replace(
                    "**",
                    ""
                ).strip()

        except Exception as erro:

            print(
                "Erro interpretando resposta:",
                str(erro)
            )

    return None


# ============================================================
# GEMINI DESENVOLVEDORA
# ============================================================

def chamar_gemini_desenvolvedora(prompt):

    corpo = montar_corpo_gemini(
        prompt,
        NIVEL_PENSAMENTO_DESENVOLVEDORA
    )

    dados_envio = json.dumps(
        corpo
    ).encode("utf-8")

    modelos = [
        MODELO_RAPIDO,
        "gemini-3.7-flash",
        "gemini-3.6-flash"
    ]

    for modelo in modelos:

        resposta_texto = (
            enviar_para_gemini(
                modelo,
                dados_envio,
                TIMEOUT_DESENVOLVEDORA
            )
        )

        if not resposta_texto:
            continue

        try:

            texto = extrair_resposta(
                resposta_texto
            )

            if texto:
                return texto.strip()

        except Exception as erro:

            print(
                "Erro interpretando IA:",
                str(erro)
            )

    return None


# ============================================================
# PAGINA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "status": "online",
        "mensagem":
            "Servidor funcionando corretamente!",
        "gemini_configurado":
            bool(GEMINI_API_KEY),
        "ia_desenvolvedora":
            "ativa"
    })


# ============================================================
# STATUS
# ============================================================

@app.route("/status")
def status():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "status": "online",
        "gemini_configurado":
            bool(GEMINI_API_KEY),
        "modelo_rapido":
            MODELO_RAPIDO,
        "modelos_fallback":
            MODELOS_FALLBACK,
        "ia_desenvolvedora":
            ESTADO_DESENVOLVEDORA
    })


# ============================================================
# SAUDE
# ============================================================

@app.route(
    "/saude",
    methods=["GET"]
)
def saude():

    return jsonify({
        "servidor":
            SERVIDOR_NOME,
        "online":
            True,
        "gemini":
            bool(GEMINI_API_KEY),
        "ia_desenvolvedora":
            True,
        "hora":
            agora()
    })


# ============================================================
# ASSISTENTE NORMAL
# ============================================================

@app.route(
    "/perguntar",
    methods=["POST"]
)
def perguntar():

    print("")
    print("========================================")
    print("PEDIDO RECEBIDO EM /perguntar")
    print("========================================")

    if not GEMINI_API_KEY:

        return jsonify({
            "erro":
                "A chave GEMINI_API_KEY "
                "nao esta configurada no servidor."
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

        if not pergunta:

            return jsonify({
                "erro":
                    "Nenhuma pergunta foi enviada."
            }), 400

        prompt = f"""
Voce e a inteligencia artificial
do aplicativo Meu Dia.

Responda em portugues do Brasil.

Seja clara, amigavel e objetiva.

Responda rapidamente.

Nao use asteriscos duplos.

Nao escreva textos desnecessarios.

Pergunta do usuario:
{pergunta}

Informacoes atuais do aplicativo Meu Dia:
{contexto}

Use essas informacoes quando forem
uteis para responder.

Se nao houver informacao suficiente,
diga claramente o que esta faltando.
"""

        resposta = chamar_gemini_normal(
            prompt
        )

        if resposta:

            return jsonify({
                "resposta":
                    resposta,
                "modelo":
                    MODELO_RAPIDO
            })

        return jsonify({
            "erro":
                "A inteligencia artificial "
                "esta temporariamente indisponivel. "
                "Tente novamente."
        }), 503

    except Exception as erro:

        print(
            "ERRO /perguntar:",
            str(erro)
        )

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# STATUS DA IA DESENVOLVEDORA
# ============================================================

@app.route(
    "/desenvolvedora/status",
    methods=["GET"]
)
def desenvolvedora_status():

    return jsonify({
        "servidor":
            SERVIDOR_NOME,
        "ia_desenvolvedora":
            True,
        "estado":
            ESTADO_DESENVOLVEDORA
    })


# ============================================================
# PAINEL WEB DA IA DESENVOLVEDORA
# ============================================================

@app.route(
    "/desenvolvedora",
    methods=["GET"]
)
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
    border-radius: 15px;
    box-shadow:
        0 3px 15px rgba(0,0,0,0.12);
}

h1 {
    margin-top: 0;
}

.caixa {
    border: 2px dashed #999;
    padding: 25px;
    border-radius: 12px;
    margin-top: 20px;
}

button {
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    margin-top: 15px;
}

#resultado {
    white-space: pre-wrap;
    background: #111;
    color: #eee;
    padding: 20px;
    border-radius: 10px;
    margin-top: 20px;
    overflow-x: auto;
}

.status {
    padding: 12px;
    background: #eee;
    border-radius: 8px;
    margin-top: 15px;
}

input {
    margin-top: 15px;
    width: 100%;
}

</style>

</head>

<body>

<div class="container">

<h1>🤖 IA Desenvolvedora do Meu Dia</h1>

<p>
Laboratório de análise do código.
</p>

<div class="status">
<strong>Status:</strong>
IA pronta para receber um arquivo.
</div>

<div class="caixa">

<h2>1. Enviar código</h2>

<p>
Selecione um arquivo do projeto Meu Dia.
</p>

<input
    type="file"
    id="arquivo"
>

<br>

<button
    onclick="analisar()">
    🔍 Analisar código
</button>

</div>

<div id="mensagem"></div>

<div id="resultado"></div>

</div>

<script>

async function analisar() {

    const arquivo =
        document.getElementById("arquivo").files[0];

    const mensagem =
        document.getElementById("mensagem");

    const resultado =
        document.getElementById("resultado");

    if (!arquivo) {

        mensagem.innerText =
            "Selecione um arquivo primeiro.";

        return;
    }

    mensagem.innerText =
        "⏳ A IA está analisando o arquivo...";

    resultado.innerText = "";

    const formulario =
        new FormData();

    formulario.append(
        "arquivo",
        arquivo
    );

    try {

        const resposta =
            await fetch(
                "/desenvolvedora/analisar-arquivo",
                {
                    method: "POST",
                    body: formulario
                }
            );

        const dados =
            await resposta.json();

        if (!resposta.ok) {

            mensagem.innerText =
                "❌ Erro na análise.";

            resultado.innerText =
                dados.erro || "Erro desconhecido.";

            return;
        }

        mensagem.innerText =
            "✅ Análise concluída.";

        resultado.innerText =
            dados.analise;

    } catch (erro) {

        mensagem.innerText =
            "❌ Erro de conexão.";

        resultado.innerText =
            erro.toString();
    }
}

</script>

</body>

</html>
"""

    return render_template_string(
        html
    )


# ============================================================
# ANALISAR ARQUIVO ENVIADO PELO PAINEL
# ============================================================

@app.route(
    "/desenvolvedora/analisar-arquivo",
    methods=["POST"]
)
def desenvolvedora_analisar_arquivo():

    if not GEMINI_API_KEY:

        return jsonify({
            "erro":
                "GEMINI_API_KEY nao configurada."
        }), 500

    try:

        if "arquivo" not in request.files:

            return jsonify({
                "erro":
                    "Nenhum arquivo foi enviado."
            }), 400

        arquivo = request.files[
            "arquivo"
        ]

        if not arquivo.filename:

            return jsonify({
                "erro":
                    "O arquivo nao possui nome."
            }), 400

        conteudo_bytes = (
            arquivo.read(
                TAMANHO_MAXIMO_ARQUIVO + 1
            )
        )

        if len(conteudo_bytes) > TAMANHO_MAXIMO_ARQUIVO:

            return jsonify({
                "erro":
                    "Arquivo muito grande. "
                    "O limite nesta etapa e 5 MB."
            }), 413

        try:

            codigo = (
                conteudo_bytes
                .decode(
                    "utf-8",
                    errors="replace"
                )
            )

        except Exception:

            return jsonify({
                "erro":
                    "Nao foi possivel ler o arquivo."
            }), 400

        if not codigo.strip():

            return jsonify({
                "erro":
                    "O arquivo esta vazio."
            }), 400

        nome_arquivo = arquivo.filename

        job_id = str(
            uuid.uuid4()
        )

        ESTADO_DESENVOLVEDORA[
            "job_id"
        ] = job_id

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "analisando"
        
        ESTADO_DESENVOLVEDORA[
            "ultima_acao"
        ] = "analisar_arquivo"

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        ESTADO_DESENVOLVEDORA[
            "arquivo"
        ] = nome_arquivo

        ESTADO_DESENVOLVEDORA[
            "autorizacao"
        ] = False

        prompt = f"""
Voce e a IA Desenvolvedora do aplicativo
Meu Dia.

Voce recebeu um arquivo real do projeto.

Sua tarefa nesta etapa e SOMENTE ANALISAR.

NAO altere o arquivo.

NAO invente partes que nao estejam presentes.

NAO diga que executou o aplicativo.

NAO diga que compilou o projeto.

Voce ainda nao possui acesso ao projeto
Android Studio completo.

Analise somente o codigo fornecido.

Arquivo:
{nome_arquivo}

Faça uma analise tecnica procurando:

1. erros de codigo
2. possiveis crashes
3. problemas de desempenho
4. problemas de rede
5. problemas de seguranca
6. problemas de memoria
7. problemas de arquitetura
8. oportunidades de melhoria
9. melhorias para a IA do Meu Dia
10. melhorias para velocidade das respostas
11. problemas relacionados a compatibilidade
12. funcionalidades que podem ser melhoradas

IMPORTANTE:

Diferencie:

CONFIRMADO
PROVAVEL
PRECISA SER TESTADO

Nao invente resultados de testes.

Responda em portugues do Brasil.

Arquivo:
========================

{codigo}

========================
"""

        resultado = (
            chamar_gemini_desenvolvedora(
                prompt
            )
        )

        if not resultado:

            ESTADO_DESENVOLVEDORA[
                "status"
            ] = "erro"

            ESTADO_DESENVOLVEDORA[
                "mensagem"
            ] = (
                "Nao foi possivel analisar "
                "o arquivo."
            )

            return jsonify({
                "erro":
                    "A IA nao conseguiu analisar "
                    "o arquivo."
            }), 503

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "analise_concluida"

        ESTADO_DESENVOLVEDORA[
            "mensagem"
        ] = (
            "Analise concluida. "
            "Nenhuma alteracao foi aplicada."
        )

        ESTADO_DESENVOLVEDORA[
            "resultado"
        ] = resultado

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        return jsonify({
            "status":
                "analise_concluida",
            "job_id":
                job_id,
            "arquivo":
                nome_arquivo,
            "analise":
                resultado,
            "alterado":
                False
        })

    except Exception as erro:

        print(
            "ERRO ANALISANDO ARQUIVO:",
            str(erro)
        )

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "erro"

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# ANALISE VIA JSON
# ============================================================

@app.route(
    "/desenvolvedora/analisar",
    methods=["POST"]
)
def desenvolvedora_analisar():

    if not GEMINI_API_KEY:

        return jsonify({
            "erro":
                "GEMINI_API_KEY nao configurada."
        }), 500

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        codigo = str(
            dados.get(
                "codigo",
                ""
            )
        )

        nome_arquivo = str(
            dados.get(
                "arquivo",
                "arquivo_desconhecido"
            )
        )

        if not codigo.strip():

            return jsonify({
                "erro":
                    "Nenhum codigo foi enviado."
            }), 400

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "analisando"

        ESTADO_DESENVOLVEDORA[
            "ultima_acao"
        ] = "analisar"

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        prompt = f"""
Voce e a IA Desenvolvedora do aplicativo
Meu Dia.

Analise somente o codigo fornecido.

Nao altere nada.

Arquivo:
{nome_arquivo}

Codigo:
========================
{codigo}
========================

Analise:

ERROS
RISCOS
DESEMPENHO
SEGURANCA
ARQUITETURA
MELHORIAS
PLANO

Marque cada ponto como:

CONFIRMADO
PROVAVEL
PRECISA SER TESTADO

Nao invente resultados de testes.

Responda em portugues do Brasil.
"""

        resultado = (
            chamar_gemini_desenvolvedora(
                prompt
            )
        )

        if not resultado:

            ESTADO_DESENVOLVEDORA[
                "status"
            ] = "erro"

            return jsonify({
                "erro":
                    "Nao foi possivel analisar o codigo."
            }), 503

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "analise_concluida"

        ESTADO_DESENVOLVEDORA[
            "mensagem"
        ] = "Analise concluida."

        ESTADO_DESENVOLVEDORA[
            "resultado"
        ] = resultado

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        return jsonify({
            "status":
                "analise_concluida",
            "arquivo":
                nome_arquivo,
            "analise":
                resultado
        })

    except Exception as erro:

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "erro"

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# GERAR ALTERACAO
# ============================================================

@app.route(
    "/desenvolvedora/gerar",
    methods=["POST"]
)
def desenvolvedora_gerar():

    if not GEMINI_API_KEY:

        return jsonify({
            "erro":
                "GEMINI_API_KEY nao configurada."
        }), 500

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        pedido = str(
            dados.get(
                "pedido",
                ""
            )
        ).strip()

        codigo_atual = str(
            dados.get(
                "codigo_atual",
                ""
            )
        )

        nome_arquivo = str(
            dados.get(
                "arquivo",
                "arquivo.kt"
            )
        )

        if not pedido:

            return jsonify({
                "erro":
                    "Nenhum pedido de alteracao foi enviado."
            }), 400

        if not codigo_atual.strip():

            return jsonify({
                "erro":
                    "O codigo atual nao foi enviado."
            }), 400

        job_id = str(
            uuid.uuid4()
        )

        ESTADO_DESENVOLVEDORA[
            "job_id"
        ] = job_id

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "gerando"

        ESTADO_DESENVOLVEDORA[
            "ultima_acao"
        ] = "gerar"

        ESTADO_DESENVOLVEDORA[
            "autorizacao"
        ] = False

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        prompt = f"""
Voce e a IA Desenvolvedora do aplicativo
Meu Dia.

Pedido:
{pedido}

Arquivo:
{nome_arquivo}

Analise o codigo atual antes de gerar.

Nao destrua funcionalidades existentes.

Nao remova recursos sem necessidade.

Crie uma nova versao COMPLETA do arquivo.

A resposta deve conter:

RESUMO DA ALTERACAO

RISCOS

CODIGO_COMPLETO

Em CODIGO_COMPLETO coloque somente
o arquivo completo pronto para substituicao.

Ainda NAO aplique nenhuma alteracao.

Codigo atual:
========================

{codigo_atual}

========================
"""

        resultado = (
            chamar_gemini_desenvolvedora(
                prompt
            )
        )

        if not resultado:

            ESTADO_DESENVOLVEDORA[
                "status"
            ] = "erro"

            return jsonify({
                "erro":
                    "A IA nao conseguiu gerar a alteracao."
            }), 503

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "aguardando_autorizacao"

        ESTADO_DESENVOLVEDORA[
            "autorizacao"
        ] = False

        ESTADO_DESENVOLVEDORA[
            "resultado"
        ] = resultado

        ESTADO_DESENVOLVEDORA[
            "mensagem"
        ] = (
            "Alteracao preparada. "
            "Aguardando autorizacao."
        )

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        return jsonify({
            "status":
                "aguardando_autorizacao",
            "job_id":
                job_id,
            "arquivo":
                nome_arquivo,
            "resultado":
                resultado,
            "mensagem":
                "Alteracao preparada, "
                "mas ainda nao aplicada."
        })

    except Exception as erro:

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "erro"

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# AUTORIZAR
# ============================================================

@app.route(
    "/desenvolvedora/autorizar",
    methods=["POST"]
)
def desenvolvedora_autorizar():

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        job_id = str(
            dados.get(
                "job_id",
                ""
            )
        ).strip()

        if not job_id:

            return jsonify({
                "erro":
                    "job_id nao informado."
            }), 400

        if job_id != ESTADO_DESENVOLVEDORA[
            "job_id"
        ]:

            return jsonify({
                "erro":
                    "job_id invalido."
            }), 400

        if ESTADO_DESENVOLVEDORA[
            "status"
        ] != "aguardando_autorizacao":

            return jsonify({
                "erro":
                    "Nao existe alteracao "
                    "aguardando autorizacao."
            }), 409

        ESTADO_DESENVOLVEDORA[
            "autorizacao"
        ] = True

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "autorizado"

        ESTADO_DESENVOLVEDORA[
            "mensagem"
        ] = (
            "Alteracao autorizada pelo usuario."
        )

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        return jsonify({
            "status":
                "autorizado",
            "job_id":
                job_id,
            "mensagem":
                ESTADO_DESENVOLVEDORA[
                    "mensagem"
                ]
        })

    except Exception as erro:

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# REJEITAR
# ============================================================

@app.route(
    "/desenvolvedora/rejeitar",
    methods=["POST"]
)
def desenvolvedora_rejeitar():

    try:

        dados = request.get_json(
            silent=True
        ) or {}

        job_id = str(
            dados.get(
                "job_id",
                ""
            )
        ).strip()

        if job_id != ESTADO_DESENVOLVEDORA[
            "job_id"
        ]:

            return jsonify({
                "erro":
                    "job_id invalido."
            }), 400

        ESTADO_DESENVOLVEDORA[
            "autorizacao"
        ] = False

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "rejeitado"

        ESTADO_DESENVOLVEDORA[
            "mensagem"
        ] = (
            "Alteracao rejeitada pelo usuario."
        )

        ESTADO_DESENVOLVEDORA[
            "ultima_atualizacao"
        ] = agora()

        return jsonify({
            "status":
                "rejeitado",
            "job_id":
                job_id,
            "mensagem":
                "Alteracao descartada."
        })

    except Exception as erro:

        return jsonify({
            "erro":
                str(erro)
        }), 500


# ============================================================
# INICIALIZACAO
# ============================================================

if __name__ == "__main__":

    porta = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print("")
    print("========================================")
    print("SERVIDOR MEU DIA")
    print("========================================")
    print("PORTA:", porta)
    print(
        "GEMINI CONFIGURADO:",
        bool(GEMINI_API_KEY)
    )
    print(
        "MODELO RAPIDO:",
        MODELO_RAPIDO
    )
    print(
        "IA DESENVOLVEDORA:",
        "ATIVA"
    )
    print(
        "PAINEL:",
        "/desenvolvedora"
    )
    print("========================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=porta
    )
