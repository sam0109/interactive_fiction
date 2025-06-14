document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');

    let isThinking = false;

    // --- Event Listeners ---
    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !isThinking) {
            sendMessage();
        }
    });

    // --- UI Functions ---
    function addChatMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message');

        let prefix = "";
        let cssClass = "";

        switch (role.toLowerCase()) {
            case 'player':
                cssClass = 'user-message';
                prefix = "You: ";
                break;
            case 'game':
                cssClass = 'character-message'; // Re-use character style for game responses
                break;
            case 'system':
                cssClass = 'system-message';
                break;
            default:
                cssClass = 'system-message';
                prefix = `[${role}] `;
        }

        messageDiv.classList.add(cssClass);
        messageDiv.textContent = `${prefix}${text}`;

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // --- Send Message Logic ---
    async function sendMessage() {
        const prompt = chatInput.value.trim();
        if (!prompt || isThinking) {
            return;
        }

        addChatMessage('player', prompt);
        chatInput.value = '';
        isThinking = true;
        sendButton.disabled = true;
        chatInput.disabled = true;

        const thinkingMessageDiv = document.createElement('div');
        thinkingMessageDiv.classList.add('thinking-message');
        thinkingMessageDiv.textContent = `Thinking...`;
        thinkingMessageDiv.id = 'thinking-indicator';
        chatBox.appendChild(thinkingMessageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    prompt: prompt,
                }),
            });

            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);

            if (!response.ok) {
                const errorData = await response.json();
                addChatMessage('system', `Error: ${errorData.error || 'Unknown error'}`);
            } else {
                const data = await response.json();
                addChatMessage('game', data.response);
            }
        } catch (error) {
            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);
            addChatMessage('system', 'Could not connect to the server.');
        } finally {
            isThinking = false;
            sendButton.disabled = false;
            chatInput.disabled = false;
            chatInput.focus();
        }
    }
}); 