# Linear Programming Modeling Recipe: Dorfman-Samuelson-Solow (1958) Framework and Tow's Method (1999)

**Target Audiences:**
1. **DORA Autonomous Agent:** Operational rules and validation checks to translate informal business descriptions into mathematical programs.
2. **Domain Packages:** Reusable modeling templates for agriculture, sawmills/manufacturing, chemicals, and logistics.
3. **Analysts:** Reference guide for microeconomic modeling with linear programming.

---

## 1. Conceptual Foundations of Dorfman, Samuelson, and Solow

Dorfman, Samuelson, and Solow (DSS) ground linear programming in the microeconomics of enterprise production (DSS, Chap. 6, pp. 130–165).

### 1.1. The Engineer's Perspective vs. Smooth Production Functions
- Neoclassical economic theory relies on continuous, differentiable production functions ($Q = f(K, L)$) (DSS, p. 131).
- In actual plant operations, management choices are not infinitesimal tradeoffs of inputs, but selections among distinct "ways of doing things" (DSS, p. 132).
- A **process** or **activity** is a fixed technical ratio between input consumption rates and output production rates per unit of operational intensity (DSS, p. 132).
- Factor and product substitution arises from operating two or more discrete processes in parallel at varying intensities (DSS, p. 133).
- The **production possibilities frontier** is a piecewise-linear convex polyhedron whose extreme vertices represent pure technical processes (DSS, Chap. 2, pp. 33–38; Chap. 6, pp. 133–136).

### 1.2. The Four Assumptions of the Linear Model
Representing a system as a linear program requires four empirical conditions (DSS, pp. 132–134):
1. **Proportionality:** Constant returns to scale hold for each process individually. Doubling operational scale doubles inputs and outputs (DSS, p. 132).
   - *Deviations noted by the authors:* In agricultural operations, proportionality is an approximation. Crop yields vary near field boundaries compared to the center; transit times across parcels do not scale linearly with acreage; and fencing length grows with the perimeter (proportional to the square root of area), rather than linearly with area (DSS, p. 132, items 1–4).
2. **Additivity:** When multiple processes run concurrently, total inputs and total outputs equal the direct algebraic sum of inputs and outputs of each process, without unmodeled technical interferences or synergies (DSS, p. 133).
3. **Divisibility:** Activity levels $x_j$ can take any non-negative continuous real value ($x_j \ge 0$) (DSS, p. 133).
4. **Finiteness:** The number of available technological processes is finite and discrete (DSS, p. 133).

---

## 2. Systematic Comparison: DSS (1958) vs. Tow (1999)

Fernando Tow developed an operational five-step method for linear formulation (Tow, 1999, pp. 18–20).

### Comparison Matrix

| Step in Tow (1999, pp. 18–20) | DSS Formulation (1958) | Differences and Complements |
|---|---|---|
| **1. Identify activities** ($x_j$) | Definition of processes $P_j$ and activity levels $x_j$ (DSS, p. 132). | DSS explicitly separates physical transformation processes from commercial purchasing and selling activities (DSS, pp. 142–143). |
| **2. Identify items** | Net output vector $y$ (DSS, pp. 142–146). | DSS splits items into fixed factor capacities (utilization $\le 100\%$) and intermediate products (net balance $= 0$) (DSS, p. 145). |
| **3. Input-output coefficients** ($a_{ij}$) | Technology matrix $A$ across process columns (DSS, pp. 143–145). | Full agreement on the Dantzig matrix tableau format (DSS, p. 143; Tow, p. 24). |
| **4. External flows** ($b_i$) | Limitation vector $s$ (DSS, p. 145). | DSS integrates internal equipment limits and external sales bounds in a unified restriction vector (DSS, p. 145). |
| **5. Balance equations and Objective** | System $y = Ax \ge s$ and $\max Z = c'x$ (DSS, p. 145). | DSS integrates shadow price theory for internal accounting valuation and managerial control (DSS, Chap. 3 and Chap. 7). |

