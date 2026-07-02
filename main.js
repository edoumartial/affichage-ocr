const API_URL = "http://localhost:8000";
const SUFFIXE_CASO = "/ANUTTC/DG/DC/SC";
// Liste des champs mise à jour selon votre nouvelle structure
const champs = ["lettre_date", "requerant", "parcelle", "section", "commune", "lieu_dit"];
let tousLesDocs = [];
let triAsc = true;
let userRole = "";

function getToken() { return localStorage.getItem('token'); }

function initUserSession() {
    const token = getToken();
    if (!token) { window.location.href = 'login.html'; return; }
    try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        document.getElementById('userDisplay').innerText = payload.sub;
        userRole = payload.role || 'Utilisateur';
        document.getElementById('roleDisplay').innerText = userRole;
        const btnUsers = document.getElementById('btnGestionUsers');
        if (userRole.toLowerCase().includes('admin')) {
            btnUsers.classList.remove('hidden');
        } else {
            btnUsers.classList.add('hidden');
        }
    } catch (e) { deconnexion(); }
}

function deconnexion() { localStorage.removeItem('token'); window.location.href = 'login.html'; }

function formaterDateTime(isoString) {
    if (!isoString) return "N/A";
    const date = new Date(isoString);
    const d = String(date.getDate()).padStart(2, '0');
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const y = date.getFullYear();
    const hh = String(date.getHours()).padStart(2, '0');
    const mm = String(date.getMinutes()).padStart(2, '0');
    const ss = String(date.getSeconds()).padStart(2, '0');
    return `${d}/${m}/${y} ${hh}:${mm}:${ss}`;
}

async function chargerDonnees() {
    try {
        const res = await fetch(`${API_URL}/tous-les-documents/`, { headers: { 'Authorization': 'Bearer ' + getToken() }});
        tousLesDocs = await res.json();
        majStats();
        afficherTableau(tousLesDocs);
    } catch(e) { console.error(e); }
}

function majStats() {
    document.getElementById('statTotal').innerText = tousLesDocs.length;
    document.getElementById('statAttente').innerText = tousLesDocs.filter(d => d.statut === 'en_attente').length;
    document.getElementById('statValide').innerText = tousLesDocs.filter(d => d.statut === 'valide').length;
}


// Dans main.js
function afficherTableau(data) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = data.map(doc => `
        <tr class="border-b hover:bg-slate-50">
            <td class="p-3">${doc.lettre_date || ''}</td>
            <td class="p-3">${doc.requerant || ''}</td>
            <td class="p-3">${doc.commune || ''}</td>
            <td class="p-3">${doc.parcelle || ''}</td>
            <td class="p-3">${doc.section || ''}</td>
            <td class="p-3">${doc.lieu_dit || ''}</td>
            <td class="p-3">${doc.created_at ? formaterDateTime(doc.created_at) : 'N/A'}</td>
            <td class="p-3">
                <span class="px-2 py-1 rounded text-[10px] ${doc.statut === 'valide' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">
                    ${doc.statut || 'en_attente'}
                </span>
            </td>
            <td class="p-3">
                <button onclick="editerDoc(${doc.id})" class="text-blue-600 font-bold hover:underline">Éditer</button>
            </td>
        </tr>
    `).join('');
}



function trierPar(col) {
    triAsc = !triAsc;
    const data = [...tousLesDocs].sort((a, b) => {
        const valA = (a[col] || '').toLowerCase();
        const valB = (b[col] || '').toLowerCase();
        return triAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    });
    afficherTableau(data);
}

function filtrerStatut(statut) {
    if (statut === 'tous') return afficherTableau(tousLesDocs);
    afficherTableau(tousLesDocs.filter(d => d.statut === statut));
}

function appliquerFiltres() {
    const texte = document.getElementById('searchInput').value.toLowerCase();
    const data = tousLesDocs.filter(d => Object.values(d).some(val => String(val).toLowerCase().includes(texte)));
    afficherTableau(data);
}

async function uploaderFichiers() {
    const fileInput = document.getElementById('fileInput');
    const statusDiv = document.getElementById('uploadStatus');
    if (fileInput.files.length === 0) return alert("Sélectionnez des fichiers.");
    const formData = new FormData();
    for (const file of fileInput.files) formData.append('files', file);
    statusDiv.innerHTML = `<span class="animate-pulse">Traitement OCR...</span>`;
    try {
        const res = await fetch(`${API_URL}/upload-multiple/`, { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() }, body: formData });
        if (res.ok) { statusDiv.innerHTML = "Terminé. <span class='cursor-pointer underline' onclick='chargerDonnees()'>Rafraîchir</span>"; fileInput.value = ''; }
    } catch(e) { statusDiv.innerText = "Erreur."; }
}

