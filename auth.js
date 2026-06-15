// Auth guard — include on all protected pages
// Checks session validity and redirects to login if not authenticated
(function() {
    fetch('/api/check-auth')
        .then(function(r) {
            if (!r.ok) throw new Error('Not authenticated');
            return r.json();
        })
        .then(function(data) {
            if (!data.authenticated) {
                window.location.href = '/login.html';
            }
        })
        .catch(function() {
            window.location.href = '/login.html';
        });
})();

function logout() {
    fetch('/api/logout', { method: 'POST' })
        .then(function() {
            window.location.href = '/login.html';
        })
        .catch(function() {
            window.location.href = '/login.html';
        });
}
