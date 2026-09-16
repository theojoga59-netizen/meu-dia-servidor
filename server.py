import os
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def inicio():
    chave_configurada = bool(os.environ.get("GEMINI_API_KEY"))

    return jsonify({
        "status": "online",
        "servidor": "Meu Dia",
        "gemini_configurado": chave_configurada,
        "mensagem": "Servidor funcionando corretamente!"
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "online": True,
        "gemini_configurado": bool(os.environ.get("GEMINI_API_KEY"))
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