### Points of Agreement
1. **Activity $\times$ Item Tableau:** Both organize models with decision activities in columns and items in rows (DSS, p. 143; Tow, p. 24).
2. **Universal Balance Equations:** Every physical resource, intermediate good, or cash account requires an explicit accounting row (DSS, p. 145; Tow, p. 20).
3. **Intermediate Goods:** Both Tow's grain storage model (Tow, pp. 23–24) and DSS's chemical plant (DSS, pp. 141–151) require intermediate generation to balance internal consumption plus external sales.
4. **Economic Interpretation of Duality:** Dual variables represent factor rents and marginal opportunity costs of bottlenecks (DSS, pp. 39–45, 174–178; Tow, pp. 48–60).

### What DSS Adds
1. **Strict Distinction Between Intermediate Items and Capacities:** In the chemical plant model, intermediate chemicals $C_1, C_2, C_3$ have zero bounds ($y_k = 0$), while equipment units $E_1 \dots E_4$ carry capacity limits ($s_i = -100$) (DSS, p. 145).
2. **Limits of Price Decentralization:** DSS show that shadow prices alone are insufficient to coordinate decentralized shop-floor operations (DSS, pp. 61–63, 170–172). At the optimum, all active processes yield zero imputed profit; prices tell managers what *not* to produce, but do not dictate optimal production volumes. Furthermore, decentralized trial-and-error price adjustments oscillate around equilibrium rather than settling directly (DSS, p. 63). Central quantitative balance targets remain necessary (DSS, p. 61).
3. **Spatial Economics in Transportation:** DSS formalize how freight tariffs determine spatial price differentials and basing-point pricing systems via dual variables (DSS, Chap. 5, pp. 106–127).

### Common Modeling Errors Identified by DSS
1. **Defining Variables by Product Instead of Process:** If a product can be manufactured via two alternative technologies, grouping them into a single variable eliminates technological choice (DSS, p. 132).
2. **Temporal Inconsistency:** Combining monthly machine ratings with hourly rates or annual demand figures (DSS, p. 145).
3. **Omitting Intermediate Balance Rows:** Omitting balance equations linking sequential production stages, allowing solvers to create inputs from nothing (DSS, p. 145).
4. **Overlooking Ancillary Bottlenecks:** Modeling primary machines while ignoring auxiliary storage, drying, or power constraints (DSS, p. 145).
5. **Extrapolating Shadow Prices Beyond Basis Limits:** Shadow prices remain constant only within the resource variation interval that preserves the optimal basis (DSS, pp. 180–183).

---

## 3. The Agent's Step-by-Step Modeling Guide

### Step 1: Establish Time Horizon
Set a single planning period for all rates, capacities, and demands (e.g., month, fortnight, or crop year) (DSS, p. 145).

### Step 2: Catalog Items (Rows)
Classify each item into five categories (DSS, pp. 142–146; Tow, pp. 19–20):
1. **Fixed capacities and equipment:** Machine-hours, reactor capacities, land acreage.
2. **Purchased inputs:** Externally procured raw materials and utilities.
3. **Intermediate items:** Internally produced items consumed downstream or sold.
4. **Final goods:** Finished products delivered to external buyers.
5. **Financial items:** Cash flow balances and credit facilities.

### Step 3: Catalog Activities (Columns)
Define decision variables $x_j \ge 0$ (DSS, pp. 142–143; Tow, p. 19):
1. Physical transformation processes.
2. Procurement activities.
3. Commercial sales activities.
4. Storage and temporal transfer activities.
5. Financing and credit drawdowns.

### Step 4: Construct Technology Matrix ($a_{ij}$) and Sign Convention
DSS applies a single accounting convention (DSS, p. 143, Table 6-4; p. 145, Eq. 6-2):
- **Item consumption:** Negative coefficient ($-a_{ij}$).
- **Item production:** Positive coefficient ($+a_{ij}$).
- **Canonical matrix restriction:**
  $$y = Ax \ge s$$
  where $y$ is the net output vector and $s$ is the external bound vector.
  - Intermediate goods in equilibrium: $y_k = 0$ (or $\ge 0$).
  - Fixed equipment capacities: $s_i = -100$ (maximum 100% capacity utilization).
  - *DSS Example (Chap. 6, p. 145, equipment $E_2$):*
    $$y_5 = -5x_1 - 4x_2 - 2x_3 + 0x_4 + 0x_5 + 0x_6 \ge -100$$
- **Standard spreadsheet and solver translation:**
  Multiplying by $-1$, the inequality is expressed as "consumption $\le$ capacity" with positive coefficients:
  $$5x_1 + 4x_2 + 2x_3 \le 100$$

