const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log("Navigating to frontend...");
    await page.goto('http://localhost:3000');

    // Wait for loading and select project
    console.log("Waiting for projects to load...");
    await page.waitForTimeout(2000);

    // Click on Project Kalfatol if it exists, otherwise just click new workspace
    const projectLink = await page.$('text="Project Kalfatol"');
    if (projectLink) {
        await projectLink.click();
    } else {
        // Try to create one
        await page.click('button:has-text("New Workspace")');
        await page.fill('input[placeholder="Name your workspace..."]', 'Test Workspace');
        await page.click('button:has-text("Create")');
    }

    await page.waitForTimeout(2000);

    console.log("Switching to Deep Chat...");
    await page.click('button:has-text("Deep Chat")');
    await page.waitForTimeout(1000);

    console.log("Typing message...");
    const msg = `Please output EXACTLY this format: 
| Feature | Document A | Document B |
|---|---|---|
| Approach | Yes | No |

**Accuracy:** 95%`;

    await page.fill('textarea', msg);
    await page.click('button:has-text("Ask")').catch(() => page.click('button svg')); // Send button

    console.log("Message sent. Waiting for response...");
    await page.waitForTimeout(5000); // Wait for stream/response

    // Check the DOM for ComparisonTable and MetricCard
    const hasTable = await page.$('.overflow-x-auto table');
    const hasMetric = await page.$('text="Accuracy"');

    if (hasTable && hasMetric) {
        console.log("SUCCESS: Generative UI components found in the DOM.");
    } else {
        console.log("FAILURE: Components not found.");
        console.log("Table found:", !!hasTable);
        console.log("Metric found:", !!hasMetric);
        // Print the chat content
        const chatContent = await page.textContent('.overflow-y-auto');
        console.log("Chat text:", chatContent.substring(0, 500));
    }

    await browser.close();
})();
