/**
 * npc_chat.js
 * Quick NPC dialogue generator for Session Mode.
 * Opens a modal, sends a situation to the AI, and displays in-character dialogue.
 */

(function () {
    'use strict';

    const STATUS_MESSAGES = [
        { after: 0,  text: 'Thinking in character...' },
        { after: 5,  text: 'Crafting dialogue...' },
        { after: 15, text: 'Still working — local models can take a moment...' },
        { after: 30, text: 'Almost there...' },
    ];

    let statusTimer = null;
    let startTime = 0;

    function startStatusUpdates() {
        startTime = Date.now();
        const statusEl = document.getElementById('npc-chat-status');
        statusEl.classList.remove('d-none');

        function update() {
            const elapsed = (Date.now() - startTime) / 1000;
            let msg = STATUS_MESSAGES[0].text;
            for (const s of STATUS_MESSAGES) {
                if (elapsed >= s.after) msg = s.text;
            }
            statusEl.textContent = msg;
        }

        update();
        statusTimer = setInterval(update, 3000);
    }

    function stopStatusUpdates() {
        if (statusTimer) clearInterval(statusTimer);
        statusTimer = null;
        const statusEl = document.getElementById('npc-chat-status');
        if (statusEl) statusEl.classList.add('d-none');
    }

    // Called by the chat button on each NPC
    window.openNpcChat = function (npcId, npcName) {
        document.getElementById('npc-chat-npc-id').value = npcId;
        document.getElementById('npc-chat-npc-name').textContent = npcName;
        document.getElementById('npc-chat-situation').value = '';
        document.getElementById('npc-chat-response').classList.add('d-none');
        document.getElementById('npc-chat-response-text').textContent = '';
        document.getElementById('npc-chat-error').classList.add('d-none');
        stopStatusUpdates();

        const modal = new bootstrap.Modal(document.getElementById('npcChatModal'));
        modal.show();

        // Focus the textarea after modal opens
        document.getElementById('npcChatModal').addEventListener('shown.bs.modal', function handler() {
            document.getElementById('npc-chat-situation').focus();
            document.getElementById('npcChatModal').removeEventListener('shown.bs.modal', handler);
        });
    };

    document.addEventListener('DOMContentLoaded', function () {
        const form = document.getElementById('npc-chat-form');
        if (!form) return;

        const submitBtn = document.getElementById('npc-chat-submit');
        const spinner = document.getElementById('npc-chat-spinner');
        const responseBox = document.getElementById('npc-chat-response');
        const responseText = document.getElementById('npc-chat-response-text');
        const errorBox = document.getElementById('npc-chat-error');
        const csrfToken = document.getElementById('npc-chat-csrf').value;

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const npcId = document.getElementById('npc-chat-npc-id').value;
            const situation = document.getElementById('npc-chat-situation').value.trim();

            // Read selected provider from radio group, or the single hidden input
            const providerEl = document.querySelector('input[name="npc-chat-provider"]:checked')
                             || document.querySelector('input[name="npc-chat-provider"]');
            const provider = providerEl ? providerEl.value : null;

            if (!situation) return;

            // Show loading state
            submitBtn.disabled = true;
            spinner.classList.remove('d-none');
            responseBox.classList.add('d-none');
            errorBox.classList.add('d-none');
            startStatusUpdates();

            fetch('/session-mode/npc-chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ npc_id: parseInt(npcId), situation: situation, provider: provider }),
            })
                .then(r => r.json().then(data => ({ ok: r.ok, data })))
                .then(({ ok, data }) => {
                    if (!ok || data.error) {
                        errorBox.textContent = data.error || 'Something went wrong. Try again.';
                        errorBox.classList.remove('d-none');
                        return;
                    }
                    responseText.textContent = data.response;
                    responseBox.classList.remove('d-none');
                })
                .catch(() => {
                    errorBox.textContent = 'Request failed — check your connection and try again.';
                    errorBox.classList.remove('d-none');
                })
                .finally(() => {
                    submitBtn.disabled = false;
                    spinner.classList.add('d-none');
                    stopStatusUpdates();
                });
        });

        // Reset when modal closes
        document.getElementById('npcChatModal').addEventListener('hidden.bs.modal', function () {
            stopStatusUpdates();
            submitBtn.disabled = false;
            spinner.classList.add('d-none');
        });
    });
})();
