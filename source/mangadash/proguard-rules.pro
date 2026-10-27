-dontwarn java.awt.**
-dontwarn javax.imageio.**
-dontwarn java.beans.**
-dontwarn org.apache.log4j.**
-dontwarn org.apache.avalon.**
-dontwarn org.apache.log.**

# Commons Logging resolves these implementations by their class names at runtime.
-keep class org.apache.commons.logging.** { *; }

# Keep the small PDF entry point so CI tests the optimized, published JAR directly.
-keep class eu.kanade.tachiyomi.extension.pt.mangadash.PdfImageExtractor {
    public static java.util.List extract(java.io.InputStream);
}
-keep class eu.kanade.tachiyomi.extension.pt.mangadash.PdfImageExtractor$Image {
    public *;
}
