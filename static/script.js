document.addEventListener('DOMContentLoaded', () => {
    const characterSelect = document.getElementById('character-select');
    const characterPortrait = document.getElementById('character-portrait');
    const portraitPlaceholder = document.getElementById('portrait-placeholder');
    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    // Inventory elements
    const inventoryDisplay = document.getElementById('inventory-display');
    const inventoryLoading = document.getElementById('inventory-loading');
    const inventoryContent = document.getElementById('inventory-content');
    const inventoryMoney = document.getElementById('inventory-money');
    const inventoryItems = document.getElementById('inventory-items');
    const inventoryError = document.getElementById('inventory-error');

    let selectedCharacterName = null;
    let isThinking = false;

    // --- Initial Load ---
    updatePlayerInventoryDisplay(); // Fetch player inventory on load

    // --- Event Listeners ---
    characterSelect.addEventListener('change', async () => {
        selectedCharacterName = characterSelect.value;
        updateCharacterPortrait();
        clearChat();
        // updateInventoryDisplay(); // REMOVED - No longer updating based on NPC selection

        if (selectedCharacterName) {
            // Fetch HISTORY for selected character
            chatInput.disabled = true;
            sendButton.disabled = true;
            addSystemMessage("Loading history...");
            try {
                const response = await fetch(`/history/${encodeURIComponent(selectedCharacterName)}`);
                clearChat();
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const history = await response.json();
                if (history.length > 0) {
                    console.log("Loading history:", history);
                    history.forEach(msg => {
                        if (msg && msg.role && typeof msg.text !== 'undefined') {
                            addChatMessage(msg.role, msg.text);
                        } else {
                            console.warn("Skipping invalid message in history:", msg);
                        }
                    });
                } else {
                    addSystemMessage(`You approach ${selectedCharacterName}.`);
                }
                chatInput.disabled = false;
                sendButton.disabled = false;
                chatInput.focus();
            } catch (error) {
                console.error("Error fetching history:", error);
                clearChat();
                addErrorMessage("Error loading conversation history.");
            }
        } else {
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

    // Renamed function for clarity
    async function updatePlayerInventoryDisplay() {
        // inventoryLoading.style.display = 'block'; // Not needed - player inventory loads initially
        inventoryContent.style.display = 'none';
        inventoryError.style.display = 'none';
        inventoryItems.innerHTML = '<li>(None)</li>';
        inventoryMoney.textContent = '0';

        try {
            const response = await fetch(`/player_inventory`); // Fetch from the new route
            if (!response.ok) {
                let errorMsg = `HTTP error! status: ${response.status}`;
                try { const errData = await response.json(); errorMsg = errData.error || errorMsg; } catch (e) { }
                throw new Error(errorMsg);
            }
            const inventory = await response.json();

            inventoryMoney.textContent = inventory.money || 0;
            inventoryItems.innerHTML = ''; // Clear default
            if (inventory.items && Object.keys(inventory.items).length > 0) {
                for (const [item, count] of Object.entries(inventory.items)) {
                    const li = document.createElement('li');
                    li.textContent = `${item} (x${count})`;
                    inventoryItems.appendChild(li);
                }
            } else {
                inventoryItems.innerHTML = '<li>(None)</li>';
            }
            inventoryContent.style.display = 'block';
        } catch (error) {
            console.error("Error fetching player inventory:", error);
            inventoryError.textContent = `Error loading your inventory: ${error.message}`;
            inventoryError.style.display = 'block';
        } finally {
            // inventoryLoading.style.display = 'none'; // Not needed
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

    // --- Send Message Logic ---
    async function sendMessage() {
        const prompt = chatInput.value.trim();
        if (!prompt || !selectedCharacterName || isThinking) {
            return;
        }

        addChatMessage('Player', prompt);
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
                // Display the character response first
                addChatMessage('Character', data.response);

                // NOW check the flag and update inventory if needed
                if (data.player_inventory_updated === true) {
                    console.log("Server indicated player inventory updated, refreshing display...");
                    updatePlayerInventoryDisplay();
                }
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