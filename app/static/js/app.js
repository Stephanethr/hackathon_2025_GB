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
                    localStorage.setItem('ws_username', data.username);
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

    // Check Admin Role
    if (userRole === 'admin') {
        document.getElementById('nav-admin').style.display = 'flex';
    } else {
        document.getElementById('nav-admin').style.display = 'none';
    }

    lucide.createIcons();
    loadBookings();

    // Set Username
    const username = localStorage.getItem('ws_username') || 'Invité';
    const avatarEl = document.getElementById('user-avatar-sm');
    if (avatarEl) {
        avatarEl.textContent = username;
    }
}

function logout() {
    localStorage.removeItem('ws_token');
    localStorage.removeItem('ws_role'); // Clear role
    localStorage.removeItem('ws_username');
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
    const navItems = document.querySelectorAll('.nav-item');
    if (tabName === 'dashboard') navItems[0].classList.add('active');
    if (tabName === 'chat') navItems[1].classList.add('active');
    if (tabName === 'admin') {
        document.getElementById('nav-admin').classList.add('active');
        switchAdminTab('users'); // Default sub-tab
    }

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

    // Create Bot Message Bubble
    let botMsgDiv = document.createElement('div');
    botMsgDiv.className = 'message bot';
    botMsgDiv.innerHTML = `
        <div class="avatar"><i data-lucide="bot"></i></div>
        <div class="text"><i data-lucide="loader-2" class="animate-spin"></i></div>
    `;
    chatHistory.appendChild(botMsgDiv);
    lucide.createIcons();
    chatHistory.scrollTop = chatHistory.scrollHeight;

    const msgTextContainer = botMsgDiv.querySelector('.text');
    let isFirstChunk = true;
    let fullResponse = "";

    try {
        const res = await fetch(`${API_BASE}/chat/message`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message: text })
        });

        if (!res.ok) throw new Error("Network error");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            let lines = buffer.split('\n');
            buffer = lines.pop(); // Keep incomplete line

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);

                    if (data.type === 'delta') {
                        if (isFirstChunk) {
                            msgTextContainer.innerHTML = ''; // Clear loader
                            isFirstChunk = false;
                        }
                        // Handle simple markdownish formatting (newlines)
                        // For proper markdown we might need a library, but let's just use simple text append
                        // or better: utilize innerHTML carefully. 
                        // The backend sends markdown. We should parse it ideally.
                        // For now, let's treat it as text but handle newlines as <br> if needed?
                        // Actually, LLM sends \n. 
                        // Let's use marked.js if available? No, user didn't ask for markdown library.
                        // We will just replace \n with <br> and bolding if simple.
                        // But wait, the previous implementation used simple innerHTML assignment.
                        // We will accumulate text and regex-replace basic markdown.

                        fullResponse += data.content;
                        msgTextContainer.innerHTML = formatMarkdown(fullResponse);
                        chatHistory.scrollTop = chatHistory.scrollHeight;

                    } else if (data.type === 'action') {
                        handleAction({ action_required: data.data.action_required, payload: data.data.payload }, botMsgDiv);
                    } else if (data.type === 'error') {
                        msgTextContainer.textContent = data.content;
                    }

                } catch (e) {
                    console.error("Stream Parse Error", e);
                }
            }
        }
        lucide.createIcons();

    } catch (err) {
        msgTextContainer.innerHTML = "Erreur de connexion.";
        msgTextContainer.classList.add('error');
    }
}

function formatMarkdown(text) {
    // Simple markdown formatter
    let html = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') // Bold
        .replace(/- /g, '&bull; '); // Bullets
    return html;
}


