/**
 * sd_generate.js — Stable Diffusion image generation from entity forms
 *
 * Usage: Add a button with onclick="sdGenerate('npc', event)" and the following
 * elements in the form:
 *   - #sd-preview-img        — <img> element for preview (hidden by default)
 *   - #sd-generated-filename — <input type="hidden" name="sd_generated_filename">
 *   - #sd-generate-btn       — the generate button itself
 *   - #sd-generate-result    — <div> for error messages
 *
 * Shift+click the Generate Image button to edit the prompt before sending.
 */

// Status messages for image generation
const SD_STATUS_MESSAGES = [
    { after: 0,  text: 'Sending to Stable Diffusion...' },
    { after: 5,  text: 'Rendering image...' },
    { after: 15, text: 'Still rendering — images can take a minute...' },
    { after: 30, text: 'Almost there — hang tight...' },
    { after: 60, text: 'Still processing — high-res images take longer...' },
];

// Prompt builders per entity type — reads form fields and returns a prompt string
const SD_PROMPT_BUILDERS = {
    npc: function() {
        const name = document.getElementById('name')?.value || '';
        const role = document.getElementById('role')?.value || '';
        const desc = document.getElementById('physical_description')?.value || '';
        const parts = ['fantasy portrait', 'detailed face'];
        if (name) parts.push(name);
        if (role) parts.push(role);
        if (desc) parts.push(desc);
        return parts.join(', ');
    },
    location: function() {
        const name = document.getElementById('name')?.value || '';
        const type = document.getElementById('type')?.value || '';
        const desc = document.getElementById('description')?.value || '';
        const parts = ['fantasy landscape', 'detailed environment'];
        if (name) parts.push(name);
        if (type) parts.push(type);
        if (desc) parts.push(desc);
        return parts.join(', ');
    },
    bestiary: function() {
        const name = document.getElementById('name')?.value || '';
        const system = document.getElementById('system')?.value || '';
        const parts = ['fantasy creature', 'detailed illustration'];
        if (name) parts.push(name);
        if (system) parts.push(system + ' style');
        return parts.join(', ');
    },
    item: function() {
        const name = document.getElementById('name')?.value || '';
        const type = document.getElementById('type')?.value || '';
        const desc = document.getElementById('description')?.value || '';
        const parts = ['fantasy item illustration', 'detailed object'];
        if (name) parts.push(name);
        if (type) parts.push(type);
        if (desc) parts.push(desc);
        return parts.join(', ');
    },
    pc: function() {
        const race = document.getElementById('race_or_ancestry')?.value || '';
        const cls = document.getElementById('class_or_role')?.value || '';
        const name = document.getElementById('character_name')?.value || '';
        const desc = document.getElementById('description')?.value || '';
        const parts = ['fantasy character portrait', 'detailed face'];
        if (race) parts.push(race);
        if (cls) parts.push(cls);
        if (name) parts.push(name);
        if (desc) parts.push(desc);
        return parts.join(', ');
    }
};

let sdElapsedTimer = null;

// ---------------------------------------------------------------------------
// Inject the prompt editor modal (for shift+click)
// ---------------------------------------------------------------------------
(function () {
    const modalHtml = `
    <div class="modal fade" id="sdPromptEditModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg">
            <div class="modal-content bg-dark border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title">
                        <i class="bi bi-pencil-square"></i> Edit Image Prompt
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted small mb-2">
                        This prompt was auto-built from the form fields. Edit it to fine-tune the image, then click Generate.
                    </p>
                    <textarea id="sd-prompt-edit-text" class="form-control bg-dark border-secondary text-light"
                              rows="5"></textarea>
                </div>
                <div class="modal-footer border-secondary">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="sd-prompt-edit-submit">
                        <i class="bi bi-image"></i> Generate
                    </button>
                </div>
            </div>
        </div>
    </div>`;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
})();

// Store current entity type for the modal submit handler
let _sdPromptEditEntityType = null;

// Modal submit handler — sends the edited prompt
document.getElementById('sd-prompt-edit-submit').addEventListener('click', function () {
    const modal = bootstrap.Modal.getInstance(document.getElementById('sdPromptEditModal'));
    const editedPrompt = document.getElementById('sd-prompt-edit-text').value.trim();
    if (!editedPrompt) return;
    modal.hide();
    _sdSendRequest(editedPrompt);
});

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------
function sdGenerate(entityType, event) {
    const btn = document.getElementById('sd-generate-btn');
    const resultEl = document.getElementById('sd-generate-result');

    // Build prompt from form fields
    const builder = SD_PROMPT_BUILDERS[entityType];
    if (!builder) {
        resultEl.innerHTML = '<span class="text-danger">Unknown entity type.</span>';
        return;
    }

    const prompt = builder();
    if (prompt.length < 10) {
        resultEl.innerHTML = '<span class="text-warning">Fill in some fields first (name, description, etc.) so the AI knows what to draw.</span>';
        return;
    }

    _sdPromptEditEntityType = entityType;

    // Shift+click: show prompt editor modal
    if (event && event.shiftKey) {
        document.getElementById('sd-prompt-edit-text').value = prompt;
        new bootstrap.Modal(document.getElementById('sdPromptEditModal')).show();
        return;
    }

    // Normal click: send immediately
    _sdSendRequest(prompt);
}

// ---------------------------------------------------------------------------
// Send the SD request (shared by normal click and prompt editor)
// ---------------------------------------------------------------------------
function _sdSendRequest(prompt) {
    const btn = document.getElementById('sd-generate-btn');
    const resultEl = document.getElementById('sd-generate-result');
    const previewImg = document.getElementById('sd-preview-img');
    const filenameInput = document.getElementById('sd-generated-filename');

    // Show spinner with status updates
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Generating…';

    const startTime = Date.now();
    resultEl.innerHTML = '<span class="text-muted small"><span class="spinner-border spinner-border-sm me-1"></span> <span id="sd-status-text">' + SD_STATUS_MESSAGES[0].text + '</span> <span id="sd-elapsed" class="ms-2 text-secondary">0:00</span></span>';

    sdElapsedTimer = setInterval(function () {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const mins = Math.floor(elapsed / 60);
        const secs = elapsed % 60;
        const elapsedEl = document.getElementById('sd-elapsed');
        const statusEl = document.getElementById('sd-status-text');
        if (elapsedEl) elapsedEl.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;

        if (statusEl) {
            for (let i = SD_STATUS_MESSAGES.length - 1; i >= 0; i--) {
                if (elapsed >= SD_STATUS_MESSAGES[i].after) {
                    statusEl.textContent = SD_STATUS_MESSAGES[i].text;
                    break;
                }
            }
        }
    }, 1000);

    fetch('/api/sd/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            prompt: prompt,
            negative_prompt: ''
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            previewImg.src = data.url;
            previewImg.style.display = 'block';
            previewImg.parentElement.style.display = 'block';
            filenameInput.value = data.filename;
            resultEl.innerHTML = '<span class="text-success"><i class="bi bi-check-circle"></i> Image generated! It will be saved when you submit the form.</span>';
        } else {
            resultEl.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle"></i> ' + (data.error || 'Unknown error') + '</span>';
        }
    })
    .catch(err => {
        resultEl.innerHTML = '<span class="text-danger">Request failed: ' + err.message + '</span>';
    })
    .finally(() => {
        if (sdElapsedTimer) { clearInterval(sdElapsedTimer); sdElapsedTimer = null; }
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-image"></i> Generate Image';
    });
}
