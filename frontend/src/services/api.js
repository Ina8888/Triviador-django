// Helper to read cookie by name
export function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Ensure CSRF token is present
export async function ensureCsrfToken() {
  let token = getCookie('csrftoken');
  if (!token) {
    await fetch('/api/auth/csrf/', {
      method: 'GET',
      credentials: 'include',
    });
    token = getCookie('csrftoken');
  }
  return token;
}

// Base API fetcher with CSRF and credentials
export async function apiRequest(url, method = 'GET', data = null) {
  const options = {
    method,
    headers: {
      'Accept': 'application/json',
    },
    credentials: 'include',
  };

  if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method.toUpperCase())) {
    const csrfToken = await ensureCsrfToken();
    if (csrfToken) {
      options.headers['X-CSRFToken'] = csrfToken;
    }
  }

  if (data) {
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(data);
  }

  const response = await fetch(url, options);

  if (response.status === 204) {
    return { ok: true, data: null };
  }

  const json = await response.json().catch(() => null);

  if (!response.ok) {
    return { ok: false, status: response.status, errors: json?.errors || json || {} };
  }

  return { ok: true, status: response.status, data: json };
}

// Authentication API methods
export const authApi = {
  getCsrf: () => ensureCsrfToken(),
  register: (payload) => apiRequest('/api/auth/register/', 'POST', payload),
  login: (payload) => apiRequest('/api/auth/login/', 'POST', payload),
  logout: () => apiRequest('/api/auth/logout/', 'POST'),
  getMe: () => apiRequest('/api/auth/me/', 'GET'),
  updateProfile: (payload) => apiRequest('/api/auth/me/', 'PATCH', payload),
};
