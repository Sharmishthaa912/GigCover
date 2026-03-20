import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? '/api' : '')

export const api = axios.create({
  baseURL: API_BASE_URL,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('gigcover_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  console.log('[api request]', config.method?.toUpperCase(), `${config.baseURL || ''}${config.url || ''}`, config.data || {})
  return config
})

api.interceptors.response.use(
  (response) => {
    console.log('[api response]', response.status, response.config.url, response.data)
    return response
  },
  (error) => {
    const status = error?.response?.status
    const data = error?.response?.data
    console.error('[api error]', status, error?.config?.url, data || error.message)
    return Promise.reject(error)
  },
)