const micBtn = document.getElementById('mic-btn');
let recognition;
let isRecording = false;
let silenceTimer;
const SILENCE_DELAY = 2000; // 2 seconds

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = true; // Changed to true
    recognition.lang = 'fr-FR';
    recognition.interimResults = true; // Changed to true

    recognition.onstart = function () {
        isRecording = true;
        micBtn.classList.add('listening');
    };

    recognition.onend = function () {
        isRecording = false;
        micBtn.classList.remove('listening');
        clearTimeout(silenceTimer);

        // Auto-send if there is text and it was a voice session
        if (chatInput.value.trim() !== '') {
            sendMessage();
        }
    };

    recognition.onresult = function (event) {
        clearTimeout(silenceTimer);
        let finalTranscript = '';

        // Build transcript from results
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            } else {
                finalTranscript += event.results[i][0].transcript;
            }
        }

        // Only update if we have something (simplified for single input)
        // Ideally we would want to append to existing text, but for this use case 
        // managing cursor position and previous text vs new voice text can be complex.
        // We will just set the value to what is being spoken for this session.
        // Or better: Append to what was there before recording started? 
        // Let's keep it simple: overwrite or append? 
        // The user wants "le texte se remplit". 
        // With continuous=true, we get accumulated results in the session.
        // We'll trust the latest result is the accumulator for this session.

        // Actually, simplest way for 'continuous' is often just handling the latest result
        // But let's stick to this robust loop pattern.

        // Note: For a simple command field, we might just want to set the value.
        // But let's check if we want to preserve previous text. 
        // User request implies dictation.

        // Allow user to edit while speaking? Maybe not.

        // Let's just set the input to the current transcript of this session
        // We'll reset chatInput.value = ...

        // IMPORTANT: webkitSpeechRecognition behavior:
        // results contains all results for the session if continuous=true
        let interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            interimTranscript += event.results[i][0].transcript;
        }

        // To avoid complexity, we will just APPEND or SET?
        // Let's just SET for now as it's a "voice command" style.
        // If user typed something before, it might be lost if we aren't careful.
        // But usually voice button = fresh input.

        // Let's use a simpler approach for the specific request: 
        // Just put what is recognized into the box.
        chatInput.value = interimTranscript;
        chatInput.focus();

        // Set silence timer
        silenceTimer = setTimeout(() => {
            recognition.stop();
        }, SILENCE_DELAY);
    };

    recognition.onerror = function (event) {
        console.error("Speech recognition error", event.error);
        isRecording = false;
        micBtn.classList.remove('listening');
        clearTimeout(silenceTimer);
    };
} else {
    if (micBtn) micBtn.style.display = 'none';
}

if (micBtn) {
    micBtn.onclick = () => {
        if (!recognition) return;
        if (isRecording) {
            clearTimeout(silenceTimer);
            recognition.stop();
        } else {
            chatInput.value = ''; // Clear previous input on new start
            recognition.start();
        }
    };
}


if (sendBtn) sendBtn.onclick = sendMessage;
if (chatInput) chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };


// --- ADMIN LOGIC ---

function switchAdminTab(tab) {
    // Buttons
    document.querySelectorAll('.admin-tab-btn').forEach(btn => btn.classList.remove('active'));
    // Matching button
    const btns = document.querySelectorAll('.admin-tab-btn');
    if (tab === 'users') btns[0].classList.add('active');
    if (tab === 'rooms') btns[1].classList.add('active');

    // Views
    document.getElementById('admin-users-view').style.display = tab === 'users' ? 'block' : 'none';
    document.getElementById('admin-rooms-view').style.display = tab === 'rooms' ? 'block' : 'none';

    // Load data
    if (tab === 'users') loadUsers();
    if (tab === 'rooms') loadRooms();
}

