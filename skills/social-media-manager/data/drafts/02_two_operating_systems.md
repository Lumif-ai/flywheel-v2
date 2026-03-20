# Your Startup Has Two Operating Systems
**Series:** The Automation Architect, Week 1, Post 2 (Problem Recognition)
**Pillar:** The Admin Tax
**Status:** DRAFT

---

## HOOK VARIANTS

**Hook A (The Split):**
Your company runs two operating systems. One gets all the engineering. The other runs on Slack messages and prayer.

**Hook B (The Inventory):**
I counted 14 spreadsheets, 9 Slack channels, 3 Notion databases, and a Google Doc called "source of truth (OLD)" running our 22-person company.

**Hook C (The Job Posting):**
We'd never ship a product held together with copy-paste and tribal knowledge. But that's exactly how we run the company that builds the product.

**Hook D (The Observation):**
Every engineer I know would reject a PR with hardcoded values, manual data entry, and no error handling. Then they go update the company's revenue tracker by hand.

---

## LINKEDIN DRAFT (Hook A)

Your company runs two operating systems. One gets all the engineering. The other runs on Slack messages and prayer.

.

OS1 is your product. You know this one. Version controlled. Tested. Monitored. Documented (sometimes). You have engineers who think carefully about architecture, data flow, edge cases. You review each other's work. You refactor when things get messy. You'd never ship something held together with copy-paste and manual data entry.

OS2 is everything else. How deals get tracked. How customers get onboarded. How the board deck gets updated. How hiring pipelines move. How expenses get approved. How anyone knows what happened last quarter.

OS2 runs your company. And OS2 is a disaster.

.

I'm not saying this from the outside. I built our OS2. I'm the one who created the spreadsheet that feeds the other spreadsheet that someone manually copies into the slide deck every month. I set up the Slack channel where customer feedback goes to die. I wrote the Notion doc titled "Process" that three people have read and nobody follows.

At our peak complexity, our 22-person startup had:

14 spreadsheets with overlapping data.
9 Slack channels for ops coordination.
3 Notion databases that were supposed to be one.
A Google Doc called "source of truth" and another called "source of truth (ACTUAL)."
One person (me) who knew how they all connected.

That last part is the real problem.

.

Here's how OS2 evolves at every startup I've seen.

Month 1. Founder tracks everything in one spreadsheet. It works fine.

Month 4. Spreadsheet has 12 tabs. Someone starts a second spreadsheet for a specific function. A Slack channel gets created for "quick updates" that becomes the actual system of record.

Month 8. Three people are maintaining parallel versions of the same data. Nobody's is wrong exactly. They're just different. When the numbers don't match, someone spends an afternoon reconciling.

Month 14. You buy a tool. Salesforce, HubSpot, Monday, whatever. The tool is good. But it doesn't replace the spreadsheets. It becomes layer 4. Now you have the tool AND the spreadsheets AND the Slack channels AND the docs. Someone builds a Zapier connection between two of them. It breaks. Nobody notices for three weeks.

Month 20. A new hire asks "where do I find X?" The answer is always "ask [person's name]."

That's OS2. Not designed. Accumulated.

.

What kills me is the double standard.

I have watched engineers spend four hours debating the right abstraction for a service boundary. Good. That's their job. Clean architecture matters.

Those same engineers then go update a customer tracker by manually copying data from an email into a spreadsheet, then pinging someone in Slack to let them know it's updated, then logging that they pinged in a different spreadsheet.

If you described OS2 as a software system in a technical review, people would walk out of the room.

No version control. Manual data synchronization. Single points of failure everywhere. Undocumented dependencies. No monitoring. No tests. State management via "did you see my Slack message?"

We'd never accept this in our product. We accept it in our company because we don't think of it as a system.

But it is one. A bad one.

.

The cost isn't just inefficiency. It's something worse.

OS2 creates what I've started calling Productive Theater. It's admin work that looks like real work but is actually just re-learning what you already knew.

Example: every Monday, our ops lead compiled a weekly summary. She'd go through Slack, pull out updates, cross-reference with the task tracker, check the CRM for deal movement, and write a narrative. Took about 90 minutes.

The information already existed. In five different places. Her job was to be a human ETL pipeline. Extract, transform, load. Every week. From memory and manual search.

She wasn't producing new knowledge. She was re-assembling old knowledge that had been scattered across OS2 during the previous week.

That's Productive Theater. You feel productive because you're working hard and the output is useful. But you're spending energy on reconstruction, not creation. And you're doing it because OS2 scatters context instead of collecting it.

.

So why doesn't anyone fix OS2?

Three reasons.

First, nobody owns it. OS1 has a CTO, an engineering team, a roadmap. OS2 has... whoever cares enough to maintain the spreadsheet this week. There's no OS2 architect. No OS2 roadmap. No OS2 code review.

Second, each piece of OS2 is small. No single spreadsheet or Slack channel is worth an engineering project. The problem is the aggregate. Fourteen small things connected by tribal knowledge and goodwill.

Third, the people who suffer most from OS2 aren't engineers. They're ops people, founders, customer success managers. People who don't have the vocabulary or political capital to say "we need to engineer our internal operations." That sounds crazy at a 30-person startup. You just use the tools and push through.

.

I think this is actually the root cause of the Admin Tax I wrote about in my last post.

The 60% of time your best people spend on useful-but-wrong-person work? Most of it is OS2 maintenance. Reconciling data. Re-finding context. Manually bridging gaps between tools. Being the human integration layer.

The fix isn't better tools. We've all bought better tools. We have incredible tools. The fix is treating OS2 as a real system that deserves real architecture.

That means: data flows between tools without a human carrying it. Context generated in one workflow is available in the next. Updates propagate instead of getting manually copied. And the knowledge your company generates as a side effect of working doesn't get lost in a Slack thread from six weeks ago.

This is what we're building at lumif.ai. Not a replacement for your tools. An OS2 that actually works like an operating system. But honestly, even just acknowledging that OS2 exists is the first step most teams skip.

.

Go count your spreadsheets. Your Slack channels for ops. Your "source of truth" docs.

That's your OS2. And nobody's engineering it.

How many spreadsheets are running YOUR company?

---

## X / TWITTER VERSION

**Tweet:**
Your company runs two operating systems. OS1 is your product: version controlled, tested, reviewed. OS2 is everything else: 14 spreadsheets, 9 Slack channels, and one person who knows how they connect. We'd never ship OS2 as a product. But we run our companies on it.

**Note:** LinkedIn post link goes in reply.
