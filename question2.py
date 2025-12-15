import gurobipy as gp
from gurobipy import GRB

# --- 1. Data Preparation ---
# Weights from Source 40
weights = {"A": 8, "B": 7, "C": 7, "D": 6, "E": 6, "F": 5, "G": 6}

# Candidates u and v (Source 40)
# u: A=72, B=66, C=75, D=85, E=88, F=66, G=93
# v: A=71, B=73, C=63, D=92, E=76, F=79, G=93
grades_u = {"A": 72, "B": 66, "C": 75, "D": 85, "E": 88, "F": 66, "G": 93}
grades_v = {"A": 71, "B": 73, "C": 63, "D": 92, "E": 76, "F": 79, "G": 93}

# We are explaining why u > v (if u is indeed better)
# Let's calculate deltas
deltas = {}
pros = []
cons = []

print("--- Comparing u vs v ---")
total_score_u = 0
total_score_v = 0

for s in weights.keys():
    # Contribution
    diff = grades_u[s] - grades_v[s]
    contrib = weights[s] * diff
    deltas[s] = contrib
    
    total_score_u += grades_u[s] * weights[s]
    total_score_v += grades_v[s] * weights[s]

    if contrib > 0:
        pros.append(s)
    elif contrib < 0:
        cons.append(s)

print(f"Total Score u: {total_score_u}")
print(f"Total Score v: {total_score_v}")
print(f"Delta Pros: {pros}")
print(f"Delta Cons: {cons}")
print(f"Deltas: {deltas}\n")

# --- 2. Gurobi Model for (1-m) Explanation ---
try:
    m = gp.Model("Explanation_1_m")

    # Decision Variables: x[p, c] = 1 if pro p covers con c
    # Note: We create variables for ALL pairs now, because validity depends on the SUM, not individual pairs.
    x = {}
    for p in pros:
        for c in cons:
            x[p, c] = m.addVar(vtype=GRB.BINARY, name=f"match_{p}_{c}")

    m.update()

    # Constraint 1: Every CON must be covered exactly once
    for c in cons:
        m.addConstr(gp.quicksum(x[p, c] for p in pros) == 1, name=f"cover_{c}")

    # Constraint 2: Trade-off Strength
    # For each Pro, its weight + sum of weights of assigned Cons >= 0
    # (Remember deltas for cons are negative, so we ADD them)
    for p in pros:
        m.addConstr(
            deltas[p] + gp.quicksum(deltas[c] * x[p, c] for c in cons) >= 0,
            name=f"strength_{p}"
        )

    # Objective: Find any feasible solution
    m.setObjective(0, GRB.MINIMIZE)

    # Optimize
    m.optimize()

    # --- 3. Output Results ---
    if m.status == GRB.OPTIMAL:
        print("\n--- Explanation Found (Type 1-m) ---")
        for p in pros:
            assigned_cons = []
            current_sum = deltas[p]
            for c in cons:
                if x[p, c].X > 0.5:
                    assigned_cons.append(f"{c}({deltas[c]})")
                    current_sum += deltas[c]
            
            if assigned_cons:
                print(f"Trade-off: Pro {p} (+{deltas[p]}) covers {assigned_cons}")
                print(f"   Balance: {current_sum} >= 0")
                
    elif m.status == GRB.INFEASIBLE:
        print("\nNo (1-m) explanation exists for this comparison.")
        # Generate Certificate
        m.computeIIS()
        m.write("model_1m.ilp")
        print("Certificate written to model_1m.ilp")

except gp.GurobiError as e:
    print(f"Error code {e.errno}: {e}")