// USERS CRUD
async function loadUsers() {
    const list = document.getElementById('admin-users-list');
    list.innerHTML = '<tr><td colspan="4">Chargement...</td></tr>';

    try {
        const res = await fetch(`${API_BASE}/admin/users`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const users = await res.json();
        list.innerHTML = '';
        users.forEach(u => {
            list.innerHTML += `
                <tr>
                    <td>${u.username}</td>
                    <td><span class="badge ${u.role}">${u.role}</span></td>
                    <td class="action-cell">
                        <button class="btn-icon btn-edit" onclick="editUser(${u.id})"><i data-lucide="edit-2"></i></button>
                        <button class="btn-icon btn-delete-sm" onclick="deleteUser(${u.id})"><i data-lucide="trash-2"></i></button>
                    </td>
                </tr>
            `;
        });
        lucide.createIcons();
    } catch (e) {
        list.innerHTML = '<tr><td colspan="4">Erreur chargement</td></tr>';
    }
}

function openUserModal(user = null) {
    const modal = document.getElementById('user-modal');
    modal.classList.add('active');
    document.getElementById('user-form').reset();
    if (user) {
        document.getElementById('user-id').value = user.id;
        document.getElementById('user-username').value = user.username;
        document.getElementById('user-email').value = user.email;
        document.getElementById('user-role').value = user.role;
    } else {
        document.getElementById('user-id').value = '';
    }
}

function closeUserModal() {
    document.getElementById('user-modal').classList.remove('active');
}

async function editUser(id) {
    const res = await fetch(`${API_BASE}/admin/users`, { headers: { 'Authorization': `Bearer ${token}` } });
    const users = await res.json();
    const user = users.find(u => u.id === id);
    if (user) openUserModal(user);
}

window.handleUserSubmit = async function (e) {
    e.preventDefault();
    try {
        const id = document.getElementById('user-id').value;
        const username = document.getElementById('user-username').value;
        const email = document.getElementById('user-email').value;
        const password = document.getElementById('user-password').value;
        const role = document.getElementById('user-role').value;

        console.log("Submitting User:", { id, username, email, role }); // Debug

        if (!id && !password) {
            alert("Le mot de passe est obligatoire pour un nouvel utilisateur.");
            return;
        }

        const url = id ? (`${API_BASE}/admin/users/${id}`) : (`${API_BASE}/admin/users`);
        const method = id ? 'PUT' : 'POST';

        const body = { username, email, role };
        if (password) body.password = password;

        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
            closeUserModal();
            loadUsers();
        } else {
            alert("Erreur: " + (data.message || "Impossible d'enregistrer"));
        }
    } catch (err) {
        console.error(err);
        alert("Erreur JS: " + err.message);
    }
}

