// CRT Force Logout - Run this in browser console
// Copy and paste this entire script into the browser DevTools console

(function() {
    console.log('🔒 CRT Force Logout Script Starting...\n');
    
    // Clear auth token
    const hadToken = localStorage.getItem('crt_auth_token') !== null;
    localStorage.removeItem('crt_auth_token');
    console.log(hadToken ? '✓ Removed auth token' : '○ No auth token found');
    
    // Clear chat storage
    const hadChats = localStorage.getItem('crt-chat-state') !== null;
    localStorage.removeItem('crt-chat-state');
    console.log(hadChats ? '✓ Removed chat storage' : '○ No chat storage found');
    
    // Clear all CRT-related keys
    const keys = Object.keys(localStorage);
    const crtKeys = keys.filter(k => k.toLowerCase().includes('crt'));
    let count = 0;
    crtKeys.forEach(key => {
        localStorage.removeItem(key);
        count++;
    });
    console.log(`✓ Removed ${count} CRT-related localStorage keys`);
    
    // Clear session storage
    sessionStorage.clear();
    console.log('✓ Cleared sessionStorage');
    
    console.log('\n✅ Force logout complete!');
    console.log('🔄 Reloading page in 2 seconds...\n');
    
    setTimeout(() => {
        window.location.reload();
    }, 2000);
})();
