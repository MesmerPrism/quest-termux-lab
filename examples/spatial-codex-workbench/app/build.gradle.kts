plugins {
  id("com.android.application")
  id("org.jetbrains.kotlin.android")
  id("com.meta.spatial.plugin") version "0.13.2"
}

val prepareWorkbenchAssets by tasks.registering(Sync::class) {
  into(layout.buildDirectory.dir("generated/workbench-assets"))
  from("../sidecar") {
    into("workbench/sidecar")
    exclude("tests/**")
  }
  from("../demo-project") {
    into("workbench/demo-project")
    exclude(".gitignore", "build/**")
  }
}

android {
  namespace = "io.github.mesmerprism.questtermuxlab.spatialcodex"
  compileSdk = 35

  defaultConfig {
    applicationId = "io.github.mesmerprism.questtermuxlab.spatialcodex"
    minSdk = 34
    targetSdk = 35
    versionCode = 1
    versionName = "0.1.0"
    testInstrumentationRunner = "io.github.mesmerprism.questtermuxlab.spatialcodex.WorkbenchE2eInstrumentation"
    ndk { abiFilters += "arm64-v8a" }
  }

  buildFeatures { buildConfig = true }
  sourceSets.named("main") {
    assets.srcDir("../web")
    assets.srcDir(layout.buildDirectory.dir("generated/workbench-assets"))
  }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }
  kotlinOptions { jvmTarget = "17" }
  testOptions { unitTests.isReturnDefaultValues = true }
}

tasks.configureEach {
  if (name == "preBuild") dependsOn(prepareWorkbenchAssets)
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
