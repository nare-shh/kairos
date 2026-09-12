import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { CartProvider } from './context/CartContext'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CartProvider>
          <App />
          <Toaster
            position="bottom-center"
            toastOptions={{
              style: {
                background: '#FDFCFA',
                color: '#16170F',
                border: '1px solid #DFD9CC',
                borderRadius: '9999px',
                padding: '10px 18px',
                fontSize: '14px',
                boxShadow: '0 8px 30px rgba(22, 23, 15, 0.08)',
              },
              duration: 3000,
              success: { iconTheme: { primary: '#647550', secondary: '#FDFCFA' } },
              error:   { iconTheme: { primary: '#9B3B2F', secondary: '#FDFCFA' } },
            }}
          />
        </CartProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)