async function deleteUser(id) {
    // No confirmation
    await fetch(`${API_BASE}/admin/users/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    loadUsers();
}


// ROOMS CRUD
async function loadRooms() {
    const list = document.getElementById('admin-rooms-list');
    list.innerHTML = '<tr><td colspan="4">Chargement...</td></tr>';

    try {
        const res = await fetch(`${API_BASE}/admin/rooms`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const rooms = await res.json();
        list.innerHTML = '';
        rooms.forEach(r => {
            list.innerHTML += `
                <tr>
                    <td>${r.name}</td>
                    <td>${r.capacity}p</td>
                    <td><span class="text-sm text-muted">${Array.isArray(r.equipment) ? r.equipment.join(', ') : ''}</span></td>
                    <td class="action-cell">
                        <button class="btn-icon btn-edit" onclick="editRoom(${r.id})"><i data-lucide="edit-2"></i></button>
                        <button class="btn-icon btn-delete-sm" onclick="deleteRoom(${r.id})"><i data-lucide="trash-2"></i></button>
                    </td>
                </tr>
            `;
        });
        lucide.createIcons();
    } catch (e) {
        list.innerHTML = '<tr><td colspan="4">Erreur chargement</td></tr>';
    }
}

function openRoomModal(room = null) {
    const modal = document.getElementById('room-modal');
    modal.classList.add('active');
    document.getElementById('room-form').reset();
    if (room) {
        document.getElementById('room-id').value = room.id;
        document.getElementById('room-name').value = room.name;
        document.getElementById('room-capacity').value = room.capacity;
        document.getElementById('room-equipment').value = Array.isArray(room.equipment) ? room.equipment.join(', ') : '';
    } else {
        document.getElementById('room-id').value = '';
    }
}

function closeRoomModal() {
    document.getElementById('room-modal').classList.remove('active');
}

async function editRoom(id) {
    const res = await fetch(`${API_BASE}/admin/rooms`, { headers: { 'Authorization': `Bearer ${token}` } });
    const rooms = await res.json();
    const room = rooms.find(r => r.id === id);
    if (room) openRoomModal(room);
}

async function handleRoomSubmit(e) {
    e.preventDefault();
    const id = document.getElementById('room-id').value;
    const name = document.getElementById('room-name').value;
    const capacity = document.getElementById('room-capacity').value;
    const eqStr = document.getElementById('room-equipment').value;

    // Parse equipment
    const equipment = eqStr.split(',').map(s => s.trim()).filter(s => s !== '');

    const url = id ? (`${API_BASE}/admin/rooms/${id}`) : (`${API_BASE}/admin/rooms`);
    const method = id ? 'PUT' : 'POST';

    const body = { name, capacity: parseInt(capacity), equipment, is_active: true }; // Always active

    await fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(body)
    });

    closeRoomModal();
    loadRooms();
}

async function deleteRoom(id) {
    // No confirmation
    const res = await fetch(`${API_BASE}/admin/rooms/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    loadRooms();
}

function handleAction(data, targetElement = null) {
    const container = targetElement ? targetElement.querySelector('.text') : chatHistory.lastElementChild.querySelector('.text');
    const btn = document.createElement('button');
    btn.className = 'btn-primary';
    btn.style.marginTop = '0.5rem';
    btn.style.fontSize = '0.9rem';
    btn.style.padding = '0.5rem 1rem';

    if (data.action_required === 'confirm_booking') {
        btn.innerHTML = '<i data-lucide="check"></i> Confirmer';
        btn.onclick = () => confirmBooking(data.payload);
    } else if (data.action_required === 'confirm_modification') {
        btn.innerHTML = '<i data-lucide="check"></i> Confirmer Modification';
        btn.onclick = () => confirmModification(data.payload);
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
        // Update context instead of clearing
        fetch(`${API_BASE}/chat/context/last_booking`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ booking_id: data.id })
        });
    } else {
        addMessage(`❌ Erreur: ${data.error}`, 'bot');
    }
}

async function confirmModification(payload) {
    addMessage("Confirmation modification...", 'user');
    const res = await fetch(`${API_BASE}/bookings/${payload.booking_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
        addMessage(`✅ Réservation modifiée ! ID: ${data.id}`, 'bot');
        loadBookings();
        // Update context
        fetch(`${API_BASE}/chat/context/last_booking`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({ booking_id: data.id })
        });
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
            const start = new Date(b.start_time);
            const end = new Date(b.end_time);
            const now = new Date();

            // Format start time
            const startStr = start.toLocaleString('fr-FR', { weekday: 'short', hour: '2-digit', minute: '2-digit' });

            // Calculate duration
            const diffMs = end - start;
            const diffMins = Math.round(diffMs / 60000);
            let durationStr = '';
            if (diffMins >= 60) {
                const h = Math.floor(diffMins / 60);
                const m = diffMins % 60;
                durationStr = `${h}h ${m > 0 ? m + 'm' : ''}`;
            } else {
                durationStr = `${diffMins} min`;
            }

            // Check in-progress
            const isInProgress = now >= start && now <= end;
            const activeClass = isInProgress ? 'in-progress' : '';
            const statusLabel = isInProgress ? '<span class="status-badge">En cours</span>' : '';

            const li = document.createElement('li');
            li.className = `booking-item ${activeClass}`;
            li.innerHTML = `
                <div class="booking-details">
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span class="booking-time">${startStr}</span>
                        ${statusLabel}
                    </div>
                    <span class="booking-meta">
                        <i data-lucide="map-pin" class="icon-xs"></i> ${b.room_name} 
                        &nbsp;&bull;&nbsp; <i data-lucide="clock" class="icon-xs"></i> ${durationStr}
                    </span>
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

