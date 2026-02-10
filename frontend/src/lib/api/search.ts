import apiClient from './client'
import { SearchRequest, SearchResponse, AskRequest } from '@/lib/types/search'

export const searchApi = {
  // Standard search (non-streaming)
  search: async (params: SearchRequest) => {
    const response = await apiClient.post<SearchResponse>('/search', params)
    return response.data
  },

  // Ask with streaming (uses relative URL for Docker compatibility)
  askKnowledgeBase: async (params: AskRequest) => {
    // Get auth token using the same logic as apiClient interceptor
    let token = null
    if (typeof window !== 'undefined') {
      const authStorage = localStorage.getItem('auth-storage')
      if (authStorage) {
        try {
          const { state } = JSON.parse(authStorage)
          if (state?.token) {
            token = state.token
          }
        } catch (error) {
          console.error('Error parsing auth storage:', error)
        }
      }
    }

    // Use relative URL to leverage Next.js rewrites
    // This works both in dev (Next.js proxy) and production (Docker network)
    const url = '/api/search/ask'

    // Long timeout for ask (LLM + multiple searches can take several minutes).
    // AbortController ensures we surface a clear timeout instead of generic "Failed to fetch".
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 600_000) // 10 minutes

    try {
      const response = await fetch(url, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` })
        },
        body: JSON.stringify(params)
      })
      clearTimeout(timeoutId)

      if (!response.ok) {
        // Mirror apiClient: on 401 clear auth and redirect to login
        if (response.status === 401 && typeof window !== 'undefined') {
          localStorage.removeItem('auth-storage')
          window.location.href = '/login'
        }
        // Try to extract error message from response
        let errorMessage = `HTTP error! status: ${response.status}`
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorData.message || errorMessage
        } catch {
          // If response isn't JSON, use status text
          errorMessage = response.statusText || errorMessage
        }
        throw new Error(errorMessage)
      }

      if (!response.body) {
        throw new Error('No response body received')
      }

      return response.body
    } catch (err) {
      clearTimeout(timeoutId)
      const isAbort = (err as { name?: string })?.name === 'AbortError'
      const isNetwork =
        err instanceof TypeError &&
        ((err as Error).message === 'Failed to fetch' || (err as Error).message === 'Load failed')
      if (isAbort || isNetwork) {
        throw new Error('Connection lost or request timed out. Ask can take several minutes—please try again or check your network.')
      }
      throw err
    }
  }
}
