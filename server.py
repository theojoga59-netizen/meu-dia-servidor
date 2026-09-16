import os
from flask import Flask, jsonify

app = Flask(**name**)

@app.route("/")
def inicio():
return jsonify({
"status": "online",
"servidor": "Meu Dia",
"mensagem": "Servidor funcionando corretamente!"
})

if **name** == "**main**":
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
