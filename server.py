from flask import Flask, jsonify, request
import os
import urllib.request
import urllib.error
import json
import time
import random

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Modelos atualizados e estáveis da API do Gemini
MODELOS_GEMINI = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash"
]

TENTATIVAS_POR_MODELO = 2
ERROS_TEMPORARIOS = [408, 429, 500, 502, 503, 504]


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
        "gemini_configurado": bool(GEMINI_API_KEY),
        "modelos": MODELOS_GEMINI
    })


def montar_url(modelo):
    return (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        + modelo
        + ":generateContent?key="
        + GEMINI_API_KEY
    )


def enviar_para_gemini(modelo, dados_envio):
    url = montar_url(modelo)
    ultimo_erro = None

    for tentativa in range(1, TENTATIVAS_POR_MODELO + 1):
        print("========================================")
        print("MODELO:", modelo)
        print("TENTATIVA:", tentativa, "DE", TENTATIVAS_POR_MODELO)
        print("========================================")

        requisicao = urllib.request.Request(
            url,
            data=dados_envio,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(requisicao, timeout=60) as resposta_http:
                resposta_texto = resposta_http.read().decode("utf-8", errors="replace")
                print("SUCESSO COM O MODELO:", modelo)
                return resposta_texto

        except urllib.error.HTTPError as erro:
            ultimo_erro = erro
            corpo_erro = erro.read().decode("utf-8", errors="replace")
            print("========================================")
            print("ERRO DO GOOGLE - CODIGO:", erro.code)
            print("RESPOSTA:", corpo_erro)
            print("========================================")

            if erro.code not in ERROS_TEMPORARIOS:
                raise erro

            if tentativa < TENTATIVAS_POR_MODELO:
                espera = (2 ** (tentativa - 1)) + random.uniform(0.5, 1.5)
                time.sleep(espera)
                continue
            return None

        except urllib.error.URLError as erro:
            ultimo_erro = erro
            if tentativa < TENTATIVAS_POR_MODELO:
                espera = (2 ** (tentativa - 1)) + random.uniform(0.5, 1.5)
                time.sleep(espera)
                continue
            return None

        except Exception as erro:
            ultimo_erro = erro
            return None

    return None


def extrair_resposta(resposta_texto):
    resposta_json = json.loads(resposta_texto)
    candidatos = resposta_json.get("candidates", [])
    if not candidatos:
        return ""
    conteudo = candidatos[0].get("content", {})
    partes = conteudo.get("parts", [])
    if not partes:
        return ""
    
    textos = [parte.get("text", "") for parte in partes if parte.get("text", "")]
    return "\n".join(textos).strip()


@app.route("/perguntar", methods=["POST"])
def perguntar():
    print("\n========================================")
    print("PEDIDO RECEBIDO EM /perguntar")
    print("========================================")

    if not GEMINI_API_KEY:
        return jsonify({"erro": "A chave GEMINI_API_KEY não está configurada no servidor."}), 500

    try:
        dados = request.get_json(silent=True) or {}
        pergunta = str(dados.get("pergunta", "")).strip()
        contexto = str(dados.get("contexto", "")).strip()

        if not pergunta:
            return jsonify({"erro": "Nenhuma pergunta foi enviada."}), 400

        # Prompt inteligente que permite resposta em texto OU comandos JSON estruturados
        prompt = f"""
Você é a inteligência artificial autônoma do aplicativo Meu Dia.
Responda em português do Brasil. Seja clara, amigável e objetiva.

Se o usuário pedir para criar uma nova função, alterar layout, atualizar dados estruturados ou adicionar uma nova ferramenta no app, você DEVE retornar APENAS um JSON válido estruturado neste formato exato (sem blocos de código markdown complexos):
{{
  "tipo": "COMANDO",
  "acao": "CRIAR_ELEMENTO",
  "titulo": "Nome da Ação",
  "mensagem": "Explicação do que será alterado no app",
  "payload": {{}}
}}

Se for apenas uma conversa comum ou dúvida, responda normalmente em texto puro, mas estruturado assim:
{{
  "tipo": "TEXTO",
  "resposta": "Sua resposta aqui"
}}

Pergunta do usuário:
{pergunta}

Informações atuais do Meu Dia:
{contexto}
"""

        corpo = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        dados_envio = json.dumps(corpo).encode("utf-8")
        resposta_texto = None
        modelo_usado = None

        for modelo in MODELOS_GEMINI:
            print(f"\nTENTANDO MODELO: {modelo}")
            resposta_texto = enviar_para_gemini(modelo, dados_envio)

            if resposta_texto:
                try:
                    texto_bruto = extrair_resposta(resposta_texto)
                    if texto_bruto:
                        modelo_usado = modelo
                        
                        # Tenta interpretar se a IA retornou um JSON de comando ou texto
                        limpo = texto_bruto.replace("```json", "").replace("```", "").strip()
                        try:
                            json_obj = json.loads(limpo)
                            return jsonify(json_obj)
                        except:
                            # Se não for JSON válido, encapsula como texto padrão
                            return jsonify({
                                "tipo": "TEXTO",
                                "resposta": limpo.replace("**", "")
                            })
                except Exception as erro:
                    print("Erro ao interpretar resposta:", str(erro))

        return jsonify({
            "erro": "O serviço de inteligência artificial está temporariamente indisponível. Tente novamente."
        }), 503

    except Exception as erro:
        print("ERRO INTERNO:", str(erro))
        return jsonify({"erro": str(erro)}), 500


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta)
