// Wait for page to load before messing with the DOM
document.addEventListener('DOMContentLoaded', function() {
    // Check if user has a theme saved, otherwise default to dark (looks cooler)
    const savedTheme = localStorage.getItem('theme') || 'dark';

    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
    }

    // Hook up the theme toggle button
    const themeToggle = document.getElementById('themeToggle');

    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            // Flip between dark and light mode
            document.body.classList.toggle('dark-mode');

            // Remember their choice for next time
            const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            localStorage.setItem('theme', currentTheme);

            // Little shrink animation when you click it
            this.style.transform = 'scale(0.9)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    }
});


// Grab references to the main chat elements
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// Simple helper to add a message to the chat
function addMessage(message, isUser) {
    const messageDiv = document.createElement('div');
    messageDiv.className = isUser ? 'message user' : 'message';

    // Pick the right avatar emoji
    const avatar = document.createElement('div');
    avatar.className = isUser ? 'message-avatar user-avatar' : 'message-avatar bot-avatar';
    avatar.textContent = isUser ? '👩‍🎓' : '🤖';

    const textDiv = document.createElement('div');
    textDiv.className = isUser ? 'user-message' : 'bot-message';
    textDiv.textContent = message;

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(textDiv);

    chatMessages.appendChild(messageDiv);
    // Auto-scroll to the bottom so you see the new message
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Fancy typing animation for the welcome message when page loads
window.addEventListener('load', function() {
    const firstMessage = document.querySelector('.bot-message');
    if (firstMessage) {
        const text = firstMessage.textContent;
        firstMessage.textContent = ''; // clear it first
        let i = 0;

        function type() {
            if (i < text.length) {
                firstMessage.textContent += text.charAt(i);
                i++;
                chatMessages.scrollTop = chatMessages.scrollHeight;
                setTimeout(type, 20); // 20ms delay between each character
            }
        }

        // Wait a bit before starting the animation
        setTimeout(type, 400);
    }
});

// Convert markdown-style formatting to HTML
// Handles **bold**, links, numbered lists, and line breaks
function formatBotMessage(text) {
    let formatted = text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') // **bold** -> <strong>bold</strong>
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #667eea; text-decoration: underline;">$1</a>') // [text](url) -> clickable link
        .replace(/(\d+)\.\s/g, '<br>$1. ') // numbered lists get line breaks
        .replace(/\n/g, '<br>'); // newlines -> <br> tags

    return formatted;
}

// Show those clickable follow-up question buttons below the bot's response
function displayFollowUpSuggestions(followUps) {
    // Clear out any old suggestions first (don't want duplicates)
    const existingSuggestions = document.querySelectorAll('.follow-up-suggestions');
    existingSuggestions.forEach(el => el.remove());

    if (!followUps || followUps.length === 0) return;

    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'follow-up-suggestions';

    // Little header with lightbulb emoji
    const headerDiv = document.createElement('div');
    headerDiv.className = 'suggestions-header';
    headerDiv.innerHTML = `
        <span class="suggestions-icon">💡</span>
        <span>You might also want to know:</span>
    `;

    suggestionsContainer.appendChild(headerDiv);

    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'suggestions-buttons';

    // Create a button for each suggestion
    followUps.forEach((suggestion, index) => {
        const button = document.createElement('button');
        button.className = 'suggestion-button';
        button.textContent = suggestion;
        button.onclick = () => handleSuggestionClick(suggestion);

        // Start invisible and slightly below, then animate in
        // Stagger the animation by 100ms for each button (looks nicer)
        button.style.opacity = '0';
        button.style.transform = 'translateY(10px)';
        button.style.transition = 'all 0.3s ease';

        setTimeout(() => {
            button.style.opacity = '1';
            button.style.transform = 'translateY(0)';
        }, index * 100);

        buttonsContainer.appendChild(button);
    });

    suggestionsContainer.appendChild(buttonsContainer);
    chatMessages.appendChild(suggestionsContainer);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// When someone clicks a suggestion button, put it in the input and send it
function handleSuggestionClick(suggestion) {
    userInput.value = suggestion;
    sendMessage();

    // Fade out and remove the suggestion buttons after clicking
    const suggestions = document.querySelectorAll('.follow-up-suggestions');
    suggestions.forEach(el => {
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
    });
}

// Main function that sends a message to the backend
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return; // don't send empty messages

    // Add user's message to chat
    addMessage(message, true);
    userInput.value = ''; // clear the input box

    // Create a placeholder for the bot's response
    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'message';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar bot-avatar';
    avatar.textContent = '👩‍🏫';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-message';
    contentDiv.id = 'streaming-message'; // we'll use this ID to update it as chunks arrive

    botMessageDiv.appendChild(avatar);
    botMessageDiv.appendChild(contentDiv);
    chatMessages.appendChild(botMessageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        // Hit the /chat endpoint
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });

        // Set up streaming reader (Server-Sent Events style)
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        const DELAY_MS = 20; // small delay between chunks for smooth animation

        // Keep reading chunks until the stream ends
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            // Process each line (SSE format is "data: {json}")
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6)); // skip "data: " prefix

                        if (data.error) {
                            contentDiv.innerHTML = formatBotMessage('Sorry, I encountered an error. Please try again.');
                            break;
                        }

                        // Got a chunk of the response text
                        if (data.content) {
                            fullText += data.content;
                            contentDiv.innerHTML = formatBotMessage(fullText);
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                            await new Promise(resolve => setTimeout(resolve, DELAY_MS)); // tiny delay for smooth typing effect
                        }

                        // Response is complete, show follow-up suggestions
                        if (data.done) {
                            contentDiv.id = ''; // remove the ID now that streaming is done

                            if (data.follow_ups && Array.isArray(data.follow_ups) && data.follow_ups.length > 0) {
                                setTimeout(() => {
                                    displayFollowUpSuggestions(data.follow_ups);
                                }, 100);
                            }
                        }
                    } catch (e) {
                        // Sometimes we get partial JSON chunks, just skip them
                    }
                }
            }
        }
    } catch (error) {
        // Network error or server is down
        const streamingMsg = document.getElementById('streaming-message');
        if (streamingMsg) {
            streamingMsg.innerHTML = formatBotMessage('Connection error. Please check if the server is running.');
        }
    }
}

// Hook up the send button and Enter key
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});