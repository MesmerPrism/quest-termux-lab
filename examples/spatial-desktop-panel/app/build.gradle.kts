plugins {
  id("com.android.application")
  id("org.jetbrains.kotlin.android")
  id("com.meta.spatial.plugin") version "0.13.2"
}

android {
  namespace = "io.github.mesmerprism.questtermuxlab.spatialdesktop"
  compileSdk = 35
  defaultConfig {
    applicationId = "io.github.mesmerprism.questtermuxlab.spatialdesktop"
    minSdk = 34
    targetSdk = 35
    versionCode = 4
    versionName = "0.2.2"
    ndk { abiFilters += "arm64-v8a" }
  }
  buildFeatures { buildConfig = true }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }
  kotlinOptions { jvmTarget = "17" }
  testOptions { unitTests.isReturnDefaultValues = true }
}

dependencies {
  implementation("androidx.core:core-ktx:1.15.0")
  implementation("com.meta.spatial:meta-spatial-sdk:0.13.2")
  implementation("com.meta.spatial:meta-spatial-sdk-toolkit:0.13.2")
  implementation("com.meta.spatial:meta-spatial-sdk-vr:0.13.2")
  implementation("com.meta.spatial:meta-spatial-sdk-isdk:0.13.2")
  testImplementation("junit:junit:4.13.2")
}

spatial { allowUsageDataCollection.set(false) }
