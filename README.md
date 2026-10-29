# Sourcing-Engine-Prototype
Case Study

1. Business Reason

Objective

ShipBob supports thousands of ecommerce brands through a network of 60+ fulfillment centers across the US, Canada, the UK, the EU, and Australia, processing roughly 100 million orders annually. The value of that network depends on the sourcing decision made for each order, and that decision is getting harder: 58.65% of brands already use more than one fulfillment center, and 43.99% plan to add more in 2026.

Our goal is to design an MVP sourcing engine that helps merchants deliver on the date promised to their shoppers while reducing shipping costs. In phase one, the primary objective is to meet the promised delivery date, measured by on-time delivery rate. Within that constraint, the engine selects the lowest-cost option and shows the cost of each decision, so merchants can see the tradeoff.

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

