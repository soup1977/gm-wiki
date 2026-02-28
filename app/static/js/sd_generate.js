/**
 * sd_generate.js — Stable Diffusion image generation from entity forms
 *
 * Usage: Add a button with onclick="sdGenerate('npc')" and the following
 * elements in the form:
 *   - #sd-preview-img        — <img> element for preview (hidden by default)
 *   - #sd-generated-filename — <input type="hidden" name="sd_generated_filename">
 *   - #sd-generate-btn       — the generate button itself
 *   - #sd-generate-result    — <div> for error messages
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
        if (desc) parts.push(desc.substring(0, 200));
        return parts.join(', ');
    },
    location: function() {
        const name = document.getElementById('name')?.value || '';
        const type = document.getElementById('type')?.value || '';
        const desc = document.getElementById('description')?.value || '';
        const parts = ['fantasy landscape', 'detailed environment'];
        if (name) parts.push(name);
        if (type) parts.push(type);
        if (desc) parts.push(desc.substring(0, 200));
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
        if (desc) parts.push(desc.substring(0, 200));
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
        if (desc) parts.push(desc.substring(0, 200));
        return parts.join(', ');
    }
};

let sdElapsedTimer = null;

function sdGenerate(entityType) {
    const btn = document.getElementById('sd-generate-btn');
    const resultEl = document.getElementById('sd-generate-result');
    const previewImg = document.getElementById('sd-preview-img');
    const filenameInput = document.getElementById('sd-generated-filename');

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
            // Show preview
            previewImg.src = data.url;
            previewImg.style.display = 'block';
            previewImg.parentElement.style.display = 'block';
            // Set hidden filename so the form save picks it up
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
