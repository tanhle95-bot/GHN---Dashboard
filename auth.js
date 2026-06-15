// Auth guard — include on all protected pages
(function() {
    var token = localStorage.getItem('session_token');
    if (!token) {
        window.location.href = '/login.html';
        return;
    }

    fetch('/api/check-auth', {
        headers: { 'Authorization': 'Bearer ' + token }
    })
    .then(function(r) {
        if (!r.ok) {
            localStorage.removeItem('session_token');
            window.location.href = '/login.html';
        }
    })
    .catch(function() {
        localStorage.removeItem('session_token');
        window.location.href = '/login.html';
    });
})();

// Helper: add auth header to any fetch
function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};
    var token = localStorage.getItem('session_token');
    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    return fetch(url, options);
}

function logout() {
    localStorage.removeItem('session_token');
    fetch('/api/logout', { method: 'POST' }).catch(function(){});
    window.location.href = '/login.html';
}
