import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'

export function validateBuildEnvironment(env) {
  const missing = ['VITE_API_BASE_URL', 'VITE_SUPABASE_URL']
    .filter((name) => !env[name]?.trim())
  if (!env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() && !env.VITE_SUPABASE_ANON_KEY?.trim()) {
    missing.push('VITE_SUPABASE_PUBLISHABLE_KEY or VITE_SUPABASE_ANON_KEY')
  }
  if (missing.length) throw new Error(`Missing build configuration: ${missing.join(', ')}`)
}

export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    validateBuildEnvironment(loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), 'VITE_'))
  }
  return { plugins: [react()] }
})
