document.addEventListener('DOMContentLoaded', () => {
    const characterSelect = document.getElementById('character-select');
    const characterPortrait = document.getElementById('character-portrait');
    const portraitPlaceholder = document.getElementById('portrait-placeholder');
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');

    let selectedCharacterName = null;
    let isThinking = false;

    // --- Event Listeners ---
    characterSelect.addEventListener('change', async () => {
        selectedCharacterName = characterSelect.value;
        updateCharacterPortrait();
        clearChat(); // Clear first

        if (selectedCharacterName) {
            // Fetch history from server
            chatInput.disabled = true; // Disable input while loading history
            sendButton.disabled = true;
            addSystemMessage("Loading history..."); // Indicate loading
            try {
                const response = await fetch(`/history/${encodeURIComponent(selectedCharacterName)}`);
                clearChat(); // Clear loading message
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const history = await response.json();

                // Display loaded history
                if (history.length > 0) {
                    console.log("Loading history:", history); // Debug log
                    history.forEach(msg => {
                        // Ensure msg has role and text before adding
                        if (msg && msg.role && typeof msg.text !== 'undefined') {
                            addChatMessage(msg.role, msg.text);
                        } else {
                            console.warn("Skipping invalid message in history:", msg);
                        }
                    });
                } else {
                    addSystemMessage(`You approach ${selectedCharacterName}.`); // Show if no history
                }

                // Enable interaction
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();

            } catch (error) {
                console.error("Error fetching history:", error);
                clearChat(); // Clear loading message
                addErrorMessage("Error loading conversation history.");
                // Keep input disabled on error
            }
        } else {
            // No character selected
            chatInput.disabled = true;
            sendButton.disabled = true;
        }
    });

    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !isThinking && selectedCharacterName) {
            sendMessage();
        }
    });

    // --- UI Functions ---
    function updateCharacterPortrait() {
        if (selectedCharacterName) {
            const imageUrl = `/character_image/${encodeURIComponent(selectedCharacterName)}`;
            characterPortrait.src = imageUrl;
            characterPortrait.style.display = 'block';
            portraitPlaceholder.style.display = 'none';
            characterPortrait.onerror = () => {
                characterPortrait.style.display = 'none';
                portraitPlaceholder.textContent = `(Image not found for ${selectedCharacterName})`;
                portraitPlaceholder.style.display = 'block';
            };
        } else {
            characterPortrait.style.display = 'none';
            portraitPlaceholder.textContent = 'Select a character to see their portrait.';
            portraitPlaceholder.style.display = 'block';
        }
    }

    function clearChat() {
        chatBox.innerHTML = '';
    }

    // Only displays messages, history is managed server-side
    function addChatMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message');
        messageDiv.textContent = text; // Default text content

        // Match roles sent by the server ("Player", "Character")
        switch (role) {
            case 'Player': // Check for "Player" role from server history
                messageDiv.classList.add('user-message');
                messageDiv.textContent = `You: ${text}`;
                break;
            case 'Character': // Check for "Character" role from server history
                messageDiv.classList.add('character-message');
                // Use current selection for name, fallback if needed
                const characterName = selectedCharacterName || 'Character';
                messageDiv.textContent = `${characterName}: ${text}`;
                break;
            case 'system': // For client-side system messages
                messageDiv.classList.add('thinking-message');
                break;
            case 'error': // For client-side error messages
                messageDiv.classList.add('error-message');
                break;
            default:
                console.warn("Unknown chat message role:", role);
            // Optionally add a default style or prefix
            // messageDiv.textContent = `${role}: ${text}`;
        }

        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function addSystemMessage(text) {
        addChatMessage('system', text);
    }

    function addErrorMessage(text) {
        addChatMessage('error', text);
    }

    // --- Send Message Logic --- (Server handles history persistence)
    async function sendMessage() {
        const prompt = chatInput.value.trim();
        if (!prompt || !selectedCharacterName || isThinking) {
            return;
        }

        addChatMessage('Player', prompt); // Display user message immediately with correct role
        chatInput.value = '';
        isThinking = true;
        sendButton.disabled = true;
        chatInput.disabled = true;

        const thinkingMessageDiv = document.createElement('div');
        thinkingMessageDiv.classList.add('thinking-message');
        thinkingMessageDiv.textContent = `${selectedCharacterName} is thinking...`;
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
                    character_name: selectedCharacterName,
                    prompt: prompt,
                }),
            });

            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);

            if (!response.ok) {
                let errorText = 'Failed to get response';
                try {
                    const errorData = await response.json();
                    errorText = errorData.error || errorText;
                } catch (e) { /* Ignore */ }
                console.error("Chat API Error:", response.status, errorText);
                addErrorMessage(`Error: ${errorText}`);
                addChatMessage('Character', `(My mind feels muddled right now...)`);
            } else {
                const data = await response.json();
                addChatMessage('Character', data.response);
            }
        } catch (error) {
            console.error("Fetch Error:", error);
            const thinkingIndicator = document.getElementById('thinking-indicator');
            if (thinkingIndicator) chatBox.removeChild(thinkingIndicator);
            addErrorMessage('Error: Could not connect to the server.');
            addChatMessage('Character', `(My connection seems fuzzy...)`);
        } finally {
            isThinking = false;
            if (characterSelect.value) {
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            }
        }
    }
}); 