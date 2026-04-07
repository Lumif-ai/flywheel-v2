/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FEATURE_EMAIL?: string
  readonly VITE_FEATURE_TASKS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
