// ===== DOM ELEMENTS =====
const knowledgeForm = document.getElementById('knowledgeForm');
const editForm = document.getElementById('editForm');
const knowledgeList = document.getElementById('knowledgeList');
const successMsg = document.getElementById('successMsg');
const errorMsg = document.getElementById('errorMsg');
const uploadSuccessMsg = document.getElementById('uploadSuccessMsg');
const uploadErrorMsg = document.getElementById('uploadErrorMsg');
const csvFileInput = document.getElementById('csvFile');
const uploadBtn = document.getElementById('uploadBtn');
const fileName = document.getElementById('fileName');
const progressInfo = document.getElementById('progressInfo');

let deleteId = null;

// ===== AUTHENTICATION CHECK =====
function checkAuthentication(response) {
    // If we get redirected to login page (HTML instead of JSON), redirect user
    if (response.redirected && response.url.includes('/admin/login')) {
        window.location.href = '/admin/login';
        return false;
    }
    return true;
}

// ===== CSV UPLOAD FUNCTIONALITY =====

// Enable upload button when file is selected
csvFileInput.addEventListener('change', function(e) {
    if (e.target.files.length > 0) {
        fileName.textContent = e.target.files[0].name;
        uploadBtn.disabled = false;
    } else {
        fileName.textContent = 'No file selected';
        uploadBtn.disabled = true;
    }
});

// Handle CSV file upload
uploadBtn.addEventListener('click', async function() {
    const file = csvFileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Uploading...';
    progressInfo.style.display = 'block';

    try {
        const response = await fetch('/upload_csv', {
            method: 'POST',
            body: formData,
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        const result = await response.json();

        if (response.ok) {
            showUploadMessage(uploadSuccessMsg, 
                `✓ Successfully imported ${result.added} entries! ${result.skipped > 0 ? `Skipped ${result.skipped} rows.` : ''}`);
            
            if (result.errors && result.errors.length > 0) {
                console.log('Upload errors:', result.errors);
            }
            
            // Reset form
            csvFileInput.value = '';
            fileName.textContent = 'No file selected';
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Upload & Import';
            
            // Refresh knowledge list and stats
            loadKnowledge();
            updateStats();
        } else {
            showUploadMessage(uploadErrorMsg, '✗ Upload failed: ' + result.error);
            uploadBtn.textContent = 'Upload & Import';
        }
    } catch (error) {
        showUploadMessage(uploadErrorMsg, '✗ Connection error: ' + error.message);
        uploadBtn.textContent = 'Upload & Import';
    } finally {
        progressInfo.style.display = 'none';
        uploadBtn.disabled = false;
    }
});

// ===== MESSAGE DISPLAY FUNCTIONS =====

function showMessage(element, message) {
    element.textContent = message;
    element.style.display = 'block';
    setTimeout(() => {
        element.style.display = 'none';
    }, 3000);
}

function showUploadMessage(element, message) {
    element.textContent = message;
    element.style.display = 'block';
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

// ===== ADD KNOWLEDGE FORM =====

knowledgeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        category: document.getElementById('category').value,
        question: document.getElementById('question').value,
        answer: document.getElementById('answer').value,
        source: document.getElementById('source').value
    };

    try {
        const response = await fetch('/add_knowledge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        if (response.ok) {
            showMessage(successMsg, '✓ Knowledge added successfully!');
            knowledgeForm.reset();
            loadKnowledge();
            updateStats();
        } else {
            showMessage(errorMsg, '✗ Error adding knowledge. Please try again.');
        }
    } catch (error) {
        showMessage(errorMsg, '✗ Connection error: ' + error.message);
    }
});

// ===== LOAD AND DISPLAY KNOWLEDGE =====

