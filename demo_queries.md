# ClrInsights Working Demo Queries

This document contains a set of structured queries to test the various capabilities of the CLRInsights agent, including its conversational memory (historical context) within the same session and starting fresh in a new session.

## Session 1: General Analysis & Conversational Context
*Test the agent's ability to remember previous questions and refine its queries in a single chat session.*

**Query 1: Initial broad analysis**
> ```text
> What is the overall failure rate for transactions in 2024?
> ```
*(Agent should calculate COUNT(FAILED) / COUNT(*) * 100)*

**Query 2: Follow-up (Contextual Temporal Filter)**
> ```text
> Is it higher on weekends?
> ```
*(Agent should remember it's calculating the failure rate for 2024, and now group it by weekend vs weekday)*

**Query 3: Follow-up (Contextual Categorical Filter)**
> ```text
> What about for just P2P transfers on those weekends?
> ```
*(Agent should remember "it" is failure rate, and filter for P2P transactions during the weekend)*

**Query 4: Follow-up (Visualization based on Context)**
> ```text
> Can you show me a bar chart comparing the failure rates of P2P transfers on weekends versus weekdays?
> ```
*(Agent should recall the entire context and generate a visualization script)*

---

Click **"New Chat"** or clear the session to test isolation.

---

## Session 2: Fresh Context & Complex Aggregations
*Test the agent starting with a blank slate, ensuring no bleed-over from Session 1, and performing complex groupings.*

**Query 1: Multiple Aggregations & Schema Understanding**
> ```text
> What are the peak hours for all transactions during the day, and what's the average amount during those hours compared to non-peak hours?
> ```
*(Agent should use schema guideline: peak hours = 18-21)*

**Query 2: Relational Comparison in P2P**
> ```text
> For P2P transfers, what is the most common sender age group compared to the receiver age group? Is there a pattern?
> ```
*(Tests complex filtering comparing two different categorical columns)*

**Query 3: Follow-up (Contextual Category Drill-down)**
> ```text
> Does this age pattern change if we only look at transactions over 5,000 INR?
> ```
*(Agent should remember the P2P transfer age comparison and add an amount filter)*

---

## Session 3: Anomaly & Fraud Analysis
*Test limits of the data schema knowledge.*

**Query 1: Rule-Based Constraint Application**
> ```text
> Which state has the highest number of transactions flagged for review, and what is the typical amount for these flagged transactions?
> ```
*(Agent should recognize fraud_flag=1 means flagged for review, not confirmed fraud, as per schema notes)*

**Query 2: Follow-up (Correlation)**
> ```text
> Is there any correlation between the device type and the network type used for those flagged transactions?
> ```
*(Agent should remember we are talking about transactions flagged for review in the state from the previous answer, or nationally, depending on how they interpret "those", but must include the fraud flag filter)*

---

## Session 4: Tough Queries & Edge Cases
*Test the agent's ability to handle complex mathematical derivations, edge cases, and multi-step reasoning.*

**Query 1: Complex Multi-step Derivation**
> ```text
> For users aged 26-35 who made P2M transactions, which merchant category had the highest average transaction amount on weekends, and how does that average compare to the overall average for that same merchant category across all days?
> ```
*(This is a very tough query requiring the agent to perform multiple aggregations, handle nulls for P2M, filter by age, filter by weekend, and calculate a baseline to compare against.)*

**Query 2: Missing Data / Schema Edge Case Handling**
> ```text
> What is the receiver age group distribution for Grocery payments where the amount is over 1000?
> ```
*(This is a trick question/edge case. The schema explicitly states `receiver_age_group` is NULL for non-P2P transactions, and Grocery implies P2M. The agent should confidently explain that this data doesn't exist because receiver age groups aren't tracked for merchant payments.)*
