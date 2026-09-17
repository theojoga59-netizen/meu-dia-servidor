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
# CONFIGURAÇÃO DO GEMINI
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

MODELO_RAPIDO = "gemini-3.8-flash"

MODELOS_RESERVA = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
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


def texto_seguro(valor, limite=200000):
    if valor is None:
        return ""

    texto = str(valor)

    if len(texto) > limite:
        texto = texto[:limite]

    return texto


def nome_arquivo_seguro(nome):
    if not nome:
        return "arquivo.txt"

    nome = os.path.basename(str(nome))

    caracteres_permitidos = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "._-"
    )

    resultado = ""

    for caractere in nome:
        if caractere in caracteres_permitidos:
            resultado += caractere

    if not resultado:
        return "arquivo.txt"

    return resultado


# ============================================================
# GEMINI
# ============================================================

def chamar_gemini(prompt, modelo=None, timeout=TIMEOUT_NORMAL):

    if not GEMINI_API_KEY:
        return {
            "ok": False,
            "erro": "GEMINI_API_KEY não configurada no servidor."
        }

    if modelo is None:
        modelo = MODELO_RAPIDO

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
                "content",
                {}
            ).get(
                "parts",
                []
            )

            textos = []

            for parte in partes:

                if "text" in parte:

                    textos.append(
                        str(parte["text"])
                    )

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

    except urllib.error.HTTPError as erro_http:

        try:
            detalhe = erro_http.read().decode("utf-8")
        except Exception:
            detalhe = str(erro_http)

        return {
            "ok": False,
            "erro": (
                "Erro HTTP "
                + str(erro_http.code)
                + ": "
                + detalhe
            )
        }

    except urllib.error.URLError as erro_url:

        return {
            "ok": False,
            "erro": (
                "Erro de conexão com Gemini: "
                + str(erro_url)
            )
        }

    except Exception as erro:

        return {
            "ok": False,
            "erro": str(erro)
        }


def chamar_gemini_com_fallback(
    prompt,
    timeout=TIMEOUT_NORMAL,
    desenvolvedora=False
):

    modelos = [
        MODELO_RAPIDO
    ] + MODELOS_RESERVA

    ultimo_erro = "Nenhum modelo respondeu."

    for modelo in modelos:

        for tentativa in range(
            TENTATIVAS_POR_MODELO
        ):

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
# IA NORMAL DO MEU DIA
# ============================================================

def criar_prompt_normal(
    pergunta,
    contexto
):

    return (
        "Você é a IA do aplicativo Meu Dia.\n"
        "Responda ao usuário em português do Brasil.\n"
        "Seja útil, clara e direta.\n\n"
        "Contexto do aplicativo:\n"
        + texto_seguro(contexto, 50000)
        + "\n\n"
        "Pergunta do usuário:\n"
        + texto_seguro(pergunta, 10000)
        + "\n\n"
        "Responda somente o necessário para ajudar o usuário."
    )


# ============================================================
# PROMPT DA IA DESENVOLVEDORA
# ============================================================

def criar_prompt_analise(
    arquivo,
    codigo
):

    return (
        "Você é a IA Desenvolvedora do aplicativo Meu Dia.\n\n"

        "Sua função é analisar código de um projeto Android "
        "e identificar problemas de compilação, execução, "
        "estrutura, lógica e integração.\n\n"

        "Você deve ser extremamente cuidadosa.\n"

        "Analise o arquivo abaixo.\n\n"

        "NOME DO ARQUIVO:\n"
        + nome_arquivo_seguro(arquivo)
        + "\n\n"

        "CÓDIGO:\n"
        + texto_seguro(codigo, 180000)
        + "\n\n"

        "Retorne uma análise contendo:\n"
        "1. Problemas encontrados.\n"
        "2. Causa provável de cada problema.\n"
        "3. O que precisa ser corrigido.\n"
        "4. Possíveis consequências.\n"
        "5. Se o arquivo parece estar correto, diga isso claramente.\n\n"

        "Não invente erros que não estejam relacionados ao código."
    )


def criar_prompt_codigo(
    arquivo,
    codigo,
    instrucoes
):

    return (
        "Você é a IA Desenvolvedora do aplicativo Meu Dia.\n\n"

        "Sua tarefa é corrigir ou melhorar um arquivo de código "
        "Android de forma completa.\n\n"

        "REGRA MUITO IMPORTANTE:\n"
        "Retorne o ARQUIVO COMPLETO corrigido.\n"
        "Nunca retorne somente um trecho.\n"
        "O usuário substituirá o arquivo inteiro pelo resultado.\n\n"

        "ARQUIVO:\n"
        + nome_arquivo_seguro(arquivo)
        + "\n\n"

        "CÓDIGO ATUAL:\n"
        + texto_seguro(codigo, 180000)
        + "\n\n"

        "INSTRUÇÕES DO USUÁRIO:\n"
        + texto_seguro(instrucoes, 30000)
        + "\n\n"

        "Regras:\n"
        "- Preserve o que já funciona.\n"
        "- Corrija erros de sintaxe.\n"
        "- Corrija imports quando necessário.\n"
        "- Evite criar dependências desnecessárias.\n"
        "- Não apague funcionalidades existentes sem motivo.\n"
        "- Entregue código completo.\n"
        "- Não coloque explicações dentro do código.\n\n"

        "A resposta deve começar diretamente com o código "
        "ou com um único bloco de código."
    )


# ============================================================
# EXTRAÇÃO DO CÓDIGO
# ============================================================

def extrair_codigo_gerado(texto):

    texto = texto.strip()

    if "```" not in texto:
        return texto

    partes = texto.split("```")

    candidatos = []

    for i in range(
        1,
        len(partes),
        2
    ):

        bloco = partes[i].strip()

        linhas = bloco.splitlines()

        if linhas:

            primeira = linhas[0].strip().lower()

            linguagens = [
                "kotlin",
                "java",
                "xml",
                "gradle",
                "python",
                "json",
                "javascript",
                "js",
                "html",
                "css",
                "text",
                "txt"
            ]

            if primeira in linguagens:

                bloco = "\n".join(
                    linhas[1:]
                )

        candidatos.append(
            bloco.strip()
        )

    if not candidatos:
        return texto

    candidatos.sort(
        key=len,
        reverse=True
    )

    return candidatos[0]


def extrair_explicacao(texto):

    texto = texto.strip()

    if "```" not in texto:
        return ""

    antes = texto.split(
        "```",
        1
    )[0].strip()

    return antes


# ============================

