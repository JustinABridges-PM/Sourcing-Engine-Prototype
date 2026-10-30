# Sourcing-Engine-Prototype
Case Study

1.0 OVERVIEW
ShipBob supports thousands of ecommerce brands through a network of 60+ fulfillment centers across the US, Canada, the UK, the EU, and Australia, processing roughly 100 million orders annually. The value of that network depends on the sourcing decision made for each order, and that decision is getting harder: 58.65% of brands already use more than one fulfillment center, and 43.99% plan to add more in 2026.

1.1 PROBLEM STATEMENT 
When an order is placed, the sourcing decision determines whether the shopper receives it on the promised date and what the merchant pays to ship it. With multiple fulfillment centers, an order can be assigned to one that cannot meet the promised date, or to one that meets it at a higher cost than necessary. Merchants have little visibility into why a fulfillment center was chosen or what the alternative would have cost.

1.2 CUSTOMER
Primary customer: Merchants (the brands ShipBob fulfills for). Merchants make the delivery promise to their shoppers, so they depend on the sourcing engine to make that promise achievable and to show what it costs. Reliable delivery dates at a controlled shipping cost build merchant trust in ShipBob.
Secondary customer: Supply chain systems and operations teams. Downstream systems execute the sourcing decision, and operations teams act on orders the engine flags as at risk, which requires enough lead time to resolve them before the promised date.
End customer: Shoppers who are given a delivery date at checkout and expect to receive their order on it.

1.3 GLOSSARY 
| **Capacity-Based Routing** | Deprioritize an FC that has hit its daily order limit. |
| **EDD** | Estimated date of delivery. |
| **Fully Splittable** | The order has no restrictions on how many packages or fulfillment locations it can be filled from. |
| **In-Region Fulfillment** | An order fulfilled from an FC in the same region as the shopper. |
| **On-Time Delivery Rate** | Share of orders delivered on or before the promised date. |
| **Partially Splittable** | Certain criteria allow the order to be split and fulfilled from multiple places. |
| **Promised Delivery Date** | The date shown to the shopper at checkout. |
| **Ranked Sourcing** | A merchant-defined ordering of which FCs to try first. |
| **Rule Cascade** | Criteria applied in order, each acting as a tiebreaker for the one before. |
| **Ship Alone** | The item cannot be shipped with anything else, usually due to size or weight. |
| **Ship as Is** | The item can ship in the container it is already packaged in. |
| **Shipping Zone** | A distance-based pricing band between the shipping origin and destination. |
| **Ship-Together Constraint** | Items must ship in the same package or from the same node. |
| **Single-Node Fulfillment** | The whole order ships from one location. |
| **SLA** | A fixed service commitment, such as shipping within a set number of days. |
| **Sourcing / Order Routing** | The decision of which FC ships an order. |
| **Split Shipment** | One order fulfilled from more than one location. |
| **Unsplittable** | An order that must be sourced as a single package, no matter what. |


1.4 GOALS (SCOPE)
- Primary: Meet the promised delivery date, measured by on-time delivery rate.
- Secondary: Within that constraint, select the lowest-cost option.
- Show the cost of each decision, including the cheapest feasible alternative, so merchants can see the tradeoff.
- Make every decision explainable, including why other FCs were rejected.
- Handle hard cases: an FC out of stock, and two orders competing for the last unit.
- Work across merchants of different sizes, validated by sample data with varied order volumes and FC footprints.
- (Proposed) Flag orders that no FC can deliver on time, early enough for the supply chain team to act.

1.5 NON-GOALS (OUT OF SCOPE)
- Split shipments will be excluded.
- Live carrier rates will not be looked up
- Inventory transfers between FC will not be used.
- No international shipping
- 

2.0 CURRENT PROBLEM
2.1 Current-State Example
We will assume a facility in PHX arizona, Dallas Texas, and Atlanta Georgia. Each facility has equal capacity to handle orders and equal amount of inventory. 

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
