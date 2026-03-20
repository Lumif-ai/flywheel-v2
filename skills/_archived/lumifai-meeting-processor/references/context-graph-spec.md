# Context Graph Specification

Interactive knowledge graph visualizing relationships across all Lumif.ai expert interviews.

## Node Types

| Type | Color | Size Rule | Properties |
|------|-------|-----------|-----------|
| Person | #60a5fa (blue) | 8 + severity*2.5 | company, severity, sentiment, date, warm(bool) |
| Company | #34d399 (green) | 12 fixed | category |
| Problem | #f87171 (red) | 10 + frequency*4 | severity(avg), frequency, painkiller(bool) |
| ICP | #fbbf24 (yellow) | 12 + validations*4 | status, validations(count) |
| Product | #a78bfa (purple) | 28 fixed, glow filter | label only (P1, P2, P3) |
| Research | #fb923c (orange) | 10 fixed | status (queued/in_progress/done) |
| Competitor | #94a3b8 (gray) | 10 + mentions*2 | times_mentioned, competes_with |

## Edge Types

| Edge | Meaning |
|------|---------|
| works_at | Person → Company |
| described | Person → Problem |
| relevant_to | Person → Product |
| referred | Person → Person (referral chain) |
| co_interviewed | Person → Person (group call) |
| follow_up | Person → Person (same person, later call) |
| experienced_by | Problem → ICP |
| target_for | ICP → Product |
| investigates | Research → Problem |
| competes_with | Competitor → Product |

## JSON Schema (`context-graph.json`)

```json
{
  "nodes": [
    {
      "id": "person-1",
      "type": "person",
      "label": "John Smith",
      "company": "ABC Insurance",
      "severity": 4,
      "sentiment": "positive",
      "date": "2026-03-03",
      "warm": true
    },
    {
      "id": "problem-1",
      "type": "problem",
      "label": "Manual COI verification",
      "severity": 4.2,
      "frequency": 3,
      "painkiller": true
    }
  ],
  "edges": [
    {"source": "person-1", "target": "company-1", "type": "works_at"}
  ],
  "metadata": {
    "last_updated": "2026-03-03",
    "total_interviews": 1,
    "total_nodes": 6,
    "total_edges": 5
  }
}
```

## Updating Rules

1. Read existing JSON (or create fresh with 3 Product nodes + hypothesis ICPs)
2. Add new nodes for new people, companies, problems, ICPs, research, competitors
3. Add edges for all relationships in this call
4. **Deduplicate problems:** If same problem label exists, increment `frequency` and
   recalculate `severity` as running average. Do NOT create duplicate nodes.
5. **Deduplicate competitors:** Same as problems — increment `times_mentioned`
6. **Link referrals:** Person A referred Person B → "referred" edge
7. **Link follow-ups:** Same person, later date → "follow_up" edge between person nodes
8. Update `metadata` counts
9. Save JSON

## D3 Visualization (`context-graph.html`)

Generate an interactive force-directed graph using D3.js (v7). Requirements:
- Color nodes by type (use color scheme above)
- Size nodes by their size rule
- Warm lead persons get gold stroke ring
- Product nodes get glow filter
- Show edge labels on hover
- Hover on any node: highlight connected nodes, dim unconnected
- Filter buttons by node type (left sidebar)
- Zoom and drag support
- Legend at bottom
- Stats bar at top (interviews, problems, ICPs, warm leads)
- Light theme matching Lumif.ai design system (see `references/design-system.md`)

Link force distances: works_at=50, target_for=120, others=90.
Charge: products=-400, others=-180.

Regenerate the HTML each time the JSON is updated.
