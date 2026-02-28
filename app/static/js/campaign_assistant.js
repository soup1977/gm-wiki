/**
 * campaign_assistant.js — Campaign Assistant chat UI
 *
 * Handles:
 *  - Sending user messages to /api/ai/assistant
 *  - Rendering assistant replies (prose + entity cards)
 *  - Saving AI-generated entities via /api/ai/assistant/save-entity
 *  - Clearing chat history via /api/ai/assistant/clear
 */

(function () {
    'use strict';

    const cfg = window.ASSISTANT_CONFIG || {};

    // DOM refs
    const messagesEl = document.getElementById('chat-messages');
    const inputEl    = document.getElementById('chat-input');
    const sendBtn    = document.getElementById('chat-send-btn');
    const clearBtn   = document.getElementById('clear-chat-btn');

    // Status messages shown while waiting (mirrors ai_generate.js pattern)
    const STATUS_MESSAGES = [
        { after: 0,  text: 'Thinking…' },
        { after: 5,  text: 'Generating response…' },
        { after: 15, text: 'Still working — LLMs can take a moment…' },
        { after: 30, text: 'Almost there…' },
        { after: 60, text: 'Still processing — hang tight…' },
    ];

    let statusTimer = null;
    let statusStart = null;

    // ---------------------------------------------------------------------------
    // Send message
    // ---------------------------------------------------------------------------

    function sendMessage() {
        if (!cfg.aiEnabled || !cfg.hasCampaign) return;

        const message = (inputEl.value || '').trim();
        if (!message) return;

        inputEl.value = '';
        inputEl.style.height = '';

        appendUserMessage(message);
        const thinkingEl = appendThinkingMessage();
        setInputEnabled(false);
        startStatusMessages(thinkingEl);

        fetch(cfg.sendUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': cfg.csrfToken,
            },
            body: JSON.stringify({ message }),
        })
            .then(r => r.json().then(data => ({ ok: r.ok, data })))
            .then(({ ok, data }) => {
                stopStatusMessages();
                thinkingEl.remove();

                if (!ok || data.error) {
                    appendErrorMessage(data.error || 'An error occurred. Please try again.');
                    return;
                }

                appendAssistantMessage(data.response, data.entities || []);

                // Enable clear button now that there's history
                if (clearBtn) clearBtn.disabled = false;
            })
            .catch(() => {
                stopStatusMessages();
                thinkingEl.remove();
                appendErrorMessage('Request failed — check your connection and try again.');
            })
            .finally(() => {
                setInputEnabled(true);
                inputEl.focus();
            });
    }

    // ---------------------------------------------------------------------------
    // Message rendering helpers
    // ---------------------------------------------------------------------------

    function appendUserMessage(text) {
        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex justify-content-end mb-3';
        wrapper.innerHTML = `<div class="bg-primary text-white rounded-3 px-3 py-2" style="max-width:75%; white-space:pre-wrap;">${escapeHtml(text)}</div>`;
        messagesEl.appendChild(wrapper);
        scrollToBottom();
    }

    function appendThinkingMessage() {
        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex justify-content-start mb-3';
        wrapper.innerHTML = `
            <div class="border border-secondary rounded-3 px-3 py-2 text-muted" style="max-width:85%;">
                <span class="spinner-border spinner-border-sm me-2"></span>
                <span class="thinking-status">Thinking…</span>
            </div>`;
        messagesEl.appendChild(wrapper);
        scrollToBottom();
        return wrapper;
    }

    function appendAssistantMessage(prose, entities) {
        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex flex-column justify-content-start mb-3';

        // Prose section
        if (prose) {
            const proseEl = document.createElement('div');
            proseEl.className = 'border border-secondary rounded-3 px-3 py-2 mb-2';
            proseEl.style.maxWidth = '85%';
            proseEl.style.whiteSpace = 'pre-wrap';
            proseEl.textContent = prose;
            wrapper.appendChild(proseEl);
        }

        // Entity cards
        entities.forEach(entity => {
            wrapper.appendChild(buildEntityCard(entity));
        });

        messagesEl.appendChild(wrapper);
        scrollToBottom();
    }

    function appendErrorMessage(text) {
        const wrapper = document.createElement('div');
        wrapper.className = 'd-flex justify-content-start mb-3';
        wrapper.innerHTML = `<div class="alert alert-danger mb-0 py-2" style="max-width:85%;">
            <i class="bi bi-exclamation-triangle me-1"></i>${escapeHtml(text)}
        </div>`;
        messagesEl.appendChild(wrapper);
        scrollToBottom();
    }

    // ---------------------------------------------------------------------------
    // Entity cards
    // ---------------------------------------------------------------------------

    const ENTITY_ICONS = {
        npc:      'bi-person',
        location: 'bi-geo-alt',
        quest:    'bi-scroll',
        item:     'bi-bag',
    };

    const ENTITY_LABELS = {
        npc:      'NPC',
        location: 'Location',
        quest:    'Quest',
        item:     'Item',
    };

    function buildEntityCard(entity) {
        const type   = entity.type;
        const fields = entity.fields || {};
        const icon   = ENTITY_ICONS[type]   || 'bi-stars';
        const label  = ENTITY_LABELS[type]  || type;
        const name   = fields.name || 'Unnamed';

        // Build a short preview of the key fields
        const previews = [];
        if (fields.role)        previews.push(fields.role);
        if (fields.type)        previews.push(fields.type);
        if (fields.status)      previews.push(fields.status);
        if (fields.rarity)      previews.push(fields.rarity);
        if (fields.description) previews.push(fields.description.substring(0, 100) + (fields.description.length > 100 ? '…' : ''));
        if (fields.hook)        previews.push(fields.hook.substring(0, 100) + (fields.hook.length > 100 ? '…' : ''));
        if (fields.physical_description) previews.push(fields.physical_description.substring(0, 100) + (fields.physical_description.length > 100 ? '…' : ''));

        const card = document.createElement('div');
        card.className = 'card border-success mb-2';
        card.style.maxWidth = '85%';
        card.style.backgroundColor = '#0f1f14'; // subtle dark green tint

        card.innerHTML = `
            <div class="card-body py-2 px-3">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <span class="badge bg-success me-2">
                            <i class="${icon} me-1"></i>${label}
                        </span>
                        <strong>${escapeHtml(name)}</strong>
                    </div>
                    <button class="btn btn-sm btn-success save-entity-btn ms-2" style="white-space:nowrap;">
                        <i class="bi bi-floppy me-1"></i>Save to Campaign
                    </button>
                </div>
                ${previews.length ? `<p class="text-muted small mb-0 mt-1">${escapeHtml(previews[0])}</p>` : ''}
            </div>`;

        // Wire up the save button
        const saveBtn = card.querySelector('.save-entity-btn');
        saveBtn.addEventListener('click', () => saveEntity(entity, saveBtn));

        return card;
    }

    // ---------------------------------------------------------------------------
    // Save entity
    // ---------------------------------------------------------------------------

    function saveEntity(entity, btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving…';

        fetch(cfg.saveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': cfg.csrfToken,
            },
            body: JSON.stringify({
                entity_type: entity.type,
                fields: entity.fields,
            }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    btn.outerHTML = `<a href="${data.url}" class="btn btn-sm btn-outline-success ms-2">
                        <i class="bi bi-check-lg me-1"></i>Saved — View ${escapeHtml(data.name)}
                    </a>`;
                } else {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Failed — Try Again';
                    btn.classList.replace('btn-success', 'btn-danger');
                }
            })
            .catch(() => {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-exclamation-triangle me-1"></i>Error';
                btn.classList.replace('btn-success', 'btn-danger');
            });
    }

    // ---------------------------------------------------------------------------
    // Clear chat
    // ---------------------------------------------------------------------------

    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            if (!confirm('Clear the conversation history?')) return;
            fetch(cfg.clearUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': cfg.csrfToken },
            })
                .then(() => location.reload())
                .catch(() => location.reload());
        });
    }

    // ---------------------------------------------------------------------------
    // Status message rotation (while waiting for AI response)
    // ---------------------------------------------------------------------------

    function startStatusMessages(thinkingEl) {
        statusStart = Date.now();
        const statusEl = thinkingEl.querySelector('.thinking-status');
        let msgIndex = 0;

        statusTimer = setInterval(() => {
            const elapsed = (Date.now() - statusStart) / 1000;
            // Find the latest status message whose threshold has passed
            for (let i = STATUS_MESSAGES.length - 1; i >= 0; i--) {
                if (elapsed >= STATUS_MESSAGES[i].after) {
                    if (i !== msgIndex) {
                        msgIndex = i;
                        if (statusEl) statusEl.textContent = STATUS_MESSAGES[i].text;
                    }
                    break;
                }
            }
        }, 1000);
    }

    function stopStatusMessages() {
        if (statusTimer) {
            clearInterval(statusTimer);
            statusTimer = null;
        }
    }

    // ---------------------------------------------------------------------------
    // Utility
    // ---------------------------------------------------------------------------

    function setInputEnabled(enabled) {
        if (inputEl) inputEl.disabled = !enabled;
        if (sendBtn) sendBtn.disabled = !enabled;
    }

    function scrollToBottom() {
        if (messagesEl) messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ---------------------------------------------------------------------------
    // Event listeners
    // ---------------------------------------------------------------------------

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (inputEl) {
        inputEl.addEventListener('keydown', e => {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Scroll to bottom on initial load (if replaying history)
    scrollToBottom();

})();
