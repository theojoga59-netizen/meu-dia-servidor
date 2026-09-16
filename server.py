from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def inicio():
    return jsonify({
        "status": "online",
        "servidor": "Meu Dia",
        "mensagem": "Servidor funcionando corretamente!"
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "online": True
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
