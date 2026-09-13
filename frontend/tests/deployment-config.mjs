import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { createServer } from 'vite'
import { validateBuildEnvironment } from '../vite.config.js'

const configured = {
  VITE_API_BASE_URL: 'https://api.example.com',
  VITE_SUPABASE_URL: 'https://project.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'public-test-key',
}
assert.doesNotThrow(() => validateBuildEnvironment(configured))
assert.doesNotThrow(() => validateBuildEnvironment({
  ...configured, VITE_SUPABASE_ANON_KEY: '', VITE_SUPABASE_PUBLISHABLE_KEY: 'public-test-key',
}))
for (const name of Object.keys(configured)) {
  assert.throws(() => validateBuildEnvironment({ ...configured, [name]: ' ' }), /Missing build configuration/)
}
assert.throws(() => validateBuildEnvironment({}), /VITE_API_BASE_URL/)

// Prove the actual build refuses missing settings even when a local .env exists.
const missingBuild = spawnSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build'], {
  encoding: 'utf8',
  env: { ...process.env, VITE_API_BASE_URL: '', VITE_SUPABASE_URL: '',
    VITE_SUPABASE_ANON_KEY: '', VITE_SUPABASE_PUBLISHABLE_KEY: '' },
})
assert.notEqual(missingBuild.status, 0)
assert.match(missingBuild.stderr, /Missing build configuration: VITE_API_BASE_URL/)

// Exercise the anon-key alias and the preserved development API default.
Object.assign(process.env, configured, { VITE_API_BASE_URL: '', VITE_SUPABASE_PUBLISHABLE_KEY: '' })
const vite = await createServer({
  configFile: false, envFile: false, server: { middlewareMode: true },
  appType: 'custom', logLevel: 'error',
})
try {
  const { isSupabaseConfigured, supabase } = await vite.ssrLoadModule('/src/lib/supabase.js')
  assert.equal(isSupabaseConfigured, true)
  assert.ok(supabase)
  const { API_BASE_URL } = await vite.ssrLoadModule('/src/api/client.js')
  assert.equal(API_BASE_URL, 'http://127.0.0.1:8000')
} finally {
  await vite.close()
}
console.log('Deployment environment checks passed')
