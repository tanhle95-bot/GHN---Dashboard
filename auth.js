// Simple auth guard — password prompt
(function() {
    var PASS = 'GiaoHangNhanhB2B';
    var saved = sessionStorage.getItem('ghn_auth');
    if (saved === 'ok') return;

    var input = prompt('Nhập mật khẩu để truy cập Dashboard:');
    if (input === PASS) {
        sessionStorage.setItem('ghn_auth', 'ok');
    } else {
        document.body.innerHTML = '<h2 style="color:white;text-align:center;margin-top:100px">Sai mật khẩu</h2>';
        throw new Error('Auth failed');
    }
})();

// Helper: authFetch (no token needed with simple auth)
function authFetch(url, options) {
    return fetch(url, options || {});
}

function logout() {
    sessionStorage.removeItem('ghn_auth');
    location.reload();
}
