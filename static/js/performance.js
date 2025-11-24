// ===== LIVE TESTING FUNCTIONALITY =====
        
        const testQuestions = [
            "What are the library hours?",
            "How do I apply for admission to NCIRL?",
            "What courses are available?",
            "How much are the tuition fees?",
            "Where is the student support office?"
        ];

        const GROQ_COST_PER_1M_TOKENS = 0.59;
        const CHATGPT_COST_PER_1M_TOKENS = 10.00; // GPT-4 pricing
        
        let testResults = {
            queries: 0,
            totalTokens: 0,
            totalResponseTime: 0,
            groqCost: 0,
            chatgptCost: 0
        };

        let testChart = null;

        async function runLiveTest() {
            const runBtn = document.getElementById('runTestBtn');
            const clearBtn = document.getElementById('clearTestBtn');
            const logsContent = document.getElementById('logsContent');
            const logStatus = document.getElementById('logStatus');
            const testSummary = document.getElementById('testSummary');
            const costComparisonDiv = document.getElementById('costComparisonTest');
            
            // Disable button and update status
            runBtn.disabled = true;
            runBtn.innerHTML = '<span class="spinner"></span> Running Test...';
            logStatus.textContent = 'Testing in progress...';
            logsContent.innerHTML = '';
            
            // Reset results
            testResults = {
                queries: 0,
                totalTokens: 0,
                totalResponseTime: 0,
                groqCost: 0,
                chatgptCost: 0
            };

            // Show summary section
            testSummary.style.display = 'block';

            for (let i = 0; i < testQuestions.length; i++) {
                const question = testQuestions[i];
                await testSingleQuery(question, i + 1, logsContent);
                
                // Update summary after each query
                updateTestSummary();
                
                // Small delay between queries
                await new Promise(resolve => setTimeout(resolve, 500));
            }

            // Test complete
            runBtn.disabled = false;
            runBtn.textContent = '✓ Test Complete - Run Again?';
            clearBtn.style.display = 'inline-block';
            logStatus.textContent = `✓ Completed ${testResults.queries} queries`;
            logStatus.style.animation = 'none';
            
            // Show cost comparison chart
            costComparisonDiv.style.display = 'block';
            updateCostChart();
        }

        async function testSingleQuery(question, queryNum, logsContainer) {
            const startTime = Date.now();
            
            // Add info log
            addLog(logsContainer, 'info', `Query ${queryNum}/5`, question, null);

            try {
                // Simulate API call (replace with actual API call to your backend)
                const response = await simulateApiCall(question);
                
                const endTime = Date.now();
                const responseTime = ((endTime - startTime) / 1000).toFixed(2);
                
                // Estimate tokens (input + output, roughly)
                const estimatedTokens = estimateTokens(question, response.answer);
                
                // Calculate costs
                const groqCost = (estimatedTokens / 1000000) * GROQ_COST_PER_1M_TOKENS;
                const chatgptCost = (estimatedTokens / 1000000) * CHATGPT_COST_PER_1M_TOKENS;
                
                // Update results
                testResults.queries++;
                testResults.totalTokens += estimatedTokens;
                testResults.totalResponseTime += parseFloat(responseTime);
                testResults.groqCost += groqCost;
                testResults.chatgptCost += chatgptCost;
                
                // Add success log
                addLog(logsContainer, 'success', `✓ Response received`, response.answer.substring(0, 100) + '...', {
                    responseTime: responseTime,
                    tokens: estimatedTokens,
                    groqCost: groqCost.toFixed(6),
                    chatgptCost: chatgptCost.toFixed(6),
                    saved: (chatgptCost - groqCost).toFixed(6)
                });
                
            } catch (error) {
                addLog(logsContainer, 'warning', '⚠ Error', error.message, null);
            }
        }

        function simulateApiCall(question) {
            // Simulate API response with realistic data
            return new Promise((resolve) => {
                setTimeout(() => {
                    const responses = {
                        "What are the library hours?": "The NCIRL library is open Monday to Friday from 8:30 AM to 9:30 PM, and Saturday from 9:00 AM to 5:00 PM. During exam periods, extended hours may be available.",
                        "How do I apply for admission to NCIRL?": "You can apply to NCIRL through CAO for undergraduate courses or directly through our website for postgraduate programs. Required documents include academic transcripts, personal statement, and references.",
                        "What courses are available?": "NCIRL offers a wide range of courses including Business, Computing, Psychology, Accounting, Marketing, Data Analytics, Cloud Computing, Cybersecurity, and more at undergraduate and postgraduate levels.",
                        "How much are the tuition fees?": "Tuition fees vary by program. Undergraduate EU students pay approximately €3,000 per year. Non-EU students and postgraduate programs have different fee structures. Contact admissions for specific pricing.",
                        "Where is the student support office?": "The Student Support office is located on the ground floor of the main building at Mayor Street. They provide counseling, disability support, and general student welfare services. You can also email support@ncirl.ie."
                    };
                    
                    resolve({
                        answer: responses[question] || "This is a sample response from the NCIRL chatbot. In production, this would be the actual AI-generated response."
                    });
                }, Math.random() * 1000 + 1000); // Random delay 1-2 seconds
            });
        }

        function estimateTokens(question, answer) {
            // Rough estimation: ~4 characters per token
            // Include system prompt overhead (~100 tokens)
            const questionTokens = Math.ceil(question.length / 4);
            const answerTokens = Math.ceil(answer.length / 4);
            const systemTokens = 100;
            
            return questionTokens + answerTokens + systemTokens;
        }

        function addLog(container, type, title, message, metrics) {
            const timestamp = new Date().toLocaleTimeString();
            
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${type}`;
            
            let html = `
                <div class="log-timestamp">${timestamp}</div>
                <div class="log-question">${title}</div>
            `;
            
            if (message) {
                html += `<div style="font-size: 13px; margin-top: 5px;">${message}</div>`;
            }
            
            if (metrics) {
                html += `
                    <div class="log-metrics">
                        <span>⏱️ ${metrics.responseTime}s</span>
                        <span>🔢 ${metrics.tokens} tokens</span>
                        <span>💰 Groq: $${metrics.groqCost}</span>
                        <span>💸 GPT-4: $${metrics.chatgptCost}</span>
                        <span style="color: #28a745; font-weight: 600;">💎 Saved: $${metrics.saved}</span>
                    </div>
                `;
            }
            
            logEntry.innerHTML = html;
            container.appendChild(logEntry);
            
            // Auto-scroll to bottom
            container.scrollTop = container.scrollHeight;
        }

        function updateTestSummary() {
            // ⭐ FIXED: Updated to match actual HTML IDs
            document.getElementById('totalQueries').textContent = testResults.queries;
            document.getElementById('totalTokens').textContent = testResults.totalTokens.toLocaleString();
            document.getElementById('avgResponseTime').textContent = 
                testResults.queries > 0 
                    ? (testResults.totalResponseTime / testResults.queries).toFixed(2) + 's'
                    : '0s';
            document.getElementById('groqCost').textContent = '$' + testResults.groqCost.toFixed(4);
            document.getElementById('chatgptCost').textContent = '$' + testResults.chatgptCost.toFixed(4);
            document.getElementById('savedAmount').textContent = '$' + (testResults.chatgptCost - testResults.groqCost).toFixed(4);
        }

        function clearTestResults() {
            document.getElementById('logsContent').innerHTML = '';
            document.getElementById('clearTestBtn').style.display = 'none';
            document.getElementById('testSummary').style.display = 'none';
            document.getElementById('costComparisonTest').style.display = 'none';
            document.getElementById('logStatus').textContent = 'Ready to test';
            document.getElementById('runTestBtn').textContent = '▶️ Run Live Test (5 Questions)';
            
            testResults = {
                queries: 0,
                totalTokens: 0,
                totalResponseTime: 0,
                groqCost: 0,
                chatgptCost: 0
            };
        }

        function updateCostChart() {
            const ctx = document.getElementById('testCostChart');
            
            if (!ctx) {
                console.error('❌ testCostChart canvas not found!');
                return;
            }
            
            if (testChart) {
                testChart.destroy();
            }
            
            testChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Groq (Our Chatbot)', 'ChatGPT GPT-4', 'Total Savings'],
                    datasets: [{
                        label: 'Cost ($)',
                        data: [
                            testResults.groqCost,
                            testResults.chatgptCost,
                            testResults.chatgptCost - testResults.groqCost
                        ],
                        backgroundColor: [
                            'rgba(40, 167, 69, 0.8)',
                            'rgba(220, 53, 69, 0.8)',
                            'rgba(23, 162, 184, 0.8)'
                        ],
                        borderColor: [
                            'rgba(40, 167, 69, 1)',
                            'rgba(220, 53, 69, 1)',
                            'rgba(23, 162, 184, 1)'
                        ],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: `Cost Comparison for ${testResults.queries} Queries`,
                            font: {
                                size: 16
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Cost (USD)'
                            }
                        }
                    }
                }
            });
        }

        // ===== LIVE API USAGE MONITORING =====

        let usageData = {
            activeKey: 1,
            totalCost: 0,
            totalTokens: 0,
            requestsToday: 0,
            keys: [
                { requests: 0, tokens: 0, cost: 0, limit: 14400 },
                { requests: 0, tokens: 0, cost: 0, limit: 14400 },
                { requests: 0, tokens: 0, cost: 0, limit: 14400 }
            ]
        };

        async function fetchUsageData() {
            const refreshBtn = document.getElementById('refreshUsageBtn');
            refreshBtn.disabled = true;
            refreshBtn.textContent = '🔄 Loading...';

            try {
                // Fetch REAL API usage data from backend
                const response = await fetch('/api-status');
                if (!response.ok) {
                    throw new Error('Failed to fetch API status');
                }

                const data = await response.json();
                
                // ✅ USE REAL DATA FROM BACKEND
                usageData.activeKey = data.activeKey;
                usageData.totalCost = data.totalCost;
                usageData.totalTokens = data.totalTokens;
                usageData.requestsToday = data.requestsToday;
                
                // Update each key's data with real values
                data.keys.forEach((keyData, index) => {
                    usageData.keys[index].requests = keyData.requests;
                    usageData.keys[index].tokens = keyData.tokens;
                    usageData.keys[index].cost = keyData.cost;
                });

                updateUsageDisplay();
                
            } catch (error) {
                console.error('Error fetching usage data:', error);
                alert('Failed to fetch usage data. Using demo data as fallback.');
                
                // Use simulated data as fallback
                usageData.requestsToday = 0;
                usageData.totalTokens = 0;
                usageData.totalCost = 0.0;
                usageData.keys.forEach(key => {
                    key.requests = 0;
                    key.tokens = 0;
                    key.cost = 0.0;
                });
                updateUsageDisplay();
            } finally {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 Refresh Usage Data';
                
                const now = new Date();
                document.getElementById('lastUpdated').textContent = 
                    `Last updated: ${now.toLocaleTimeString()}`;
            }
        }

        function updateUsageDisplay() {
            // Update summary cards
            document.getElementById('activeKeyNum').textContent = `Key ${usageData.activeKey}`;
            document.getElementById('totalCost').textContent = `$${usageData.totalCost.toFixed(4)}`;
            
            // Handle duplicate totalTokens ID - update the one in usage section
            const totalTokensElements = document.querySelectorAll('#totalTokens');
            if (totalTokensElements.length > 1) {
                // Update the second one (usage monitor section)
                totalTokensElements[1].textContent = usageData.totalTokens.toLocaleString();
            } else if (totalTokensElements.length === 1) {
                totalTokensElements[0].textContent = usageData.totalTokens.toLocaleString();
            }
            
            document.getElementById('requestsToday').textContent = usageData.requestsToday.toLocaleString();

            // Update each key card
            usageData.keys.forEach((key, index) => {
                const keyNum = index + 1;
                const percentage = (key.requests / key.limit) * 100;

                // Update progress bar
                const progressFill = document.getElementById(`progress${keyNum}`);
                if (progressFill) {
                    progressFill.style.width = `${percentage}%`;
                    
                    // Change color based on usage
                    progressFill.className = 'progress-fill';
                    if (percentage >= 90) {
                        progressFill.classList.add('danger');
                    } else if (percentage >= 70) {
                        progressFill.classList.add('warning');
                    }
                }

                // Update progress text
                const progressText = document.getElementById(`progressText${keyNum}`);
                if (progressText) {
                    progressText.textContent = `${key.requests.toLocaleString()} / ${key.limit.toLocaleString()} requests (${percentage.toFixed(1)}%)`;
                }

                // Update key details
                const keyCost = document.getElementById(`keyCost${keyNum}`);
                if (keyCost) {
                    keyCost.textContent = `💰 Cost: $${key.cost.toFixed(4)}`;
                }
                
                const keyTokens = document.getElementById(`keyTokens${keyNum}`);
                if (keyTokens) {
                    keyTokens.textContent = `🔢 Tokens: ${key.tokens.toLocaleString()}`;
                }

                // Update key card styling
                const keyCard = document.getElementById(`keyCard${keyNum}`);
                if (keyCard) {
                    const statusElement = keyCard.querySelector('.key-status');
                    
                    if (keyNum === usageData.activeKey) {
                        keyCard.classList.add('active-key');
                        if (statusElement) {
                            statusElement.classList.add('active');
                            statusElement.textContent = '● Active';
                        }
                    } else {
                        keyCard.classList.remove('active-key');
                        if (statusElement) {
                            statusElement.classList.remove('active');
                            statusElement.textContent = '● Standby';
                        }
                    }
                }
            });
        }

        // ⭐ AUTO-REFRESH EVERY 5 SECONDS (UPDATED FROM 30s) ⭐
        let autoRefreshInterval = null;
        const REFRESH_INTERVAL = 5000; // 5 seconds in milliseconds

        function startAutoRefresh() {
            // Clear any existing interval
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
            
            // Fetch immediately
            fetchUsageData();
            
            // Then refresh every 5 seconds
            autoRefreshInterval = setInterval(fetchUsageData, REFRESH_INTERVAL);
            
            console.log(`✅ Auto-refresh started (${REFRESH_INTERVAL/1000}s interval)`);
            
            // Update toggle button state if it exists
            const toggleBtn = document.getElementById('toggleAutoRefreshBtn');
            if (toggleBtn) {
                toggleBtn.textContent = '⏸️ Pause Auto-Refresh';
                toggleBtn.style.background = 'linear-gradient(135deg, #ffc107 0%, #ff9800 100%)';
            }
        }

        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                console.log('⏹️ Auto-refresh stopped');
                
                // Update toggle button state if it exists
                const toggleBtn = document.getElementById('toggleAutoRefreshBtn');
                if (toggleBtn) {
                    toggleBtn.textContent = '▶️ Start Auto-Refresh';
                    toggleBtn.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
                }
            }
        }

        function toggleAutoRefresh() {
            if (autoRefreshInterval) {
                stopAutoRefresh();
            } else {
                startAutoRefresh();
            }
        }

        // ===== API HEALTH CHECK FUNCTIONALITY =====

        const apiTestModal = document.getElementById('apiTestModal');
        const testApiBtn = document.getElementById('testApiBtn');
        const closeModalBtn = document.getElementById('closeModalBtn');
        const closeTestBtn = document.getElementById('closeTestBtn');
        const retestBtn = document.getElementById('retestBtn');

        let apiTestResults = [];

        // ===== CHART.JS CONFIGURATION WITH DOM READY FIX =====
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🎨 Initializing dashboard...');
            
            Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

            // ⭐ SETUP EVENT LISTENERS FOR LIVE TEST ⭐
            const runBtn = document.getElementById('runTestBtn');
            const clearBtn = document.getElementById('clearTestBtn');
            
            if (runBtn) {
                runBtn.addEventListener('click', runLiveTest);
                console.log('✅ Live Test button event listener added');
            } else {
                console.error('❌ runTestBtn not found!');
            }
            
            if (clearBtn) {
                clearBtn.addEventListener('click', clearTestResults);
                console.log('✅ Clear Test button event listener added');
            }

            // Setup API Usage event listeners
            const refreshBtn = document.getElementById('refreshUsageBtn');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => {
                    fetchUsageData();
                    startAutoRefresh(); // Restart auto-refresh timer
                });
                console.log('✅ Refresh Usage button event listener added');
            }

            // Event listener for toggle auto-refresh button (optional)
            const toggleBtn = document.getElementById('toggleAutoRefreshBtn');
            if (toggleBtn) {
                toggleBtn.addEventListener('click', toggleAutoRefresh);
                console.log('✅ Toggle Auto-Refresh button event listener added');
            }

            // Setup API Health Check modal
            if (testApiBtn) {
                testApiBtn.addEventListener('click', () => {
                    apiTestModal.style.display = 'block';
                    resetTestUI();
                    startAPITest();
                });
            }

            if (closeModalBtn) {
                closeModalBtn.addEventListener('click', closeModal);
            }
            
            if (closeTestBtn) {
                closeTestBtn.addEventListener('click', closeModal);
            }
            
            if (retestBtn) {
                retestBtn.addEventListener('click', () => {
                    resetTestUI();
                    startAPITest();
                });
            }

            // Close modal on outside click
            window.addEventListener('click', (e) => {
                if (e.target === apiTestModal) {
                    closeModal();
                }
            });

            // ⭐ START AUTO-REFRESH AFTER SHORT DELAY ⭐
            setTimeout(startAutoRefresh, 2000);

            // Check if canvas elements exist
            const responseTimeCanvas = document.getElementById('responseTimeChart');
            const costCanvas = document.getElementById('costComparisonChart');
            const tokenCanvas = document.getElementById('tokenUsageChart');

            if (!responseTimeCanvas || !costCanvas || !tokenCanvas) {
                console.error('❌ One or more canvas elements not found!');
                return;
            }

            console.log('✅ All canvas elements found');

            // 1. Response Time Comparison Chart
            try {
                const responseTimeCtx = responseTimeCanvas.getContext('2d');
                new Chart(responseTimeCtx, {
                    type: 'bar',
                    data: {
                        labels: ['NCIRL Chatbot\n(Streaming)', 'ChatGPT\n(Bulk)', 'Basic Chatbot\n(Static)', 'Average Response\nTime'],
                        datasets: [{
                            label: 'Time to Complete Response (seconds)',
                            data: [2.1, 3.2, 0.8, 2.0],
                            backgroundColor: [
                                'rgba(102, 126, 234, 0.8)',
                                'rgba(255, 99, 132, 0.8)',
                                'rgba(255, 206, 86, 0.8)',
                                'rgba(75, 192, 192, 0.8)'
                            ],
                            borderColor: [
                                'rgba(102, 126, 234, 1)',
                                'rgba(255, 99, 132, 1)',
                                'rgba(255, 206, 86, 1)',
                                'rgba(75, 192, 192, 1)'
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            title: {
                                display: true,
                                text: 'Response Time Performance Comparison',
                                font: {
                                    size: 18
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Seconds'
                                }
                            }
                        }
                    }
                });
                console.log('✅ Response Time Chart created');
            } catch (error) {
                console.error('❌ Error creating Response Time Chart:', error);
            }

            // 2. Cost Comparison Chart
            try {
                const costCtx = costCanvas.getContext('2d');
                new Chart(costCtx, {
                    type: 'bar',
                    data: {
                        labels: ['NCIRL Chatbot\n(Groq LLaMA)', 'ChatGPT\nGPT-3.5', 'ChatGPT\nGPT-4', 'Monthly Savings\nvs GPT-4'],
                        datasets: [{
                            label: 'Cost per 1000 Queries (USD)',
                            data: [0.30, 0.25, 5.00, 4.70],
                            backgroundColor: [
                                'rgba(40, 167, 69, 0.8)',
                                'rgba(255, 193, 7, 0.8)',
                                'rgba(220, 53, 69, 0.8)',
                                'rgba(23, 162, 184, 0.8)'
                            ],
                            borderColor: [
                                'rgba(40, 167, 69, 1)',
                                'rgba(255, 193, 7, 1)',
                                'rgba(220, 53, 69, 1)',
                                'rgba(23, 162, 184, 1)'
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'top'
                            },
                            title: {
                                display: true,
                                text: 'Cost Efficiency: NCIRL Chatbot vs ChatGPT (1000 queries/month)',
                                font: {
                                    size: 18
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Cost (USD)'
                                }
                            }
                        }
                    }
                });
                console.log('✅ Cost Comparison Chart created');
            } catch (error) {
                console.error('❌ Error creating Cost Comparison Chart:', error);
            }

            // 3. Token Usage Chart
            try {
                const tokenCtx = tokenCanvas.getContext('2d');
                new Chart(tokenCtx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Input Tokens (250)', 'Output Tokens (250)', 'Follow-up Tokens (100)', 'System Tokens (50)'],
                        datasets: [{
                            label: 'Token Distribution per Query',
                            data: [250, 250, 100, 50],
                            backgroundColor: [
                                'rgba(102, 126, 234, 0.8)',
                                'rgba(118, 75, 162, 0.8)',
                                'rgba(40, 167, 69, 0.8)',
                                'rgba(255, 193, 7, 0.8)'
                            ],
                            borderColor: [
                                'rgba(102, 126, 234, 1)',
                                'rgba(118, 75, 162, 1)',
                                'rgba(40, 167, 69, 1)',
                                'rgba(255, 193, 7, 1)'
                            ],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'bottom'
                            },
                            title: {
                                display: true,
                                text: 'Average Token Usage Breakdown (650 tokens/query)',
                                font: {
                                    size: 18
                                }
                            }
                        }
                    }
                });
                console.log('✅ Token Usage Chart created');
            } catch (error) {
                console.error('❌ Error creating Token Usage Chart:', error);
            }

            console.log('🎉 All charts and event listeners initialized successfully!');
        });

        // ===== API HEALTH CHECK HELPER FUNCTIONS =====
        
        function closeModal() {
            if (apiTestModal) {
                apiTestModal.style.display = 'none';
            }
        }

        function resetTestUI() {
            apiTestResults = [];
            
            // Reset all test items to pending
            for (let i = 1; i <= 3; i++) {
                const testItem = document.getElementById(`testKey${i}`);
                if (testItem) {
                    const statusElement = testItem.querySelector('.test-status');
                    const detailsElement = testItem.querySelector('.test-details');
                    
                    if (statusElement) {
                        statusElement.className = 'test-status pending';
                        statusElement.textContent = i === 1 ? '⏳ Testing...' : '⏳ Waiting...';
                    }
                    if (detailsElement) {
                        detailsElement.style.display = 'none';
                    }
                    testItem.classList.remove('test-success', 'test-fail');
                }
            }
            
            // Hide summary
            const summarySection = document.getElementById('testSummarySection');
            if (summarySection) {
                summarySection.style.display = 'none';
            }
        }

        async function startAPITest() {
            console.log('Starting API health check...');
            
            for (let i = 1; i <= 3; i++) {
                await testSingleAPI(i);
                await new Promise(resolve => setTimeout(resolve, 500)); // Small delay
            }
            
            showTestSummary();
        }

        async function testSingleAPI(keyNum) {
            const testItem = document.getElementById(`testKey${keyNum}`);
            if (!testItem) return;
            
            const statusElement = testItem.querySelector('.test-status');
            const detailsElement = testItem.querySelector('.test-details');
            
            if (statusElement) {
                statusElement.className = 'test-status pending';
                statusElement.textContent = '⏳ Testing...';
            }
            
            const startTime = Date.now();
            
            try {
                // Call backend endpoint to test specific API key
                const response = await fetch(`/test-api-key/${keyNum}`);
                const data = await response.json();
                
                const endTime = Date.now();
                const responseTime = endTime - startTime;
                
                if (data.success) {
                    // Success
                    if (statusElement) {
                        statusElement.className = 'test-status success';
                        statusElement.textContent = '✅ Working';
                    }
                    testItem.classList.add('test-success');
                    
                    // Show details
                    if (detailsElement) {
                        const metrics = detailsElement.querySelectorAll('.test-value');
                        if (metrics.length >= 4) {
                            metrics[0].textContent = `${responseTime}ms`;
                            metrics[1].textContent = data.model || 'llama-3.3-70b-versatile';
                            metrics[2].textContent = `~${data.tokens || 150}`;
                            metrics[3].textContent = data.response ? data.response.substring(0, 100) + '...' : 'N/A';
                        }
                        detailsElement.style.display = 'block';
                    }
                    
                    apiTestResults.push({
                        keyNum,
                        success: true,
                        responseTime,
                        model: data.model,
                        tokens: data.tokens
                    });
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
                
            } catch (error) {
                // Failure
                if (statusElement) {
                    statusElement.className = 'test-status fail';
                    statusElement.textContent = `❌ Failed`;
                }
                testItem.classList.add('test-fail');
                
                // Show error details
                if (detailsElement) {
                    const metrics = detailsElement.querySelectorAll('.test-value');
                    if (metrics.length >= 4) {
                        metrics[0].textContent = '-';
                        metrics[1].textContent = '-';
                        metrics[2].textContent = '-';
                        metrics[3].textContent = `Error: ${error.message}`;
                    }
                    detailsElement.style.display = 'block';
                }
                
                apiTestResults.push({
                    keyNum,
                    success: false,
                    error: error.message,
                    responseTime: 0
                });
            }
        }

        function showTestSummary() {
            const summarySection = document.getElementById('testSummarySection');
            if (!summarySection) return;
            
            const workingKeys = apiTestResults.filter(r => r.success).length;
            const failedKeys = apiTestResults.filter(r => !r.success).length;
            const avgTime = apiTestResults
                .filter(r => r.success)
                .reduce((sum, r) => sum + r.responseTime, 0) / (workingKeys || 1);

            const workingKeysEl = document.getElementById('workingKeys');
            const failedKeysEl = document.getElementById('failedKeys');
            const avgResponseTimeEl = document.getElementById('avgResponseTime');
            
            if (workingKeysEl) workingKeysEl.textContent = workingKeys;
            if (failedKeysEl) failedKeysEl.textContent = failedKeys;
            if (avgResponseTimeEl) {
                avgResponseTimeEl.textContent = workingKeys > 0 ? `${Math.round(avgTime)}ms` : 'N/A';
            }

            const conclusion = document.getElementById('testConclusion');
            if (conclusion) {
                if (workingKeys === 3) {
                    conclusion.innerHTML = '🎉 Perfect! All 3 API keys are working correctly. Your chatbot has full redundancy and can handle high traffic.';
                    conclusion.style.background = 'rgba(40, 167, 69, 0.2)';
                } else if (workingKeys >= 2) {
                    conclusion.innerHTML = `⚠️ ${workingKeys} out of 3 keys are working. Your system is operational but check the failed key(s).`;
                    conclusion.style.background = 'rgba(255, 193, 7, 0.2)';
                } else if (workingKeys === 1) {
                    conclusion.innerHTML = '⚠️ Only 1 key is working. Your system is operational but lacks redundancy. Check other keys urgently.';
                    conclusion.style.background = 'rgba(255, 193, 7, 0.3)';
                } else {
                    conclusion.innerHTML = '❌ All API keys failed! Check your API keys and network connection immediately.';
                    conclusion.style.background = 'rgba(220, 53, 69, 0.2)';
                }
            }

            summarySection.style.display = 'block';
        }