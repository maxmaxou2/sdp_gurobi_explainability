import gurobipy as gp
from gurobipy import GRB

# --- 1. Data Preparation ---
weights = {
    "A": 8,
    "B": 7,
    "C": 7,
    "D": 6,
    "E": 6,
    "F": 5,
    "G": 6
}
grades = {
    'x': {"A": 85, "B": 81, "C": 71, "D": 69, "E": 75, "F": 81, "G": 88},
    'y': {"A": 81, "B": 81, "C": 75, "D": 63, "E": 67, "F": 88, "G": 95},
    'z': {"A": 74, "B": 89, "C": 74, "D": 81, "E": 68, "F": 84, "G": 79},
    't': {"A": 74, "B": 71, "C": 84, "D": 91, "E": 77, "F": 76, "G": 73},
    'u': {"A": 72, "B": 66, "C": 75, "D": 85, "E": 88, "F": 66, "G": 93},
    'v': {"A": 71, "B": 73, "C": 63, "D": 92, "E": 76, "F": 79, "G": 93},
    'w': {"A": 79, "B": 69, "C": 78, "D": 76, "E": 67, "F": 84, "G": 79},
    'w_prime': {"A": 57, "B": 76, "C": 81, "D": 76, "E": 82, "F": 86, "G": 77},
}

candidate_1 = 'y'
candidate_2 = 'z'

grades_1 = grades[candidate_1]
grades_2 = grades[candidate_2]

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
    diff = grades_1[s] - grades_2[s]
    contrib = weights[s] * diff
    deltas[s] = contrib
    
    total_score_u += grades_1[s] * weights[s]
    total_score_v += grades_2[s] * weights[s]

    if contrib > 0:
        pros.append(s)
    elif contrib < 0:
        cons.append(s)
print(deltas)
print(f"Total Score u: {total_score_u}")
print(f"Total Score v: {total_score_v}")
print(f"Delta Pros: {pros}")
print(f"Delta Cons: {cons}")
print(f"Deltas: {deltas}\n")

# --- 2. Gurobi Model for (1-m) Explanation ---
try:
    m = gp.Model("Explanation_m_1")

    # Decision Variables: x[p, c] = 1 if pro p covers con c
    # Note: We create variables for ALL pairs now, because validity depends on the SUM, not individual pairs.
    x = {}
    for p in pros:
        for c in cons:
            x[p, c] = m.addVar(vtype=GRB.BINARY, name=f"match_{p}_{c}")

    m.update()

    # Constraint 1 (Disjoint Pros): Each Pro p is used AT MOST once
    for p in pros:
        m.addConstr(gp.quicksum(x[p, c]
                    for c in cons) <= 1, name=f"pro_disjoint_{p}")

    # Constraint 2 (Cons Coverage): Each Con c must be covered AT LEAST once
    # (Since Pros are disjoint, this ensures it's the target of exactly one trade-off)
    for c in cons:
        m.addConstr(gp.quicksum(x[p, c] for p in pros) >= 1, name=f"cover_{c}")

    # Constraint 3 (Trade-off Strength, m-1): Sum of Pros covering c must dominate c
    for c in cons:
        m.addConstr(
            gp.quicksum(deltas[p] * x[p, c] for p in pros) + deltas[c] >= 0,
            name=f"strength_{c}"
        )
    
    # Objective: Find any feasible solution
    # m.setObjective(0, GRB.MINIMIZE)
    m.setObjective(gp.quicksum(x[p, c]for p in pros for c in cons), GRB.MINIMIZE)
    # Optimize
    m.optimize()

    # --- 3. Output Results ---
    if m.status == GRB.OPTIMAL:
        print("\n--- Explanation Found (Type m-1) ---")

        # We iterate over the Cons, as they are the central element of the trade-off.
        for c in cons:
            assigned_pros = []
            current_sum = deltas[c]

            # Find all Pros assigned to this Con c
            for p in pros:
                if x[p, c].X > 0.5:
                    assigned_pros.append(f"{p}(+{deltas[p]})")
                    current_sum += deltas[p]

            # The Cons are covered exactly once, so this logic is sound
            print(
                f"Trade-off: Con {c} ({deltas[c]}) is covered by {assigned_pros}")
            print(f"  Balance: {current_sum} >= 0")

    elif m.status == GRB.INFEASIBLE:
        print("\nNo (m-1) explanation exists for this comparison.")
        m.computeIIS()
        m.write(f"model_{candidate_1}_{candidate_2}_m1.ilp")
        print("Certificate of infeasibility written to file.")
        
        
except gp.GurobiError as e:
    print(f"Error code {e.errno}: {e}")
