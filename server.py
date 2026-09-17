import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

class IaViewModel : ViewModel() {

    var respostaAtual by mutableStateOf("Olá! Como posso ajudar o seu dia hoje?")
        private set

    var isLoading by mutableStateOf(false)
        private set

    // Estado para controlar o Dialog de Confirmação da IA
    var comandoPendente by mutableStateOf<RespostaServidor?>(null)
        private set

    fun perguntarAoServidor(pergunta: String, contextoLocal: String) {
        viewModelScope.launch {
            isLoading = true
            try {
                val respostaJson = withContext(Dispatchers.IO) {
                    enviarPostParaRender(pergunta, contextoLocal)
                }

                if (respostaJson != null) {
                    val gson = Gson()
                    val resultado = gson.fromJson(respostaJson, RespostaServidor::class.java)

                    if (resultado.tipo == "COMANDO") {
                        // A IA quer fazer uma modificação estrutural. Pede sua autorização!
                        comandoPendente = resultado
                    } else {
                        // Apenas texto normal
                        respostaAtual = resultado.resposta ?: "Sem resposta da IA."
                    }
                } else {
                    respostaAtual = "Erro ao conectar com o servidor no Render."
                }
            } catch (e: Exception) {
                respostaAtual = "Erro: ${e.localizedMessage}"
            } finally {
                isLoading = false
            }
        }
    }

    fun confirmarComandoDaIA() {
        val comando = comandoPendente ?: return
        
        // Executa a ação de forma segura sem mexer no que já está salvo no Room
        when (comando.acao) {
            "CRIAR_ELEMENTO" -> {
                // Insira aqui a lógica local de salvamento (ex: chamar seu DAO do Room)
            }
        }
        
        respostaAtual = "Ação '${comando.titulo}' aplicada com sucesso!"
        comandoPendente = null // Fecha o diálogo
    }

    fun rejeitarComandoDaIA() {
        comandoPendente = null
        respostaAtual = "Operação cancelada por você."
    }

    private fun enviarPostParaRender(pergunta: String, contexto: String): String? {
        val url = URL("https://NOME-DO-SEU-APP.onrender.com/perguntar") // Substitua pela sua URL real do Render
        val conexao = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Content-Type", "application/json; charset=utf-8")
            doOutput = true
            connectTimeout = 30000
            readTimeout = 30000
        }

        val jsonBody = """{"pergunta": "$pergunta", "contexto": "$contexto"}"""
        conexao.outputStream.write(jsonBody.toByteArray(Charsets.UTF_8))

        return if (conexao.responseCode == HttpURLConnection.HTTP_OK) {
            conexao.inputStream.bufferedReader().use { it.readText() }
        } else {
            null
        }
    }
}