function editerDoc(id) {
    const doc = tousLesDocs.find(d => d.id === id);
    if (!doc) return;
    
    document.getElementById('vueTableau').classList.add('hidden');
    document.getElementById('vueEdition').classList.remove('hidden');
    document.getElementById('pdfViewer').src = `${API_URL}/static/${doc.filename}`;
    document.getElementById('currentCasoId').value = doc.id;
    
    // Décodage du validateur
    try {
        const token = getToken();
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        const validateurInput = document.getElementById('validateurInput');
        if (validateurInput) validateurInput.value = payload.sub;
    } catch (e) { console.error("Erreur de décodage du token", e); }
    
    // Liste des champs visibles (champs "Upload" et "OCR" retirés de l'affichage)
    const champs = ["numero_affichage", "lettre_date", "requerant", "parcelle", "section", "commune", "lieu_dit"];
    
    // Génération du HTML
    let html = champs.map(col => {
        let label = col.replace('_', ' ');
        if (col === 'numero_affichage') label = "N° Affichage";
        if (col === 'lettre_date') label = "Date Lettre";

        if (col === 'commune') {
            return `
                <div class="mb-3">
                    <label class="block text-xs font-bold uppercase">${label}</label>
                    <input type="text" name="${col}" value="${doc[col] || ''}" list="listeCommunes" class="w-full p-2 border rounded shadow-sm" autocomplete="off">
                </div>`;
        }
        
        return `
            <div class="mb-3">
                <label class="block text-xs font-bold uppercase">${label}</label>
                <input type="text" name="${col}" value="${doc[col] || ''}" class="w-full p-2 border rounded shadow-sm">
            </div>`;
    }).join('');

    // AJOUT : Ajout du champ caché pour conserver l'extraction_ocr lors de la soumission
    html += `<input type="hidden" name="extraction_ocr" value="${doc.extraction_ocr || ''}">`;

    document.getElementById('fieldsContainer').innerHTML = html;
}

function retourTableau() {
    document.getElementById('vueTableau').classList.remove('hidden');
    document.getElementById('vueEdition').classList.add('hidden');
    document.getElementById('vueUsers').classList.add('hidden');
}

document.getElementById('validationForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    // Ajustez ici si vous avez toujours besoin de suffixer le N° CASO
    const res = await fetch(`${API_URL}/valider-document/${formData.get('caso_id')}`, { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() }, body: formData });
    if (res.ok) { retourTableau(); await chargerDonnees(); } else alert("Erreur validation");
});

function ouvrirVueUsers() {
    document.getElementById('vueTableau').classList.add('hidden');
    document.getElementById('vueEdition').classList.add('hidden');
    document.getElementById('vueUsers').classList.remove('hidden');
    chargerUsers();
}

async function chargerUsers() {
    const res = await fetch(`${API_URL}/users/`, { headers: { 'Authorization': 'Bearer ' + getToken() } });
    const users = await res.json();
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = users.map(u => `
        <tr class="border-b"><td class="p-3">${u.username}</td><td class="p-3">${u.role}</td><td class="p-3">${u.is_active ? 'Actif' : 'Inactif'}</td><td class="p-3"><button onclick="preparerModification(${u.id}, '${u.username}')" class="text-blue-600 font-bold mr-2 hover:underline">Modifier</button><button onclick="supprimerUser(${u.id})" class="text-red-600 font-bold hover:underline">Supprimer</button></td></tr>
    `).join('');
}

function preparerModification(id, oldUsername) {
    const newUsername = prompt("Nouveau username :", oldUsername);
    if (newUsername === null) return;
    const newPassword = prompt("Nouveau mot de passe (laisser vide pour ne pas changer) :");
    modifierUser(id, newUsername, newPassword);
}

async function modifierUser(id, newUsername, newPassword) {
    const payload = { username: newUsername };
    if (newPassword) payload.password = newPassword;
    const res = await fetch(`${API_URL}/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
        body: JSON.stringify(payload)
    });
    if (res.ok) chargerUsers(); else alert("Erreur lors de la modification.");
}

async function supprimerUser(id) {
    if (!confirm("Voulez-vous vraiment supprimer cet utilisateur ?")) return;
    const res = await fetch(`${API_URL}/users/${id}`, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + getToken() } });
    if (res.ok) chargerUsers(); else alert("Erreur lors de la suppression.");
}

document.getElementById('formAjoutUser').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const res = await fetch(`${API_URL}/users/`, { method: 'POST', headers: { 'Authorization': 'Bearer ' + getToken() }, body: formData });
    if (res.ok) { e.target.reset(); chargerUsers(); } else alert("Erreur lors de la création.");
});

initUserSession();
chargerDonnees();