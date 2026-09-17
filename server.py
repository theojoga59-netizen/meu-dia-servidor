```kotlin
package com.meudia.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class IaViewModel : ViewModel() {

    companion object {
        private const val URL_SERVIDOR =
            "https://meu-dia-servidor.onrender.com/perguntar"

        private const val TIMEOUT_CONEXAO = 30000
        private const val TIMEOUT_LEITURA = 60000
    }

    var respostaAtual by mutableStateOf(
        "Olá! Como posso ajudar o seu dia hoje?"
    )
        private set

    var isLoading by mutableStateOf(false)
        private set

    var comandoPendente by mutableStateOf<RespostaServidor?>(null)
        private set

    fun perguntarAoServidor(
        pergunta: String,
        contextoLocal: String
    ) {
        if (pergunta.isBlank()) {
            respostaAtual = "Digite ou fale alguma coisa."
            return
        }

        viewModelScope.launch {

            isLoading = true

            try {

                val respostaJson = withContext(Dispatchers.IO) {
                    enviarPostParaRender(
                        pergunta = pergunta.trim(),
                        contexto = contextoLocal
                    )
                }

                if (respostaJson == null) {

                    respostaAtual =
                        "Não consegui receber uma resposta do servidor Meu Dia."

                } else {

                    processarRespostaServidor(respostaJson)
                }

            } catch (e: Exception) {

                respostaAtual =
                    "Erro ao comunicar com o servidor: ${e.localizedMessage ?: "erro desconhecido"}"

            } finally {

                isLoading = false
            }
        }
    }

    private fun processarRespostaServidor(
        respostaJson: String
    ) {

        try {

            val json = JSONObject(respostaJson)

            val erro = json.optString("erro", "")

            if (erro.isNotBlank()) {

                respostaAtual = "Servidor: $erro"

                return
            }

            val tipo = json.optString(
                "tipo",
                "RESPOSTA"
            )

            val resposta = json.optString(
                "resposta",
                ""
            )

            if (tipo == "COMANDO") {

                val comando = RespostaServidor(
                    tipo = "COMANDO",
                    resposta = resposta.ifBlank {
                        "A IA preparou uma alteração para o Meu Dia."
                    },
                    acao = json.optString(
                        "acao",
                        ""
                    ),
                    titulo = json.optString(
                        "titulo",
                        "Alteração do Meu Dia"
                    )
                )

                comandoPendente = comando

                respostaAtual =
                    "A IA preparou uma alteração. Autorize para continuar."

            } else {

                respostaAtual =
                    resposta.ifBlank {
                        "O servidor não retornou uma resposta."
                    }
            }

        } catch (e: Exception) {

            respostaAtual =
                "Recebi uma resposta do servidor, mas não consegui interpretá-la."
        }
    }

    fun confirmarComandoDaIA() {

        val comando = comandoPendente ?: return

        when (comando.acao) {

            "CRIAR_ELEMENTO" -> {

                /*
                 * AQUI NÃO ALTERAMOS O BANCO AUTOMATICAMENTE AINDA.
                 *
                 * Primeiro vamos conectar esta parte ao seu Room
                 * e ao modelo real do Meu Dia.
                 *
                 * Isso protege os dados que já funcionam no aplicativo.
                 */
            }

            else -> {

                /*
                 * Ação ainda não implementada.
                 *
                 * A IA não poderá executar uma ação desconhecida.
                 */
            }
        }

        respostaAtual =
            "A ação '${comando.titulo}' foi autorizada."

        comandoPendente = null
    }

    fun rejeitarComandoDaIA() {

        comandoPendente = null

        respostaAtual =
            "Operação cancelada por você."
    }

    private fun enviarPostParaRender(
        pergunta: String,
        contexto: String
    ): String? {

        var conexao: HttpURLConnection? = null

        return try {

            val url = URL(URL_SERVIDOR)

            conexao =
                (url.openConnection() as HttpURLConnection).apply {

                    requestMethod = "POST"

                    setRequestProperty(
                        "Content-Type",
                        "application/json; charset=utf-8"
                    )

                    setRequestProperty(
                        "Accept",
                        "application/json"
                    )

                    doOutput = true

                    connectTimeout =
                        TIMEOUT_CONEXAO

                    readTimeout =
                        TIMEOUT_LEITURA
                }

            val json = JSONObject().apply {

                put(
                    "pergunta",
                    pergunta
                )

                put(
                    "contexto",
                    contexto
                )
            }

            val corpo =
                json.toString().toByteArray(Charsets.UTF_8)

            conexao.outputStream.use { output ->

                output.write(corpo)
                output.flush()
            }

            val codigo =
                conexao.responseCode

            if (
                codigo == HttpURLConnection.HTTP_OK
            ) {

                conexao.inputStream
                    .bufferedReader()
                    .use { leitor ->
                        leitor.readText()
                    }

            } else {

                val erroTexto = try {

                    conexao.errorStream
                        ?.bufferedReader()
                        ?.use { leitor ->
                            leitor.readText()
                        }

                } catch (_: Exception) {

                    null
                }

                if (!erroTexto.isNullOrBlank()) {

                    erroTexto

                } else {

                    JSONObject()
                        .put(
                            "erro",
                            "Servidor retornou HTTP $codigo."
                        )
                        .toString()
                }
            }

        } catch (e: Exception) {

            JSONObject()
                .put(
                    "erro",
                    e.localizedMessage
                        ?: "Erro de conexão."
                )
                .toString()

        } finally {

            conexao?.disconnect()
        }
    }
}

data class RespostaServidor(
    val tipo: String = "RESPOSTA",
    val resposta: String = "",
    val acao: String = "",
    val titulo: String = ""
)
```
