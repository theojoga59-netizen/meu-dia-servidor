from flask import Flask, jsonify, request
import os
import urllib.request
import urllib.error
import json
import time
import random
import uuid
from datetime import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURACAO
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

SERVIDOR_NOME = "Meu Dia"

# Modelo principal atual.
# O Google documenta o Gemini 3.8 Flash como modelo estavel
# e voltado tambem para engenharia de software e agentes.
MODELO_RAPIDO = "gemini-3.8-flash"

MODELOS_FALLBACK = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite"
]

# Para o assistente normal queremos velocidade.
NIVEL_PENSAMENTO_NORMAL = "low"

# Para a IA desenvolvedora queremos mais raciocinio.
NIVEL_PENSAMENTO_DESENVOLVEDORA = "medium"

# Tempo menor para evitar que o aplicativo fique preso
# esperando por muito tempo.
TIMEOUT_NORMAL = 30

# Para tarefas de desenvolvimento podemos esperar mais.
TIMEOUT_DESENVOLVEDORA = 90

# Apenas uma nova tentativa por modelo.
# Isso evita aquela espera enorme do sistema anterior.
TENTATIVAS_POR_MODELO = 1

ERROS_TEMPORARIOS = [
    408,
    429,
    500,
    502,
    503,
    504
]

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
    "resultado": None
}


# ============================================================
# FUNCOES BASICAS
# ============================================================

def agora():
    return datetime.utcnow().isoformat() + "Z"


def montar_url(modelo):
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + modelo
        + ":generateContent?key="
        + GEMINI_API_KEY
    )


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


def extrair_resposta(resposta_texto):
    resposta_json = json.loads(resposta_texto)

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

    return "\n".join(textos).strip()


# ============================================================
# ENVIO PARA GEMINI
# ============================================================

def enviar_para_gemini(
    modelo,
    dados_envio,
    timeout
):
    url = montar_url(modelo)

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
                "Content-Type": "application/json"
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

            corpo_erro = erro.read().decode(
                "utf-8",
                errors="replace"
            )

            print("")
            print("ERRO GOOGLE")
            print("MODELO:", modelo)
            print("CODIGO:", erro.code)
            print("RESPOSTA:", corpo_erro)

            if erro.code not in ERROS_TEMPORARIOS:
                return None

            return None

        except urllib.error.URLError as erro:

            print("")
            print("ERRO DE CONEXAO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))

            return None

        except Exception as erro:

            print("")
            print("ERRO DESCONHECIDO")
            print("MODELO:", modelo)
            print("ERRO:", str(erro))

            return None

    return None


# ============================================================
# CHAMADA NORMAL
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

        resposta_texto = enviar_para_gemini(
            modelo,
            dados_envio,
            TIMEOUT_NORMAL
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
# CHAMADA DA IA DESENVOLVEDORA
# ============================================================

def chamar_gemini_desenvolvedora(prompt):

    corpo = montar_corpo_gemini(
        prompt,
        NIVEL_PENSAMENTO_DESENVOLVEDORA
    )

    dados_envio = json.dumps(
        corpo
    ).encode("utf-8")

    # Primeiro tenta o modelo mais forte da arquitetura.
    modelos = [
        MODELO_RAPIDO,
        "gemini-3.7-flash",
        "gemini-3.6-flash"
    ]

    for modelo in modelos:

        resposta_texto = enviar_para_gemini(
            modelo,
            dados_envio,
            TIMEOUT_DESENVOLVEDORA
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
                "Erro interpretando IA desenvolvedora:",
                str(erro)
            )

    return None


# ============================================================
# ROTA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "status": "online",
        "mensagem": "Servidor funcionando corretamente!",
        "gemini_configurado": bool(
            GEMINI_API_KEY
        ),
        "ia_desenvolvedora": "ativa"
    })


# ============================================================
# STATUS
# ============================================================

@app.route("/status")
def status():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "status": "online",
        "gemini_configurado": bool(
            GEMINI_API_KEY
        ),
        "modelo_rapido": MODELO_RAPIDO,
        "modelos_fallback": MODELOS_FALLBACK,
        "ia_desenvolvedora": ESTADO_DESENVOLVEDORA
    })


