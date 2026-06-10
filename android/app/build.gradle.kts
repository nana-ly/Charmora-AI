plugins {
    id("com.android.application")
}

// ====== 读取项目根目录 .env 文件 ======
import java.util.Properties

val envFile = rootProject.file(".env")
val envProps = Properties()
if (envFile.exists()) {
    envProps.load(envFile.inputStream())
}

android {
    namespace = "com.client.shopguide"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.client.shopguide"
        minSdk = 24
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // 百度语音识别凭证，从 .env 注入到 BuildConfig
        buildConfigField("String", "BAIDU_APP_ID", "\"${envProps.getProperty("BAIDU_APP_ID", "")}\"")
        buildConfigField("String", "BAIDU_API_KEY", "\"${envProps.getProperty("BAIDU_API_KEY", "")}\"")
        buildConfigField("String", "BAIDU_SECRET_KEY", "\"${envProps.getProperty("BAIDU_SECRET_KEY", "")}\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation("androidx.activity:activity:1.8.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("com.google.android.material:material:1.11.0")

    // RecyclerView
    implementation("androidx.recyclerview:recyclerview:1.3.2")

    // CardView
    implementation("androidx.cardview:cardview:1.0.0")

    // Retrofit + Gson
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Coil 图片加载
    implementation("io.coil-kt:coil:2.6.0")

    // Markdown 渲染（Markwon）
    implementation("io.noties.markwon:core:4.6.2")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
}