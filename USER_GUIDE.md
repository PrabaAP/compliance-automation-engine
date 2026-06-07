# User Guide · Compliance Automation Engine

A plain-English guide for accounting and advisory staff. No coding needed.

---

## Quick start (about 3 minutes)

1. **Open the dashboard.** Your colleague or IT will have started it; you will see a page titled *Compliance Analysis Report*. If you are opening the Streamlit Cloud link, a sample report for Meridian Advisory Group loads automatically — you can explore the full dashboard right away without connecting any AI.

2. **Connect your AI** (sidebar step 1). Pick a provider from the dropdown, type the model name your provider gives you, paste your API key, and click **Connect**. A green *Connected* message confirms it worked.

3. **Upload the client file and analyse** (sidebar step 2). Upload the client's profile as a `.txt` file, then click **Analyse Now**. In under a minute the *Latest Report* tab fills in with the client's compliance risks.

That is the whole loop: connect, upload, analyse.

---

## Connecting your AI

The tool does not come with its own AI. You connect one using a key and a model name. The key is like a password that lets the app talk to the AI on your behalf. It is used only while the app is open and is never saved anywhere.

| Provider | Cost | When to choose it |
|----------|------|-------------------|
| **Groq** | **Free** | Recommended starting point. Sign up at console.groq.com — no credit card. Thousands of free analyses per day. |
| **OpenRouter** | Free tier | Another no-cost option. Get a key at openrouter.ai. |
| **Anthropic** | Paid | Claude models. Needs a billed Anthropic account. |
| **OpenAI** | Paid | GPT models. Needs a billed OpenAI account. |
| **Custom** | Varies | For firms with their own AI server. Enter the server address (base URL) and model name your IT team provides. |

**Model name:** Every provider asks you to type the model name you want to use. This keeps the tool future-proof — you are never locked to a specific version. Your provider's documentation or dashboard will show you the exact string to enter (for example Groq lists available models at console.groq.com/docs/models).

**If you are not sure, choose Groq.** It costs nothing and is fast.

---

## Understanding the results

After an analysis, the **Latest Report** tab shows four things.

- **The three cards at the top** (*Total Risks*, *High Severity*, *Medium Severity*) give the headline counts at a glance.
- **The bar chart** lists each risk coloured by how serious it is: red for HIGH, amber for MEDIUM, green for LOW. Longer red bars are the items to look at first.
- **The risk cards** sit below the chart. Each one shows the risk title, the exact CRA reference, why this specific client is exposed, and a recommended action highlighted in a coloured box.
- **The Audit Trail tab** keeps a running log of every analysis you have run: date, client, provider, model, PDFs read, and risks found. This is your record for quality and review purposes.

Each analysis is also saved automatically as a report file and a short summary, so nothing is lost when you close the app.

---

## How the email works

If your firm has set up the optional n8n automation, the engine turns each analysis into a draft client email automatically.

- The email lands in your **Gmail Drafts** and is never sent automatically — you always review and edit before anything goes out.
- It appears within about a minute of the analysis finishing.
- The draft lists only the HIGH and MEDIUM risks in plain language, asks one clarifying question per risk, and suggests a 30-minute call. Treat it as a strong first draft, not a final send.
- **There is no "To" recipient on the draft.** Open it in Gmail, add the client's email address, review the content, and send when ready.

**Setting up your Gmail account in n8n:** This is a one-time step done inside n8n when you first import the workflow. Open the *Gmail — Create Draft* node, click *Add Credential* → *Gmail OAuth2*, and sign in with the Google account you want drafts to appear in. n8n stores only a secure token — not your password. All future drafts land in that account's Drafts folder.

---

## Demo mode

When no analysis has been run yet, the dashboard automatically shows a pre-built sample report for a fictional client called *Meridian Advisory Group Inc.* A blue banner at the top of the page confirms you are viewing demo data. This is what appears on the public Streamlit Cloud link so anyone can explore the tool immediately.

Once you connect your AI and run a real analysis, the live results replace the demo automatically.

---

## Troubleshooting

**"Enter a model name first."**
Every provider requires you to type the model name before connecting. Check your provider's documentation for the exact string to use.

**"Connection failed. Check your key, model name, and URL."**
The key was mistyped or expired, or the model name is wrong for that provider. Copy the key again from your provider's site, double-check the model name, and re-paste both.

**The Analyse button is greyed out.**
You need to connect an AI first. Complete sidebar step 1 and wait for the green *Connected* message.

**"No PDFs found" or the report looks empty.**
The engine needs at least one CRA regulation PDF in `docs/regulations/`. Two sample PDFs are included with the project. For real client work, add your own CRA documents to that folder.

**The analysis is slow or times out.**
Free AI services are occasionally busy. Wait a moment and click **Analyse Now** again. Very large PDF sets also take longer to read.

**The email draft does not appear in Gmail.**
Check that the Gmail credential in n8n is still authorised (Google OAuth tokens can expire). In n8n, open the Gmail node, re-authenticate, and run the workflow again.

---

## About

Built by **Arun Prabakar Vadaseri Rajendran**, drawing on a background in professional services and advisory work and an IBM certification in data and AI.

LinkedIn: [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)
