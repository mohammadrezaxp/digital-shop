// Digital Shop - API Connection Layer
// Minimal JS to connect static templates to DRF API

const API_BASE = '/api';

// Helper: get JWT token from localStorage
function getToken() {
    return localStorage.getItem('access_token');
}

// Helper: set JWT token
function setToken(token) {
    localStorage.setItem('access_token', token);
}

// Helper: clear token
function clearToken() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
}

// Helper: API request with auth
async function apiRequest(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers,
    });
    
    if (response.status === 401) {
        clearToken();
        window.location.href = '/login/';
        return;
    }
    
    return response;
}

// ============ AUTH ============

// Login form handler
async function handleLogin(event) {
    event.preventDefault();
    const form = event.target;
    const email = form.querySelector('#email').value;
    const password = form.querySelector('#password').value;
    
    try {
        const response = await fetch(`${API_BASE}/auth/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: email, password }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            setToken(data.access);
            localStorage.setItem('refresh_token', data.refresh);
            window.location.href = '/profile/';
        } else {
            alert(data.detail || 'ورود ناموفق بود');
        }
    } catch (error) {
        alert('خطا در ارتباط با سرور');
    }
}

// Signup form handler
async function handleSignup(event) {
    event.preventDefault();
    const form = event.target;
    const fullname = form.querySelector('#fullname').value;
    const email = form.querySelector('#email').value;
    const password = form.querySelector('#password').value;
    const confirmPassword = form.querySelector('#confirm_password').value;
    
    if (password !== confirmPassword) {
        alert('رمز عبور و تکرار آن مطابقت ندارند');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/auth/register/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                username: email.split('@')[0],
                email,
                password,
                first_name: fullname,
            }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            setToken(data.access);
            localStorage.setItem('refresh_token', data.refresh);
            window.location.href = '/profile/';
        } else {
            alert(JSON.stringify(data) || 'ثبت نام ناموفق بود');
        }
    } catch (error) {
        alert('خطا در ارتباط با سرور');
    }
}

// ============ PRODUCTS ============

// Fetch and render products
async function loadProducts() {
    const container = document.querySelector('[data-products-container]');
    if (!container) return;
    
    try {
        const response = await apiRequest('/products/');
        const data = await response.json();
        
        const products = data.results || data;
        
        container.innerHTML = products.map(product => `
            <article class="bg-white/80 backdrop-blur-sm rounded-lg p-8 flex flex-col gap-6 relative overflow-hidden group shadow-sm hover:shadow-md transition-all duration-300 border border-outline-variant/10">
                <div class="absolute -top-10 -right-10 w-32 h-32 bg-primary/20 rounded-full blur-3xl group-hover:bg-primary/30 transition-colors duration-500"></div>
                <div class="flex justify-between items-start">
                    <img alt="${product.name}" class="w-16 h-16 rounded-full object-cover border border-outline-variant/20 shadow-md group-hover:scale-110 transition-transform duration-500" src="${product.image || '/static/images/logos/steam.png'}" style="transition-timing-function: cubic-bezier(0.34, 1.56, 0.64, 1);"/>
                    <span class="px-3 py-1 rounded-full bg-surface-container-highest text-on-surface-variant font-label-mono text-label-mono border border-outline-variant/10">${product.category?.name || 'محصول'}</span>
                </div>
                <div>
                    <h3 class="font-headline-md text-headline-md text-surface mb-2">${product.name}</h3>
                    <p class="font-body-md text-body-md text-surface/60 line-clamp-2">${product.description || ''}</p>
                </div>
                <div class="mt-auto pt-4 border-t border-outline-variant/20 flex justify-between items-center">
                    <span class="font-headline-md text-headline-md text-secondary text-sm md:text-base">از ${product.price?.toLocaleString('fa-IR') || '۰'} تومان</span>
                    <button class="btn-glow px-4 md:px-6 py-2 rounded-lg text-on-primary-fixed font-bold font-body-md text-body-md text-sm md:text-base" onclick="addToCart(${product.id})">خرید</button>
                </div>
            </article>
        `).join('');
    } catch (error) {
        console.error('Failed to load products:', error);
    }
}

// Add to cart (placeholder)
function addToCart(productId) {
    alert(`محصول ${productId} به سبد خرید اضافه شد`);
}

// ============ PROFILE ============

// Load user profile
async function loadProfile() {
    const container = document.querySelector('[data-profile-container]');
    if (!container) return;
    
    const token = getToken();
    if (!token) {
        window.location.href = '/login/';
        return;
    }
    
    try {
        const response = await apiRequest('/profile/');
        const data = await response.json();
        
        container.innerHTML = `
            <div class="glass-panel rounded-xl p-8 flex flex-col items-center text-center relative overflow-hidden group">
                <div class="w-24 h-24 rounded-full p-1 bg-gradient-to-tr from-primary to-secondary mb-4 relative z-10 shadow-[0_0_20px_rgba(192,193,255,0.2)]">
                    <img class="w-full h-full object-cover rounded-full border-2 border-surface-container" src="${data.avatar || '/static/images/logos/steam.png'}" alt="Avatar"/>
                </div>
                <h2 class="font-headline-md text-headline-md text-on-surface mb-1 z-10">${data.first_name} ${data.last_name}</h2>
                <p class="font-label-mono text-label-mono text-secondary mb-4 z-10">${data.email}</p>
                <div class="inline-flex items-center gap-2 bg-surface-container-highest rounded-full px-4 py-2 mt-2 z-10 border border-outline-variant/20">
                    <span class="material-symbols-outlined text-[16px] text-tertiary">verified</span>
                    <span class="font-label-mono text-label-mono text-on-surface-variant">عضویت از ${data.created_at?.split('T')[0] || '۱۴۰۲'}</span>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load profile:', error);
    }
}

// ============ INITIALIZATION ============

document.addEventListener('DOMContentLoaded', () => {
    // Login form
    const loginForm = document.querySelector('form[action="/login/"]');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Signup form
    const signupForm = document.querySelector('form[action="/signup/"]');
    if (signupForm) {
        signupForm.addEventListener('submit', handleSignup);
    }
    
    // Load products on catalog page
    if (document.querySelector('[data-products-container]')) {
        loadProducts();
    }
    
    // Load profile on profile page
    if (document.querySelector('[data-profile-container]')) {
        loadProfile();
    }
    
    // Update auth UI
    const token = getToken();
    const authLinks = document.querySelectorAll('[data-auth-link]');
    authLinks.forEach(link => {
        if (token) {
            link.textContent = 'پروفایل';
            link.href = '/profile/';
        } else {
            link.textContent = 'ورود';
            link.href = '/login/';
        }
    });
});