@file:Suppress("SpellCheckingInspection")

package eu.kanade.tachiyomi.extension.pt.mangadash

import androidx.preference.EditTextPreference
import androidx.preference.PreferenceScreen
import eu.kanade.tachiyomi.network.GET
import eu.kanade.tachiyomi.network.POST
import eu.kanade.tachiyomi.source.ConfigurableSource
import eu.kanade.tachiyomi.source.model.FilterList
import eu.kanade.tachiyomi.source.model.MangasPage
import eu.kanade.tachiyomi.source.model.Page
import eu.kanade.tachiyomi.source.model.SChapter
import eu.kanade.tachiyomi.source.model.SManga
import eu.kanade.tachiyomi.source.online.HttpSource
import keiyoushi.annotation.Source
import keiyoushi.utils.asJsoup
import keiyoushi.utils.firstInstanceOrNull
import keiyoushi.utils.getPreferencesLazy
import keiyoushi.utils.parseAs
import keiyoushi.utils.tryParse
import okhttp3.FormBody
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import java.io.IOException
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.concurrent.TimeUnit

@Suppress("unused")
@Source
abstract class MangaDash :
    HttpSource(),
    ConfigurableSource {

    override val supportsLatest = true

    private val preferences by getPreferencesLazy()

    private val pdfCache = LinkedHashMap<String, List<PdfImageExtractor.Image>>(4, 0.75f, true)

    private val loginInterceptor = Interceptor { chain ->
        val request = chain.request()

        // Skip login requests to avoid infinite loops
        if (request.url.encodedPath.contains("auth/login")) {
            return@Interceptor chain.proceed(request)
        }

        val username = preferences.getString(PREF_USERNAME, "") ?: ""
        val password = preferences.getString(PREF_PASSWORD, "") ?: ""

        if (username.isNotBlank() && password.isNotBlank()) {
            val cookies = client.cookieJar.loadForRequest(baseUrl.toHttpUrl())
            val hasSession = cookies.any { it.name == "session" }

            if (!hasSession) {
                synchronized(this) {
                    val currentCookies = client.cookieJar.loadForRequest(baseUrl.toHttpUrl())
                    if (!currentCookies.any { it.name == "session" }) {
                        try {
                            performLogin(username, password)
                        } catch (_: Exception) {
                            // Ignore login errors to let the original request proceed and fail naturally
                        }
                    }
                }
            }
        }

        chain.proceed(request)
    }

    private val pdfInterceptor = Interceptor { chain ->
        val request = chain.request()
        val path = request.url.pathSegments
        if (path.size == 3 && path[0] == "__mangadash_pdf") {
            val index = path[2].toIntOrNull() ?: throw IOException("Página PDF inválida")
            val image = synchronized(pdfCache) { pdfCache[path[1]]?.getOrNull(index) }
                ?: throw IOException("Reabra o capítulo para recarregar as imagens do PDF")
            Response.Builder()
                .code(200)
                .protocol(Protocol.HTTP_1_1)
                .request(request)
                .message("OK")
                .body(image.data.toResponseBody(image.mimeType.toMediaType()))
                .build()
        } else {
            chain.proceed(request)
        }
    }

    override val client: OkHttpClient = network.client.newBuilder()
        .addInterceptor(loginInterceptor)
        .addInterceptor(pdfInterceptor)
        .build()

    override fun headersBuilder() = super.headersBuilder()
        .add("Accept", "application/json, text/plain, */*")
        .add("Referer", "$baseUrl/")

    // ============================== Settings ==============================
    override fun setupPreferenceScreen(screen: PreferenceScreen) {
        val usernamePref = EditTextPreference(screen.context).apply {
            key = PREF_USERNAME
            title = "Usuário / Email"
            summary = "Preencha para fazer login automaticamente"
            setDefaultValue("")
        }

        val passwordPref = EditTextPreference(screen.context).apply {
            key = PREF_PASSWORD
            title = "Senha"
            summary = "Preencha para fazer login automaticamente"
            setDefaultValue("")
        }

        val infoPref = EditTextPreference(screen.context).apply {
            key = "pref_info_18plus"
            title = "Atenção: Conteúdo +18"
            summary = "Para acessar o conteúdo +18, você precisa de uma conta e habilitar a opção no site.\n\n" +
                "Passo a passo:\n" +
                "1. Abra a extensão no WebView (ícone de bússola).\n" +
                "2. Faça login na sua conta.\n" +
                "3. Acesse seu Perfil -> Configurações -> Preferências.\n" +
                "4. Marque a opção 'Habilitar Conteúdo Adulto (+18)'.\n" +
                "5. Clique em 'Salvar Preferências'."
            setOnPreferenceClickListener { true }
        }

        screen.addPreference(usernamePref)
        screen.addPreference(passwordPref)
        screen.addPreference(infoPref)
    }

    private fun performLogin(username: String, password: String) {
        val loginUrl = "$baseUrl/auth/login"
        val baseClient = network.client

        // 1. Get CSRF Token. Using Use block for safety.
        val getRequest = GET(loginUrl, headers)
        val document = baseClient.newCall(getRequest).execute().asJsoup()
        val csrfToken = document.selectFirst("meta[name=csrf-token]")?.attr("content")
            ?: document.selectFirst("input[name=csrf_token]")?.attr("value")

        if (csrfToken.isNullOrEmpty()) {
            return
        }

        // 2. Perform Login POST
        val formBody = FormBody.Builder()
            .add("csrf_token", csrfToken)
            .add("login", username)
            .add("password", password)
            .build()

        val postRequest = POST(loginUrl, headers, formBody)
        baseClient.newCall(postRequest).execute().close()
    }

    // ============================== Popular ==============================
    override fun popularMangaRequest(page: Int): Request = GET("$baseUrl/api/mangas/list?page=$page&q=&sort=populares&categoria=&status=&ano=&plus18=", headers)

    override fun popularMangaParse(response: Response): MangasPage {
        val dto = response.parseAs<MangaListDto>()
        return MangasPage(dto.mangas, dto.hasNext)
    }

    // ============================== Latest ===============================
    override fun latestUpdatesRequest(page: Int): Request = GET("$baseUrl/api/mangas/list?page=$page&q=&sort=recentes&categoria=&status=&ano=&plus18=", headers)

    override fun latestUpdatesParse(response: Response): MangasPage = popularMangaParse(response)

    // ============================== Search ===============================
    override fun searchMangaRequest(page: Int, query: String, filters: FilterList): Request {
        val sort = filters.firstInstanceOrNull<SortFilter>()?.toUriPart() ?: "recentes"
        val category = filters.firstInstanceOrNull<CategoryFilter>()?.toUriPart() ?: ""
        val status = filters.firstInstanceOrNull<StatusFilter>()?.toUriPart() ?: ""
        val year = filters.firstInstanceOrNull<YearFilter>()?.toUriPart() ?: ""
        val plus18 = if (filters.firstInstanceOrNull<Plus18Filter>()?.state == true) "true" else ""

        val url = "$baseUrl/api/mangas/list".toHttpUrl().newBuilder().apply {
            addQueryParameter("page", page.toString())
            addQueryParameter("q", query)
            addQueryParameter("sort", sort)
            addQueryParameter("categoria", category)
            addQueryParameter("status", status)
            addQueryParameter("ano", year)
            addQueryParameter("plus18", plus18)
        }.build()

        return GET(url, headers)
    }

    override fun searchMangaParse(response: Response): MangasPage = popularMangaParse(response)

    // ============================== Details ==============================
    override fun mangaDetailsParse(response: Response): SManga {
        val document = response.asJsoup()
        return SManga.create().apply {
            title = document.selectFirst(".neon-title")?.text()!!
            author = document.selectFirst(".tag-author")?.text()
            genre = document.select(".manga-tags a.tag:not(.tag-author)").joinToString { it.text() }
            description = document.selectFirst(".manga-description")?.text()

            val statsText = document.select(".stats-row .stat-item").text()
            status = when {
                statsText.contains("Lançamento", ignoreCase = true) -> SManga.ONGOING
                statsText.contains("Concluído", ignoreCase = true) -> SManga.COMPLETED
                statsText.contains("Hiato", ignoreCase = true) -> SManga.ON_HIATUS
                else -> SManga.UNKNOWN
            }
        }
    }

    // ============================= Chapters ==============================
    override fun chapterListParse(response: Response): List<SChapter> {
        val document = response.asJsoup()
        val chapters = document.select(".chapters-scroll-container .chapter-row").map { element ->
            SChapter.create().apply {
                url = element.attr("href")
                name = element.selectFirst(".chapter-title-group h4")?.text()!!
                val dateStr = element.selectFirst(".chapter-meta-info:has(.fa-calendar)")?.text()
                date_upload = dateStr?.let { dateFormat.tryParse(it) } ?: 0L

                // Extract chapter number for proper sorting fixing the website's alphabetical issue
                chapter_number = name.substringAfter("Capítulo").trim().toFloatOrNull() ?: -1f
            }
        }

        return chapters.sortedWith(
            compareByDescending<SChapter> { it.chapter_number }
                .thenByDescending { it.name },
        )
    }

    // =============================== Pages ===============================
    override fun pageListParse(response: Response): List<Page> {
        val document = response.asJsoup()
        val dataElement = document.selectFirst("script#chapterViewerData")
            ?: throw Exception("Dados do capítulo não encontrados")

        val dto = dataElement.data().parseAs<ChapterDataDto>()

        val images = dto.resolvedImages
        if (!images.isNullOrEmpty()) {
            return images.mapIndexed { i, img -> Page(i, imageUrl = img) }
        }

        var pdfUrl = dto.resolvedPdfUrl
        if (!pdfUrl.isNullOrBlank()) {
            pdfUrl = pdfUrl.replace(" ", "%20")
            if (pdfUrl.startsWith("/")) {
                pdfUrl = baseUrl + pdfUrl
            }

            val pdfClient = client.newBuilder()
                .readTimeout(3, TimeUnit.MINUTES)
                .connectTimeout(1, TimeUnit.MINUTES)
                .build()
            val pdfHeaders = headersBuilder().add("Origin", baseUrl).build()
            val pdfRequest = GET(pdfUrl, pdfHeaders)
            val pages = pdfClient.newCall(pdfRequest).execute().use { pdfResponse ->
                if (!pdfResponse.isSuccessful) {
                    throw IOException("HTTP ${pdfResponse.code} ao acessar o PDF do capítulo")
                }
                try {
                    pdfResponse.body.byteStream().use { PdfImageExtractor.extract(it) }
                } catch (e: IOException) {
                    throw IOException("MangaDash 1.4.3: ${e.message}", e)
                }
            }
            val key = MessageDigest.getInstance("SHA-256")
                .digest((document.location() + pdfUrl).toByteArray())
                .joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }
            synchronized(pdfCache) {
                pdfCache[key] = pages
                var bytes = 0L
                pdfCache.values.forEach { list -> list.forEach { bytes += it.data.size } }
                while (pdfCache.size > 2 || (bytes > 96L * 1024 * 1024 && pdfCache.size > 1)) {
                    val iterator = pdfCache.entries.iterator()
                    val previous = iterator.next()
                    previous.value.forEach { bytes -= it.data.size }
                    iterator.remove()
                }
            }
            return pages.mapIndexed { i, _ -> Page(i, imageUrl = "$baseUrl/__mangadash_pdf/$key/$i") }
        }

        throw Exception("Nenhuma imagem encontrada para este capítulo.")
    }

    override fun imageUrlParse(response: Response): String = throw UnsupportedOperationException("Not used.")

    // ============================== Filters ==============================
    override fun getFilterList() = FilterList(
        SortFilter(),
        CategoryFilter(),
        StatusFilter(),
        YearFilter(),
        Plus18Filter(),
    )

    // ============================= Utilities =============================
    companion object {
        private const val PREF_USERNAME = "pref_username"
        private const val PREF_PASSWORD = "pref_password"

        private val dateFormat by lazy {
            SimpleDateFormat("dd/MM/yyyy", Locale("pt", "BR"))
        }
    }
}