# ============================================================
# ASSISTENTE NORMAL DO MEU DIA
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
                "resposta": resposta,
                "modelo": MODELO_RAPIDO
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
            "erro": str(erro)
        }), 500


# ============================================================
# IA DESENVOLVEDORA - STATUS
# ============================================================

@app.route(
    "/desenvolvedora/status",
    methods=["GET"]
)
def desenvolvedora_status():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "ia_desenvolvedora": True,
        "estado": ESTADO_DESENVOLVEDORA
    })


# ============================================================
# IA DESENVOLVEDORA - ANALISAR
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

Sua funcao e analisar codigo de software
com muita cautela.

Nao altere nada.

Nao invente arquivos.

Nao invente funcoes que nao aparecem
no codigo fornecido.

Analise:

1. erros provaveis
2. riscos
3. problemas de arquitetura
4. oportunidades de melhoria
5. problemas de desempenho
6. problemas de seguranca
7. melhorias para o aplicativo Meu Dia

Arquivo analisado:
{nome_arquivo}

CODIGO:
--------------------
{codigo}
--------------------

Responda em portugues do Brasil.

Organize a resposta em:

ERROS
RISCOS
MELHORIAS
PLANO

Se nao tiver certeza de alguma coisa,
marque como "precisa ser verificado".
"""

        resultado = chamar_gemini_desenvolvedora(
            prompt
        )

        if not resultado:

            ESTADO_DESENVOLVEDORA[
                "status"
            ] = "erro"

            ESTADO_DESENVOLVEDORA[
                "mensagem"
            ] = "Nao foi possivel analisar o codigo."

            return jsonify({
                "erro":
                    "A IA desenvolvedora nao conseguiu analisar o codigo."
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
            "status": "analise_concluida",
            "arquivo": nome_arquivo,
            "analise": resultado
        })

    except Exception as erro:

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "erro"

        return jsonify({
            "erro": str(erro)
        }), 500


# ============================================================
# IA DESENVOLVEDORA - GERAR ALTERACAO
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

Tarefa:
{pedido}

Arquivo:
{nome_arquivo}

IMPORTANTE:

Nao destrua funcionalidades existentes.

Preserve o comportamento que ja funciona.

Nao remova recursos sem necessidade.

Analise o codigo antes de propor a mudanca.

Crie uma nova versao completa do arquivo.

A resposta deve conter:

1. RESUMO DA ALTERACAO
2. RISCOS
3. CODIGO_COMPLETO

O codigo em CODIGO_COMPLETO deve ser
o arquivo inteiro, pronto para substituir
o arquivo atual.

Nao coloque comentarios fora da estrutura
solicitada.

CODIGO ATUAL:
========================
{codigo_atual}
========================
"""

        resultado = chamar_gemini_desenvolvedora(
            prompt
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
            "Aguardando autorizacao do usuario."
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
                "A alteracao foi preparada, "
                "mas ainda nao foi aplicada."
        })

    except Exception as erro:

        ESTADO_DESENVOLVEDORA[
            "status"
        ] = "erro"

        return jsonify({
            "erro": str(erro)
        }), 500


# ============================================================
# AUTORIZAR ALTERACAO
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
                    "Nao existe alteracao aguardando autorizacao."
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
            "Alteracao autorizada pelo usuario. "
            "A aplicacao real sera feita quando "
            "o laboratorio do projeto estiver conectado."
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
            "erro": str(erro)
        }), 500


# ============================================================
# REJEITAR ALTERACAO
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
        ] = "Alteracao rejeitada pelo usuario."

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
            "erro": str(erro)
        }), 500


# ============================================================
# ROTA DE SAUDE
# ============================================================

@app.route(
    "/saude",
    methods=["GET"]
)
def saude():

    return jsonify({
        "servidor": SERVIDOR_NOME,
        "online": True,
        "gemini": bool(
            GEMINI_API_KEY
        ),
        "ia_desenvolvedora": True,
        "hora": agora()
    })


# ============================================================
# INICIO DO SERVIDOR
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
        "IA DESENVOLVEDORA: ATIVA"
    )
    print("========================================")
    print("")

    app.run(
        host="0.0.0.0",
        port=porta
    )
