const API_BASE = '/api';
let token = localStorage.getItem('ws_token');
let userRole = localStorage.getItem('ws_role');

document.addEventListener('DOMContentLoaded', () => {
    if (token) {
        showApp();
    } else {
        document.getElementById('auth-overlay').style.display = 'flex';
    }

    // Login Handler
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.onsubmit = async (e) => {
            e.preventDefault();
            const u = document.getElementById('username').value;
            const p = document.getElementById('password').value;

            const msg = document.getElementById('login-msg');
            msg.style.display = 'none';
            msg.className = 'auth-msg';

            try {
                const res = await fetch(`${API_BASE}/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: u, password: p })
                });

                const data = await res.json();
                if (res.ok) {
                    token = data.token;
                    userRole = data.role;
                    localStorage.setItem('ws_token', token);
                    localStorage.setItem('ws_role', userRole);
                    // document.getElementById('user-display').textContent = data.username; // Removed in mobile
                    document.getElementById('auth-overlay').style.display = 'none';
                    showApp();
                } else {
                    msg.textContent = data.message || "Erreur de connexion.";
                    msg.classList.add('error');
                    msg.style.display = 'block';
                }
            } catch (err) {
                msg.textContent = "Erreur réseau.";
                msg.classList.add('error');
                msg.style.display = 'block';
            }
        };
    }
});


function showApp() {
    document.getElementById('app-container').style.display = 'flex';
    document.getElementById('auth-overlay').style.display = 'none';
    lucide.createIcons();
    loadBookings();
}

function logout() {
    localStorage.removeItem('ws_token');
    location.reload();
}

// -- Mobile Nav Logic --
function switchTab(tabName) {
    // Hide all sections
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    // Deactivate nav items
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    // Show target
    document.getElementById(`view-${tabName}`).classList.add('active');

    // Activate nav item
    // Simple lookup based on onclick string
    const navItems = document.querySelectorAll('.nav-item');
    if (tabName === 'dashboard') navItems[0].classList.add('active');
    if (tabName === 'chat') navItems[1].classList.add('active');

    lucide.createIcons();
}

function setInputAndSwitch(text) {
    switchTab('chat');
    // small delay to let view render
    setTimeout(() => {
        document.getElementById('chat-input').value = text;
        document.getElementById('chat-input').focus();
    }, 100);
}

// Global Chat Logic
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    chatInput.value = '';

    // Loading Indicator
    const loaderDiv = document.createElement('div');
    loaderDiv.className = 'message bot loading-msg';
    loaderDiv.innerHTML = `
        <div class="avatar"><i data-lucide="bot"></i></div>
        <div class="text"><i data-lucide="loader-2" class="animate-spin"></i></div>
    `;
    chatHistory.appendChild(loaderDiv);
    lucide.createIcons();
    chatHistory.scrollTop = chatHistory.scrollHeight;

    try {
        const res = await fetch(`${API_BASE}/chat/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message: text })
        });
        const data = await res.json();

        // Remove loader
        loaderDiv.remove();

        addMessage(data.response, 'bot');

        if (data.action_required) {
            handleAction(data);
        }

    } catch (err) {
        loaderDiv.remove();
        addMessage("Erreur de connexion...", 'bot');
    }
}

if (sendBtn) sendBtn.onclick = sendMessage;
if (chatInput) chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

function handleAction(data) {
    const container = chatHistory.lastElementChild.querySelector('.text');
    const btn = document.createElement('button');
    btn.className = 'btn-primary';
    btn.style.marginTop = '0.5rem';
    btn.style.fontSize = '0.9rem';
    btn.style.padding = '0.5rem 1rem';

    if (data.action_required === 'confirm_booking') {
        btn.innerHTML = '<i data-lucide="check"></i> Confirmer';
        btn.onclick = () => confirmBooking(data.payload);
    } else if (data.action_required === 'confirm_cancel') {
        btn.innerHTML = '<i data-lucide="x-circle"></i> Confirmer Annulation';
        btn.onclick = () => confirmCancellation(data.payload);
    } else if (data.action_required === 'confirm_cancel_all') {
        btn.innerHTML = '<i data-lucide="alert-triangle"></i> Tout Annuler';
        btn.onclick = () => confirmCancellationAll();
    }
    container.appendChild(btn);
    lucide.createIcons();
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    const avatarIcon = sender === 'user' ? 'user' : 'bot';

    div.innerHTML = `
        <div class="avatar"><i data-lucide="${avatarIcon}"></i></div>
        <div class="text">${text}</div>
    `;

    // Check if simple text or html (bot uses HTML for multiline)
    if (sender === 'bot') div.querySelector('.text').innerHTML = text;
    else div.querySelector('.text').textContent = text; // User text safe

    chatHistory.appendChild(div);
    lucide.createIcons();
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function confirmBooking(payload) {
    addMessage("Confirmation en cours...", 'user');
    const res = await fetch(`${API_BASE}/bookings/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
        addMessage(`✅ Réservation confirmée ! ID: ${data.id}`, 'bot');
        loadBookings();
        fetch(`${API_BASE}/chat/context`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    } else {
        addMessage(`❌ Erreur: ${data.error}`, 'bot');
    }
}

async function confirmCancellation(payload) {
    addMessage("Annulation en cours...", 'user');
    const res = await fetch(`${API_BASE}/bookings/${payload.booking_id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    if (res.ok) {
        addMessage(`✅ Réservation annulée.`, 'bot');
        loadBookings();
        fetch(`${API_BASE}/chat/context`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    } else {
        addMessage(`❌ Erreur: ${data.error}`, 'bot');
    }
}

async function confirmCancellationAll() {
    addMessage("Annulation de toutes les réservations...", 'user');
    const res = await fetch(`${API_BASE}/bookings/batch`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();
    if (res.ok) {
        addMessage(`✅ ${data.message}`, 'bot');
        loadBookings();
        fetch(`${API_BASE}/chat/context`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    } else {
        addMessage(`❌ Erreur: ${data.error}`, 'bot');
    }
}

async function loadBookings() {
    const ul = document.getElementById('bookings-ul');
    if (!ul) return;
    ul.innerHTML = '<li class="loading"><i data-lucide="loader-2" class="animate-spin"></i> Chargement...</li>';
    lucide.createIcons();

    try {
        const res = await fetch(`${API_BASE}/bookings/my_bookings`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const bookings = await res.json();
        ul.innerHTML = '';
        if (bookings.length === 0) {
            ul.innerHTML = '<li style="padding:1rem; text-align:center; color:#94a3b8;">Aucune réservation.</li>';
            return;
        }
        bookings.forEach(b => {
            const start = new Date(b.start_time).toLocaleString('fr-FR', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
            const li = document.createElement('li');
            li.className = 'booking-item'; // New class
            li.innerHTML = `
                <div class="booking-details">
                    <span class="booking-time">${start}</span>
                    <span class="booking-meta"><i data-lucide="map-pin" class="icon-xs"></i> ${b.room_name} (${b.attendees_count}p)</span>
                </div>
                <button class="btn-delete" onclick="deleteBookingFromList(${b.id})"><i data-lucide="trash-2"></i></button>
            `;
            ul.appendChild(li);
        });
        lucide.createIcons();
    } catch (e) {
        ul.innerHTML = '<li>Impossible de charger.</li>';
    }
}

async function deleteBookingFromList(id) {
    // No confirmation as requested for fluidity
    try {
        const res = await fetch(`${API_BASE}/bookings/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            loadBookings();
        } else {
            console.error("Erreur suppression backend");
        }
    } catch (e) {
        console.error("Erreur réseau suppression");
    }
}