async function loadKnowledge() {
    try {
        const response = await fetch('/get_knowledge', {
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            // If we get HTML instead of JSON, we're probably not authenticated
            window.location.href = '/admin/login';
            return;
        }

        const knowledge = await response.json();

        if (knowledge.length === 0) {
            knowledgeList.innerHTML = '<p style="text-align: center; color: #666; padding: 40px;">No knowledge entries yet. Add some using the form!</p>';
            return;
        }

        knowledgeList.innerHTML = knowledge.map(item => `
            <div class="knowledge-item">
                <div class="action-buttons">
                    <button class="action-btn edit-btn" onclick="openEditModal(${item.id})" title="Edit">✏️</button>
                    <button class="action-btn delete-btn" onclick="openDeleteModal(${item.id})" title="Delete">🗑️</button>
                </div>
                <div class="category-badge">${item.category}</div>
                <div><strong>Q:</strong> ${item.question}</div>
                <div style="margin-top: 8px;"><strong>A:</strong> ${item.answer}</div>
                <div style="margin-top: 8px; font-size: 12px; color: #666;">
                    <strong>Source:</strong> ${item.source} | 
                    <strong>Added:</strong> ${new Date(item.created_at).toLocaleDateString()}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading knowledge:', error);
        knowledgeList.innerHTML = '<p style="text-align: center; color: red; padding: 40px;">Error loading knowledge. Please refresh the page.</p>';
    }
}

// ===== UPDATE STATISTICS =====

async function updateStats() {
    try {
        const response = await fetch('/get_knowledge', {
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            // If we get HTML instead of JSON, we're probably not authenticated
            return;
        }

        const knowledge = await response.json();
        
        document.getElementById('totalKnowledge').textContent = knowledge.length;
        
        const categories = new Set(knowledge.map(item => item.category));
        document.getElementById('totalCategories').textContent = categories.size;
    } catch (error) {
        console.error('Error updating stats:', error);
        // Don't show error to user, just log it
    }
}

// ===== EDIT MODAL FUNCTIONS =====

async function openEditModal(id) {
    try {
        const response = await fetch('/get_knowledge', {
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        const knowledge = await response.json();
        const item = knowledge.find(k => k.id === id);
        
        if (item) {
            document.getElementById('editId').value = item.id;
            document.getElementById('editCategory').value = item.category;
            document.getElementById('editQuestion').value = item.question;
            document.getElementById('editAnswer').value = item.answer;
            document.getElementById('editSource').value = item.source;
            document.getElementById('editModal').style.display = 'block';
        }
    } catch (error) {
        alert('Error loading entry: ' + error.message);
    }
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

editForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const id = document.getElementById('editId').value;
    const data = {
        id: parseInt(id),
        category: document.getElementById('editCategory').value,
        question: document.getElementById('editQuestion').value,
        answer: document.getElementById('editAnswer').value,
        source: document.getElementById('editSource').value
    };

    try {
        const response = await fetch(`/update_knowledge/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        if (response.ok) {
            closeEditModal();
            showMessage(successMsg, '✓ Knowledge updated successfully!');
            loadKnowledge();
            updateStats();
        } else {
            alert('Error updating knowledge. Please try again.');
        }
    } catch (error) {
        alert('Connection error: ' + error.message);
    }
});

// ===== DELETE MODAL FUNCTIONS =====

function openDeleteModal(id) {
    deleteId = id;
    document.getElementById('deleteModal').style.display = 'block';
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    deleteId = null;
}

async function confirmDelete() {
    if (!deleteId) return;

    try {
        const response = await fetch(`/delete_knowledge/${deleteId}`, {
            method: 'DELETE',
            credentials: 'same-origin' // Include session cookies
        });

        // Check authentication
        if (!checkAuthentication(response)) return;

        if (response.ok) {
            closeDeleteModal();
            showMessage(successMsg, '✓ Knowledge deleted successfully!');
            loadKnowledge();
            updateStats();
        } else {
            alert('Error deleting knowledge. Please try again.');
        }
    } catch (error) {
        alert('Connection error: ' + error.message);
    }
}

// ===== TAB SWITCHING =====

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    if (tab === 'add') {
        document.querySelector('.tab:nth-child(1)').classList.add('active');
        document.getElementById('addTab').classList.add('active');
    } else if (tab === 'upload') {
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        document.getElementById('uploadTab').classList.add('active');
    } else {
        document.querySelector('.tab:nth-child(3)').classList.add('active');
        document.getElementById('viewTab').classList.add('active');
        loadKnowledge();
    }
}

// ===== MODAL OUTSIDE CLICK HANDLER =====

window.onclick = function(event) {
    const editModal = document.getElementById('editModal');
    const deleteModal = document.getElementById('deleteModal');
    if (event.target === editModal) {
        closeEditModal();
    }
    if (event.target === deleteModal) {
        closeDeleteModal();
    }
}

// ===== INITIALIZE ON PAGE LOAD =====

loadKnowledge();
updateStats();