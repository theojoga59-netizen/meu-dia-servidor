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

# Modelo principal
MODELO_RAPIDO = "gemini-3.8-flash"

# Modelos de reserva
MODELOS_RESERVA = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]

TIMEOUT_NORMAL = 30
TIMEOUT_DESENVOLVEDORA = 90
TENTATIVAS_POR_MODELO = 1

# Limite de arquivo enviado para análise.
# 500 KB é suficiente para arquivos Kotlin/XML comuns.
TAMANHO_MAXIMO_ARQUIVO = 500 * 1024

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
    """
    Converte qualquer valor para texto e aplica um limite.
    """
    if valor is None:
        return ""

    texto = str(valor)

    if len(texto) > limite:
        texto = texto[:limite] + "\n\n[conteúdo cortado pelo servidor]"

    return texto


def nome_arquivo_seguro(nome):
    """
    Evita caminhos maliciosos vindos do nome do arquivo.
    """
    if not nome:
        return "arquivo"

    nome = os.path.basename(nome)

    caracteres_permitidos = (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        "._-"
    )

    nome_limpo = "".join(
        caractere
        for caractere in nome
        if caractere in caracteres_permitidos
    )

    return nome_limpo or "arquivo"


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
        "https://generativelanguage.googleapis.com/v1beta/models/"
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
        ],
        "generationConfig": {
            "thinkingConfig": {
                "thinkingLevel": "low"
            }
        }
    }

    corpo = json.dumps(
        dados,
        ensure_ascii=False
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

    try:

        with urllib.request.urlopen(
            requisicao,
            timeout=timeout
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
                    "erro": "Gemini não retornou candidatos."
                }

            textos = []

            for candidato in candidatos:

                conteudo = candidato.get(
                    "content",
                    {}
                )

                partes = conteudo.get(
                    "parts",
                    []
                )

                for parte in partes:

                    if "text" in parte:

                        textos.append(
                            str(parte["text"])
                        )

            resultado = "\n".join(textos).strip()

            if not resultado:

                # Alguns erros podem aparecer no próprio JSON.
                erro_api = dados_resposta.get(
                    "error",
                    {}
                )

                mensagem_api = erro_api.get(
                    "message"
                )

                if mensagem_api:

                    return {
                        "ok": False,
                        "erro": str(mensagem_api)
                    }

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

    except urllib.error.URLError as e:

        return {
            "ok": False,
            "erro": f"Erro de conexão com Gemini: {e.reason}"
        }

    except TimeoutError:

        return {
            "ok": False,
            "erro": "Tempo limite excedido ao falar com Gemini."
        }

    except json.JSONDecodeError:

        return {
            "ok": False,
            "erro": "Gemini retornou uma resposta inválida."
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

            # Pequena pausa antes do próximo modelo.
            if tentativa + 1 < TENTATIVAS_POR_MODELO:
                time.sleep(0.5)

        # Se um modelo falhou, tenta o próximo.

    return {
        "ok": False,
        "erro": ultimo_erro
    }


# ============================================================
# PROMPT NORMAL
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
# PROMPT DA IA DESENVOLVEDORA
# ============================================================

def criar_prompt_analise(nome_arquivo, codigo):

    return f"""
Você é a IA Desenvolvedora do aplicativo Meu Dia.

Sua função é analisar código de aplicativos Android e ajudar a
corrigir problemas com segurança.

Analise o arquivo abaixo.

ARQUIVO:
{nome_arquivo}

CÓDIGO:
---------------- INÍCIO DO CÓDIGO ----------------

{codigo}

----------------- FIM DO CÓDIGO -----------------

Faça uma análise técnica em português do Brasil.

Informe:

1. Se o código parece válido.
2. Possíveis erros de compilação.
3. Possíveis erros de execução.
4. Problemas de lógica.
5. Problemas de compatibilidade.
6. Melhorias recomendadas.
7. Se for necessário alterar o arquivo, explique exatamente o que
precisa ser corrigido.

Não invente erros que não estejam relacionados ao código fornecido.

Não altere o código nesta etapa.

A resposta deve ser clara e organizada.
"""


def criar_prompt_geracao(
    nome_arquivo,
    codigo_original,
    analise
):

    return f"""
Você é a IA Desenvolvedora do aplicativo Meu Dia.

Sua tarefa agora é corrigir o arquivo fornecido.

ARQUIVO:
{nome_arquivo}

CÓDIGO ORIGINAL:
---------------- INÍCIO ----------------

{codigo_original}

---------------- FIM ----------------

ANÁLISE:
---------------- INÍCIO ----------------

{analise}

---------------- FIM ----------------

REGRAS IMPORTANTES:

1. Gere o arquivo COMPLETO.
2. Não entregue apenas trechos.
3. Preserve as partes que já estão funcionando.
4. Corrija somente o que for necessário.
5. Não invente dependências sem necessidade.
6. Não remova funcionalidades existentes sem explicar.
7. Para Kotlin, entregue Kotlin completo.
8. Para XML, entregue XML completo.
9. Para Gradle, entregue o arquivo Gradle completo.
10. O resultado deve estar pronto para substituir o arquivo original.

A resposta DEVE seguir exatamente este formato:

EXPLICACAO:
Uma explicação curta das correções realizadas.

CODIGO:
```texto
COLOQUE AQUI O ARQUIVO COMPLETO CORRIGIDO
