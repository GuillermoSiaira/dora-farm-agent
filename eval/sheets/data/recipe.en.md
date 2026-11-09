# Modelling Recipe for Linear Programming in Spreadsheets

This methodological guide teaches how to formulate linear programming models for spreadsheets, based on the microeconomic modelling framework of Fernando V. Tow (*Linear Programming as a Microeconomic Modelling Tool*, Ediciones Macchi, Buenos Aires, 1999, pp. 18–20 and 48–60).

---

## Part 1: The Primal — Five-Step Method (Tow, pp. 18–20)

To build the primal spreadsheet model, organize the problem into an activities-by-items matrix following these five sequential steps:

### Step 1: Activities (Decision Variables $x_j$)
Identify the quantitative decisions to be determined by the optimizer.
- Each activity corresponds to a column in the spreadsheet (decision cells range, e.g. `B5:E5`).
- Examples: hectares allocated to each crop, tons sold at harvest, tons stored in silos, livestock units raised, units shipped or manufactured.
- Always initialize decision variable cells with `0` in the spreadsheet.

### Step 2: Items, Factors, and Material Balances (Constraints $i$)
Identify the scarce production factors, physical capacities, financial funds, or material conservation balances.
- Each item corresponds to a row in the spreadsheet.
- Examples: available land (ha), labour supply (hours), storage capacity (tons), harvested grain allocation, own working capital or credit lines (USD), agronomic rotation caps.

### Step 3: Input-Output Coefficients ($a_{ij}$)
Determine the rate of consumption or production per unit of activity for each item.
- Input (consumption): if the activity absorbs the factor (e.g., 1 ha of corn uses 1 ha of land, 2 hours of labour, 600 USD of working capital).
- Output (production): if the activity yields an intermediate good (e.g., 1 ha of corn produces 6 tons of grain).
- Sign convention: resources consumed appear on the left-hand side with a positive sign; items produced by internal activities reduce net requirements or balance out destinations.

### Step 4: External Endowments and Requirements ($b_i$)
Specify the exogenous limits or requirements originating from outside the enterprise (the right-hand side or RHS of each constraint row).
- Resource endowments: total owned land $\le 100$ ha; available working capital $\le 260,000$ USD; silo capacity $\le 300$ tons.
- Minimum demand requirements: required delivery at port $\ge 250$ tons; minimum dietary nutrient intake $\ge 12$ units.
- Internal transfer balances: grain sold + grain fed $\le$ grain harvested, i.e., $-\text{harvest} + \text{sale} + \text{feed} \le 0$.

### Step 5: Balance Equations and Objective Function
Express the quantitative relationships with linear spreadsheet formulas:
- **Objective Function:** calculate total net margin or cost using `=SUMPRODUCT(variables, margins)` (for maximization) or `=SUMPRODUCT(variables, costs)` (for minimization).
- **Constraints:** in each row, calculate total resource usage with linear formulas (e.g. `=SUM(B5:E5)` or `=SUMPRODUCT(B5:E5, B3:E3)`) and link it to the threshold with `<=`, `>=`, or `=`.

### Mandatory Primal Checklist
1. **Does every item have its balance row?** Ensure no scarce factor or physical flow is omitted.
2. **Are units consistent across each row?** Each row must use a uniform unit of measurement (do not mix kg with tons or months with years).
3. **Did you state non-negativity?** Explicitly include `variables >= 0`. Omitting it allows negative hectares or outputs.
4. **Are there invented numbers?** Every numeric constant must originate directly from the problem statement. If crucial data is missing (capital, rent, demand), **ask the user in `questions_to_user` or explicitly state it in `assumptions`**. Never invent numbers silently!

---

## Part 2: The Dual and Economic Interpretation (Tow, pp. 48–60)

The dual is the economic counterpart of the primal problem expressed in terms of **shadow prices** and resource opportunity costs (Tow, pp. 48–52). It is not solved by hand: the solver computes it by transposing the primal structure.

### Deducing the Dual from the Primal
In Tow's matrix framework, the primal activities (columns) $\times$ items (rows) table is transposed:
1. **One dual variable per primal row ($y_i$):** each primal constraint $i$ receives an imputed shadow price $y_i$, measuring the marginal value of having one additional unit of that resource endowment.
2. **One dual constraint per primal column ($j$):** each primal activity generates an opportunity cost condition: the value of resources consumed by the activity, valued at imputed shadow prices, must at least cover the net revenue generated:
   $$\sum_i a_{ij} y_i \ge c_j \quad (\text{for a maximization primal})$$
3. **Opposite Sense:**
   - If the primal is **maximize**, the dual is **minimize** the total imputed value of endowments: $\min w = \sum_i b_i y_i$.
   - If the primal is **minimize**, the dual is **maximize** the imputed value of requirements: $\max w = \sum_i b_i y_i$.

### Canonical Sign Rules for Prices (Tow, pp. 50–51)
- **Primal `max`:**
  - Constraint $\le$ (scarce resource): $y_i \ge 0$. Adding more resource increases maximum profit.
  - Constraint $\ge$ (quota or minimum requirement): $y_i \le 0$. Imposing a higher quota restricts the feasible space and lowers profit.
  - Constraint $=$ (strict equality balance): $y_i$ is free (unrestricted in sign).
- **Primal `min`:**
  - Constraint $\ge$ (minimum requirement): $y_i \ge 0$. Raising requirements increases total cost.
  - Constraint $\le$ (upper capacity bound): $y_i \le 0$.
  - Constraint $=$: $y_i$ is free.

### Fundamental Theorems and Economic Reading (Tow, pp. 53–57)
- **Strong Duality:** if the primal has a finite optimal solution, the dual also has a finite optimal solution and their objective values match exactly:
  $$\max z = \min w$$
- **Complementary Slackness:**
  - If a resource constraint has positive slack ($b_i - \sum a_{ij} x_j > 0$, abundant resource), its shadow price is strictly zero ($y_i = 0$). Surplus resources have zero marginal value.
  - If a shadow price is strictly positive ($y_i > 0$), the resource is fully exhausted (binding constraint).
  - If an activity is active at a positive level ($x_j > 0$), the imputed cost of inputs equals its unit margin exactly ($\sum a_{ij} y_i = c_j$).
- **Reduced Cost and Indifference Price:**
  - For an inactive activity ($x_j = 0$), the reduced cost is $r_j = c_j - \sum a_{ij} y_i \le 0$. It measures the penalty per unit incurred if the system is forced to produce that activity.
  - The **indifference price** is the minimum market price required to make the activity economically attractive to enter the optimal plan: $P^* = P_{\text{current}} - r_j$.
- **Right-Hand Side Allowable Range (RHS Range):**
  - The interval $[b_i^{\min}, b_i^{\max}]$ over which shadow price $y_i$ remains constant. Beyond this range, the optimal basis changes and the resource takes on a different marginal value.

### Mandatory Dual Checklist
1. **Does every primal constraint have its dual price $y_i$?** Map it using `price_of_row`.
2. **Is the objective sense reversed?** (Minimization for a maximization primal).
3. **Do price sign bounds respect the canonical convention?** ($\ge 0$ for $\le$ constraints in maximization).
4. **Does strong duality hold?** The dual optimal objective must match the primal objective within 0.1%.
5. **Do constraints with slack have a shadow price of zero?**