### Step 5: Specify External Bounds ($b_i$)
Set right-hand side parameters: factor availability caps, delivery obligations, and zero balances for intermediates (DSS, p. 145; Tow, p. 20).

### Step 6: Formulate Objective Function
Define total net margin maximization or operating cost minimization, assigning unit margin $c_j$ to each activity (DSS, p. 145; Tow, p. 20).

---

## 4. Critical Validation Checks

The agent must run these checks before and after solving (DSS, pp. 145–147, 174–178; Tow, p. 20):

1. **Row Unit Consistency:** In each row $i$, $\text{Unit}(a_{ij}) \times \text{Unit}(x_j) = \text{Unit}(b_i)$ (DSS, p. 145).
2. **Explicit Non-Negativity:** $x_j \ge 0$ for all physical and economic activities (DSS, p. 145).
3. **Intermediate Closure:** Every intermediate good must have at least one supply activity ($a_{ij} > 0$) and one consumption or sales activity ($a_{ik} < 0$) (DSS, p. 145).
4. **Boundedness:** Every activity with positive unit margin must consume at least one bounded resource (DSS, p. 145).
5. **Network Flow Conservation:** Total network supply must equal or exceed total destination demand (DSS, Chap. 5, p. 107).
6. **Complementary Slackness Verification (DSS, pp. 174–178):**
   - If a resource constraint has slack ($b_i - \sum a_{ij} x_j^* > 0$), its shadow price must equal zero ($u_i^* = 0$).
   - If a shadow price is positive ($u_i^* > 0$), the capacity must be fully exhausted ($\sum a_{ij} x_j^* = b_i$).
   - If an activity is unused ($x_j^* = 0$), its imputed cost must be greater than or equal to its unit revenue ($\sum u_i^* a_{ij} \ge c_j$).
   - If an activity is used ($x_j^* > 0$), its imputed cost must exactly equal its unit revenue ($\sum u_i^* a_{ij} = c_j$).

---

## 5. Condensed Modeling Recipe (max. 600 words)

### Operational Modeling Steps

1. **Time Horizon:** Set a single, consistent time horizon for all flows, capacities, and requirements (month, fortnight, or year) (DSS, p. 145).
2. **Item Catalog (Rows):** Group all items into five categories: equipment capacities, purchased inputs, intermediate items, finished goods, and financial accounts (DSS, pp. 142–146; Tow, pp. 19–20).
3. **Activity Menu (Columns):** Define decision variables $x_j \ge 0$ for each production technology, raw material purchase, product sale, storage transfer, and loan tranche (DSS, pp. 142–143; Tow, p. 19).
4. **Technology Matrix & Sign Convention:**
   - In DSS canonical form ($y = Ax \ge s$), consumption carries a negative sign and production a positive sign (DSS, p. 145). For equipment $E_2$: $-5x_1 - 4x_2 - 2x_3 \ge -100$.
   - In spreadsheet/solver format, express "consumption $\le$ capacity" with positive coefficients: $5x_1 + 4x_2 + 2x_3 \le 100$.
   - For intermediate goods, enforce zero net balance: internal production minus internal consumption minus sales $= 0$ (DSS, p. 145; Tow, p. 24).
5. **External Bounds:** Define right-hand side bounds ($b_i$): market quotas, facility capacities, and minimum demand targets (DSS, p. 145; Tow, p. 20).
6. **Objective Function:** Maximize total net margin by assigning each activity its unit sale price, direct variable cost, or purchase cost (DSS, p. 145; Tow, p. 20).

### Mandatory Sanity Checks

1. **Units:** Verify that all terms in a row sum in the exact physical or monetary unit of the right-hand side (DSS, p. 145).
2. **Intermediate Closure:** Confirm that every intermediate good has both a source and a sink (DSS, p. 145).
3. **Boundedness:** Confirm that no profitable activity can expand infinitely without exhausting a scarce resource (DSS, p. 145).
4. **Complementary Slackness:** In the optimal solution, verify that unused capacity has a zero shadow price, and active processes exactly match their imputed costs (DSS, pp. 174–178).
5. **Limits of Dual Prices:** Remember that shadow prices identify bottlenecks and opportunity costs, but cannot coordinate decentralized production volumes without central physical quotas (DSS, pp. 61–63, 170–172).
