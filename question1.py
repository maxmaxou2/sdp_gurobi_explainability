import gurobipy as gp
from gurobipy import GRB

# --- 1. Data Preparation ---
# Grades (from Source 12)
subjects = ["Anatomie", "Biologie", "Chirurgie", "Diagnostic", "Epidemiologie", "Forensic", "Genetique"]
weights = {"Anatomie": 8, "Biologie": 7, "Chirurgie": 7, "Diagnostic": 6, "Epidemiologie": 6, "Forensic": 5, "Genetique": 6}

# Candidate grades (Xavier vs Yvonne)
grades_x = {"Anatomie": 85, "Biologie": 81, "Chirurgie": 71, "Diagnostic": 69, "Epidemiologie": 75, "Forensic": 81, "Genetique": 88}
grades_y = {"Anatomie": 81, "Biologie": 81, "Chirurgie": 75, "Diagnostic": 63, "Epidemiologie": 67, "Forensic": 88, "Genetique": 95}

# Calculate Contributions (deltas)
deltas = {}
pros = []
cons = []

print("--- Contributions ---")
for s in subjects:
    # Contribution = weight * (grade_x - grade_y)
    diff = grades_x[s] - grades_y[s]
    contrib = weights[s] * diff
    deltas[s] = contrib
    
    if contrib > 0:
        pros.append(s)
    elif contrib < 0:
        cons.append(s)
    print(f"{s}: {contrib}")

print(f"\nPros: {pros}")
print(f"Cons: {cons}")

# --- 2. Gurobi Model ---
try:
    # Create a new model
    m = gp.Model("Explanation_1_1")

    # Decision Variables: x[p, c] = 1 if pro p explains con c
    x = {}
    
    # Only create variables for VALID trade-offs (where delta_p + delta_c >= 0)
    # This implicitly handles the "strength" constraint
    for p in pros:
        for c in cons:
            if deltas[p] + deltas[c] >= 0:
                x[p, c] = m.addVar(vtype=GRB.BINARY, name=f"match_{p}_{c}")

    # Update model to integrate variables
    m.update()

    # Constraint 1: Every CON must be covered exactly once
    for c in cons:
        m.addConstr(gp.quicksum(x[p, c] for p in pros if (p, c) in x) == 1, name=f"cover_{c}")

    # Constraint 2: Every PRO can be used at most once
    for p in pros:
        m.addConstr(gp.quicksum(x[p, c] for c in cons if (p, c) in x) <= 1, name=f"use_once_{p}")

    # Objective: Just find a feasible solution. 
    # (Gurobi will try to satisfy constraints. If impossible, it returns Infeasible)
    m.setObjective(0, GRB.MINIMIZE)

    # Optimize
    m.optimize()

    # --- 3. Output Results ---
    if m.status == GRB.OPTIMAL:
        print("\n--- Explanation Found (Type 1-1) ---")
        for p in pros:
            for c in cons:
                if (p, c) in x and x[p, c].X > 0.5:
                    print(f"Trade-off: Because {p} (+{deltas[p]}) compensates for {c} ({deltas[c]})")
    elif m.status == GRB.INFEASIBLE:
        print("\nNo (1-1) explanation exists for this comparison.")
        # Optional: Calculate IIS to see which constraints failed
        m.computeIIS()
        m.write("model.ilp")
        print("Certificate of non-existence written to model.ilp")

except gp.GurobiError as e:
    print(f"Error code {e.errno}: {e}")

except AttributeError as e:
    print("Encountered an attribute error")
