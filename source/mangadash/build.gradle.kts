import io.github.keiyoushi.gradle.api.ContentWarning

plugins {
    alias(kei.plugins.extension)
}

keiyoushi {
    name = "MangaDash"
    versionCode = 3
    contentWarning = ContentWarning.MIXED
    libVersion = "1.4"

    source {
        lang = "pt-BR"
        baseUrl = "https://mangadash.net"
    }
}

dependencies {
    implementation(files("libs/pdfbox-headless.jar", "libs/fontbox.jar", "libs/commons-logging.jar"))
}

extensions.configure<com.android.build.api.dsl.ApplicationExtension> {
    packaging.resources.merges.add("META-INF/LICENSE")
    packaging.resources.merges.add("META-INF/NOTICE")
}
