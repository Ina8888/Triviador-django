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
    try {
      await fetch('/api/auth/csrf/', {
        method: 'GET',
        credentials: 'include',
      });
      token = getCookie('csrftoken');
    } catch (err) {
      console.warn('Could not fetch CSRF token:', err);
    }
  }
  return token;
}

// Base API fetcher with CSRF, credentials, and robust error handling
export async function apiRequest(url, method = 'GET', data = null) {
  try {
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

    let json = null;
    try {
      json = await response.json();
    } catch {
      // Non-JSON response (e.g. 500 HTML/text from proxy or server)
    }

    if (!response.ok) {
      let errors = {};
      if (json && typeof json === 'object') {
        errors = json.errors || json;
      } else {
        errors = {
          detail:
            response.status === 500 || response.status === 502 || response.status === 504
              ? 'Сървърът не отговаря (възможно е Django да не е стартиран на порт 8000).'
              : `Грешка ${response.status}: Сървърът върна неочакван отговор.`,
        };
      }
      return { ok: false, status: response.status, errors };
    }

    return { ok: true, status: response.status, data: json };
  } catch (err) {
    console.error(`API request error on ${url}:`, err);
    return {
      ok: false,
      status: 0,
      errors: {
        detail:
          'Няма връзка с Django сървъра. Моля, стартирайте бекенда в отделен терминал с: python manage.py runserver',
      },
    };
  }
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

// Questions API methods
export const questionsApi = {
  getRandom: () => apiRequest('/api/questions/random/', 'GET'),
  getAll: () => apiRequest('/api/questions/', 'GET'),
};
