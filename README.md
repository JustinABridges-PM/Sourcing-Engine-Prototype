# Sourcing-Engine-Prototype
Case Study

1.0 OVERVIEW
ShipBob supports thousands of ecommerce brands through a network of 60+ fulfillment centers across the US, Canada, the UK, the EU, and Australia, processing roughly 100 million orders annually. The value of that network depends on the sourcing decision made for each order, and that decision is getting harder: 58.65% of brands already use more than one fulfillment center, and 43.99% plan to add more in 2026.

1.1 PROBLEM STATEMENT 
When an order is placed, the sourcing decision determines whether the shopper receives it on the promised date and what the merchant pays to ship it. With multiple fulfillment centers, an order can be assigned to one that cannot meet the promised date, or to one that meets it at a higher cost than necessary. Merchants have little visibility into why a fulfillment center was chosen or what the alternative would have cost.

1.2 CUSTOMER
Primary customer: Merchants (the brands ShipBob fulfills for). [Add 1-2 sentences on why: the engine must give the merchant reliable delivery dates and visibility into cost tradeoffs.]
Secondary customer: [Supply chain / operations teams. Add: they need enough lead time to resolve at-risk orders before the promised date is missed.]
End customer: Shoppers who receive the order on the promised date.

1.3 GLOSSARY (drafted)
FC: Fulfillment center.
Sourcing / order routing: The decision of which FC ships an order.
Promised delivery date: The date shown to the shopper at checkout.
EDD: Estimated date of delivery.
SLA: A fixed service commitment, such as shipping within a set number of days.
On-time delivery rate: Share of orders delivered on or before the promised date.
Shipping zone: A distance-based pricing band between the shipping origin and destination.
In-region fulfillment: An order fulfilled from an FC in the same region as the shopper.
[Add any terms used later.]

1.4 GOALS (SCOPE) (drafted)
- Primary: Meet the promised delivery date, measured by on-time delivery rate.
- Secondary: Within that constraint, select the lowest-cost option.
- Show the cost of each decision, including the cheapest feasible alternative, so merchants can see the tradeoff.
- Make every decision explainable, including why other FCs were rejected.
- Handle hard cases: an FC out of stock, and two orders competing for the last unit.
- Work across merchants of different sizes, validated by sample data with varied order volumes and FC footprints.
- (Proposed) Flag orders that no FC can deliver on time, early enough for the supply chain team to act.

1.5 NON-GOALS (OUT OF SCOPE)
[List what the MVP deliberately excludes and why. Candidates to consider: split shipments, live carrier rate lookups, inventory rebalancing across FCs, international routing, real-time inventory sync.]

2.0 CURRENT PROBLEM
2.1 Current-State Example
[One concrete order: what the shopper was promised, which FC was chosen, what went wrong or cost more than necessary.]

2.2 Business Value
[Quantify what better routing is worth. Candidate figures: Inventory Placement Program merchants saw a 15% reduction in shipping zones and a 16% increase in in-region fulfillment in 2025.]

3.0 PROPOSED SOLUTION
3.1 Inputs and Data Contracts
Input / Owner / What happens when it is wrong
- Order (client ordering system): [owner] / [failure behavior]
- Carrier rates and transit times (carrier system): [owner] / [failure behavior]
- Item catalog (SKU, dimensions, weight): [owner] / [failure behavior]
- Inventory by FC: [owner] / [failure behavior]
- Boxing / package selection: [owner] / [failure behavior]

3.2 Decision Flow
[Ordered rules, for example: 1) exclude FCs that cannot fulfill; 2) exclude FCs that cannot meet the promised date; 3) rank remaining FCs by cost; 4) record the explanation. Add what happens when no FC qualifies.]

3.3 Edge Cases
- FC out of stock: [behavior]
- Two orders competing for the last unit: [behavior]
- No FC can meet the promised date: [behavior]
- [Other cases]

3.4 Advanced / Future State
[What you would build before this reaches a real merchant.]

4.0 SUCCESS METRICS
- Primary: On-time delivery rate. Target: [x%]
- Secondary: Shipping cost reduction versus [baseline to decide]
- Supporting: Share of at-risk orders flagged before the promised date
- Kill threshold: [condition under which you would stop or roll back]

5.0 ASSUMPTIONS AND SHORTCUTS
[Everything fabricated or simplified in the prototype, and why.]

6.0 OPEN QUESTIONS
[Unresolved items. Known so far: cost-reduction baseline; how the promised date interacts with ShipBob's existing delivery-date product.]




Assumptions 
  Operational Landscape: 
    -Since we know that clients are looking to have minimum 2 locations of freight stored and almost half plan to add more. With that in mind, we will assume freight is stored at multiple locations between the range of 2-4. We will go with 3 for the sake of design. 
    -The US will be split the US into West, Central, and East and set a warehouse representing each region.
    -Order ingestion per building will be assumed to be around the same average. For initial scope we will say 60k a day. 
    -Expectation is that the average order will take 2 hours to process so we should not drop orders in after this window. 
  Carrier Contracts
    -Carrier contracts across the national brands will be considered to all have the same available options. 
    -Carriers across regional brands will be considered to all have the same available options. 
  Limitations
    -We will focus the roll out within the united states and phase the north american region (Mexico / Canada) as phase 2. With full international being phase 3. 
  
Who are the stakeholders
  -Clients ordering system: 
  -Carrier system
  -Label Generation
  -WMS
  -Inventory 
  -Item Catalog
Metrics
  -Internal Metrics
  -Client Metrics
  -Downstream metrics to monitor

3. Design
Requirements
  -We must provide an accurate and achievable Promised Delivery Date to the end customer.
Customer
User stories

5. Test
Standard Use Case (1st 
1. Single line Unit
2. Single Line multi unit
3. Multi Line Multi Unit
4. 
Exception scenarios
1. Inventory shorted to 0 in building 1 and needs to reshop to building 2
2. 

