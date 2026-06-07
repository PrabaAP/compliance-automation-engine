# User Guide · Compliance Automation Engine

A plain-English guide for accounting and advisory staff. No coding needed. If the dashboard is already open in your browser, you are ready to start.

---

## Quick start (about 3 minutes)

1. **Open the dashboard.** Your colleague or IT will have started it; you will see a page titled *Compliance Review Engine* with a sidebar on the left.
2. **Connect your AI** (sidebar step 1). Pick **Groq** from the dropdown (it is free), paste your Groq key, and click **Connect**. A green *Connected* message confirms it worked.
3. **Upload the client file and analyse** (sidebar step 2). Upload the client's profile as a `.txt` file, then click **Analyse Now**. In under a minute the *Latest Report* tab fills in with the client's compliance risks.

That is the whole loop: connect, upload, analyse.

---

## Connecting your AI

The tool does not come with its own AI. You connect one using a key, which is like a password that lets the app talk to an AI service on your behalf. Your key is used only while the app is open and is never saved anywhere.

| Provider | Cost | When to choose it |
|----------|------|-------------------|
| **Groq** | **Free** | The recommended choice. Sign up at console.groq.com, create a key, and you get thousands of free analyses per day. No credit card. |
| **OpenRouter** | Free tier | Another no-cost option. Get a key at openrouter.ai. |
| **Anthropic (Claude)** | Paid | Highest quality. Needs a billed Anthropic account. |
| **OpenAI (GPT-4o)** | Paid | Needs a billed OpenAI account. |
| **Custom** | Varies | For firms with their own AI provider or an internal server. Enter the address and model name your IT team gives you. |

**If you are not sure, choose Groq.** It costs nothing and is fast.

---

## Understanding the results

After an analysis, the **📋 Latest Report** tab shows four things.

- **The three cards at the top** (*Total Risks*, *High Severity*, and *Medium Severity*) give you the headline counts at a glance.
- **The bar chart** lists each risk, coloured by how serious it is: red for HIGH, amber for MEDIUM, green for LOW. Longer red bars are the items to look at first.
- **The expandable risk cards** sit below the chart. Click any one to open it. Each card shows the risk title, the exact CRA reference it relates to, why *this* client is exposed, and a recommended action highlighted in a coloured box.
- **The 📁 Audit Trail tab** keeps a running log of every analysis you have run: the date, client, which AI was used, how many PDFs were read, and how many risks were found. This is your record for quality and review purposes.

Each analysis is also saved automatically as a report file and a short summary, so nothing is lost when you close the app.

---

## How the email works

If your firm has set up the optional n8n automation, the engine can turn each analysis into a client email for you.

- The email lands in your **Gmail Drafts** and is never sent automatically, so you always review and edit before anything goes out.
- It usually appears within about a minute of the analysis finishing.
- The draft opens warmly, lists only the HIGH and MEDIUM risks in plain language, asks one clarifying question per risk, and suggests a 30-minute call. Treat it as a strong first draft, not a final send.

---

## Troubleshooting

**"Connection failed. Check your key and URL."**
The key was mistyped, expired, or has a space at the end. Copy it again from your provider's site and re-paste. For a Custom provider, double-check the base URL and model name too.

**The Analyse button is greyed out.**
You need to connect an AI first. Complete sidebar step 1 and wait for the green *Connected* message.

**"No PDFs found" or the report looks empty.**
The engine needs at least one CRA regulation PDF in the `docs/regulations/` folder. Ask whoever set up the tool to add the relevant CRA documents, then run the analysis again.

**The analysis is slow or times out.**
Free AI services are occasionally busy. Wait a moment and click **Analyse Now** again. Very large PDF sets also take longer to read.

---

## About

Built by **Arun Prabakar Vadaseri Rajendran**, drawing on a background in professional services and advisory work and an IBM certification in data and AI.

LinkedIn: [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)
