const API_BASE = '/api';
let token = localStorage.getItem('ws_token');
let userRole = localStorage.getItem('ws_role');

document.addEventListener('DOMContentLoaded', () => {
    if (token) {
        showApp();
    } else {
        document.getElementById('auth-overlay').style.display = 'flex';
    }

    // Toggle Forms
    document.getElementById('show-register').addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('login-container').style.display = 'none';
        document.getElementById('register-container').style.display = 'block';
    });

    document.getElementById('show-login').addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('register-container').style.display = 'none';
        document.getElementById('login-container').style.display = 'block';
    });

    // Login Handler
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        // ... previous login logic if needed, but the main logic is likely below in global scope
    });

    // Register Handler
    document.getElementById('register-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const u = document.getElementById('reg-username').value;
        const em = document.getElementById('reg-email').value;
        const p = document.getElementById('reg-password').value;

        const msg = document.getElementById('register-msg');
        msg.style.display = 'none';
        msg.className = 'auth-msg';

        try {
            const res = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: u, email: em, password: p })
            });

            const data = await res.json();
            if (res.ok) {
                // Inline success message
                msg.textContent = "Compte créé ! Redirection...";
                msg.classList.add('success');
                msg.style.display = 'block';

                setTimeout(() => {
                    document.getElementById('register-container').style.display = 'none';
                    document.getElementById('login-container').style.display = 'block';
                    document.getElementById('username').value = u;
                    document.getElementById('password').value = '';
                    msg.style.display = 'none';
                }, 1500);
            } else {
                msg.textContent = data.message || "Erreur de création.";
                msg.classList.add('error');
                msg.style.display = 'block';
            }
        } catch (e) {
            msg.textContent = "Erreur réseau.";
            msg.classList.add('error');
            msg.style.display = 'block';
        }
    });
});

// Correcting the Login Logic block because previous one had bug in fetch headers
document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();
    const u = document.getElementById('username').value;
    const p = document.getElementById('password').value;

    const msg = document.getElementById('login-msg');
    msg.style.display = 'none';
    msg.className = 'auth-msg';

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
        document.getElementById('user-display').textContent = data.username;
        document.getElementById('auth-overlay').style.display = 'none';
        showApp();
    } else {
        msg.textContent = data.message || "Erreur de connexion.";
        msg.classList.add('error');
        msg.style.display = 'block';
    }
};

document.getElementById('logout-btn').onclick = () => {
    localStorage.removeItem('ws_token');
    location.reload();
};

function showApp() {
    document.getElementById('app-container').style.display = 'flex';
    document.getElementById('auth-overlay').style.display = 'none';
    loadBookings();
}

function setInput(text) {
    document.getElementById('chat-input').value = text;
    document.getElementById('chat-input').focus();
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

        addMessage(data.response, 'bot');

        if (data.action_required === 'confirm_booking') {
            // Add a clickable confirmation button in chat
            const btn = document.createElement('button');
            btn.className = 'btn-primary';
            btn.style.marginTop = '0.5rem';
            btn.textContent = 'Confirmer la réservation';
            btn.onclick = () => confirmBooking(data.payload);
            chatHistory.lastElementChild.querySelector('.text').appendChild(btn);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } else if (data.action_required === 'confirm_cancel') {
            const btn = document.createElement('button');
            btn.className = 'btn-secondary'; // Red style if css existed, secondary is fine
            btn.style.marginTop = '0.5rem';
            btn.textContent = 'Confirmer l\'annulation';
            btn.onclick = () => confirmCancellation(data.payload);
            chatHistory.lastElementChild.querySelector('.text').appendChild(btn);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        } else if (data.action_required === 'confirm_cancel_all') {
            const btn = document.createElement('button');
            btn.className = 'btn-secondary';
            btn.style.marginTop = '0.5rem';
            btn.textContent = 'Tout annuler 🚨';
            btn.onclick = () => confirmCancellationAll();
            chatHistory.lastElementChild.querySelector('.text').appendChild(btn);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

    } catch (err) {
        addMessage("Erreur de connexion...", 'bot');
    }
}

sendBtn.onclick = sendMessage;
chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = `
        <div class="avatar">${sender === 'user' ? 'Moi' : 'AI'}</div>
        <div class="text">${text}</div> <!-- Simple text injection, be careful with XSS in prod -->
    `;
    // Fix innerHTML usage to just use textContent for safety normally, but here we want simple structure
    // Let's refine for safety if text contains html (unlikely from bot)
    if (sender === 'bot') div.querySelector('.text').innerHTML = text; // Allow bot html
    else div.querySelector('.text').textContent = text;

    chatHistory.appendChild(div);
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
    } else {
        addMessage(`❌ Erreur: ${data.error}`, 'bot');
    }
}

async function loadBookings() {
    const ul = document.getElementById('bookings-ul');
    ul.innerHTML = '<li class="loading">Chargement...</li>';

    try {
        const res = await fetch(`${API_BASE}/bookings/my_bookings`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const bookings = await res.json();
        ul.innerHTML = '';
        if (bookings.length === 0) {
            ul.innerHTML = '<li>Aucune réservation.</li>';
            return;
        }
        bookings.forEach(b => {
            const start = new Date(b.start_time).toLocaleString('fr-FR', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
            const li = document.createElement('li');
            li.innerHTML = `
                <div class="booking-info">
                    <span class="booking-time">${start}</span>
                    <span class="booking-room">Salle ID: ${b.room_id} (${b.attendees_count} pers)</span>
                </div>
                <button class="btn-icon delete-btn" onclick="deleteBookingFromList(${b.id})">❌</button>
            `;
            ul.appendChild(li);
        });
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
