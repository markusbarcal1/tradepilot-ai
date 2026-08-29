import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import AuthProvider from './auth/AuthProvider.jsx'
import AuthGate from './components/AuthGate.jsx'

const savedTheme = localStorage.getItem('tradepilot-theme')
document.documentElement.dataset.theme = savedTheme === 'light' ? 'light' : 'dark'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  </StrictMode>,
)
