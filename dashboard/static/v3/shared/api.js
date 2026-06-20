/**
 * API Client Wrapper
 * Adds JWT authentication to all fetch requests
 */

const API_BASE = '/api';

/**
 * Get the current auth token from window.authToken
 * @returns {string | null}
 */
function getAuthToken() {
  return window.authToken || null;
}

/**
 * Wrapper around fetch that adds JWT Authorization header
 * and handles common response formats
 *
 * @param {string} endpoint - API endpoint (without /api prefix)
 * @param {Object} options - fetch options
 * @param {string} [options.method='GET']
 * @param {Object} [options.body]
 * @param {boolean} [options.requiresAuth=true]
 * @returns {Promise<any>}
 */
async function apiFetch(endpoint, options = {}) {
  const {
    method = 'GET',
    body = null,
    requiresAuth = true,
    ...fetchOptions
  } = options;

  const url = endpoint.startsWith('/') ? `${API_BASE}${endpoint}` : `${API_BASE}/${endpoint}`;

  const headers = {
    'Content-Type': 'application/json',
    ...fetchOptions.headers,
  };

  if (requiresAuth) {
    const token = getAuthToken();
    if (!token) {
      throw new Error('No authentication token available');
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    method,
    headers,
    ...fetchOptions,
  };

  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    config.body = JSON.stringify(body);
  } else if (body) {
    config.body = body;
  }

  const response = await fetch(url, config);

  // Handle 401/403 - token expired or invalid
  if (response.status === 401 || response.status === 403) {
    // Clear auth and redirect to login
    window.authToken = null;
    window.location.href = '/login';
    return;
  }

  // Handle other error statuses
  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || JSON.stringify(errJson);
    } catch (e) {
      // Keep default error detail if JSON parsing fails
    }
    console.error('apiFetch error:', errorDetail);
    alert(`Error: ${response.status} ${response.statusText}`);
    throw new Error(errorDetail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  // Always attempt to parse JSON
  try {
    return await response.json();
  } catch (e) {
    console.error('Invalid JSON response:', e);
    throw e;
  }
}

/**
 * Convenience methods for common HTTP verbs
 */
export const api = {
  get: (endpoint, options = {}) => apiFetch(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options = {}) => apiFetch(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options = {}) => apiFetch(endpoint, { ...options, method: 'PUT', body }),
  delete: (endpoint, options = {}) => apiFetch(endpoint, { ...options, method: 'DELETE' }),
  patch: (endpoint, body, options = {}) => apiFetch(endpoint, { ...options, method: 'PATCH', body }),
};

// Make apiFetch available globally for backwards compatibility
window.apiFetch = apiFetch;
window.api = api;

export default apiFetch;
