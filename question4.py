import gurobipy as gp
from gurobipy import GRB

# --- 1. Data Preparation ---
weights = {
    "A": 8, "B": 7, "C": 7, "D": 6, "E": 6, "F": 5, "G": 6
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

# --- CANDIDATES (z vs t) ---
candidate_1 = 'z'
candidate_2 = 't'

grades_1 = grades[candidate_1]
grades_2 = grades[candidate_2]

# Calculation of Deltas
deltas = {}
pros = []
cons = []
total_score_1 = 0
total_score_2 = 0

for s in weights.keys():
    diff = grades_1[s] - grades_2[s]
    contrib = weights[s] * diff
    deltas[s] = contrib

    total_score_1 += grades_1[s] * weights[s]
    total_score_2 += grades_2[s] * weights[s]

    if contrib > 0:
        pros.append(s)
    elif contrib < 0:
        cons.append(s)

print(f"--- Comparing {candidate_1} vs {candidate_2} ---")
print(f"Total Delta: {total_score_1 - total_score_2}")
print(f"Delta Pros: {pros}")
print(f"Delta Cons: {cons}")
print(f"Deltas: {deltas}\n")

# A sufficiently large number for Big-M constraints.
M = sum(abs(deltas[s]) for s in weights.keys()) + 1

# --- 2. Gurobi Model for Combined (1-m) and (m-1) Explanation ---
try:
    m = gp.Model("Explanation_Combined_Final")
    m.setParam('OutputFlag', 0)

    # --- DECISION VARIABLES ---
    # x[p, c]: Pro p is associated with Con c (universal matching)
    x = m.addVars(pros, cons, vtype=GRB.BINARY, name="match")

    # y[c]: Con c is covered by (m-1) trade-off (1) or (1-m) trade-off (0)
    y = m.addVars(cons, vtype=GRB.BINARY, name="type_m1")

    # z[p]: Pro p is the SINGLE leader of a (1-m) trade-off (1)
    z = m.addVars(pros, vtype=GRB.BINARY, name="leader_1m")

    m.update()

    # --- CONSTRAINTS ---

    # 1. Pro Disjointness (Universal): Each Pro p is used AT MOST once
    for p in pros:
        m.addConstr(gp.quicksum(x[p, c]
                    for c in cons) <= 1, name=f"pro_disjoint_{p}")

    # 2. Cons Coverage (Universal): Each Con c must be covered AT LEAST once
    # Cette contrainte assure que chaque Con participe à un trade-off.
    for c in cons:
        m.addConstr(gp.quicksum(x[p, c] for p in pros) >= 1, name=f"cover_{c}")

    # --- M-1 LOGIC (If y[c]=1) ---

    # 3. Strength Constraint M-1: If c is m-1 type (y[c]=1), its covering Pros must satisfy strength
    # Sum(Delta_p * x[p,c] for p) + Delta_c >= 0 if y[c]=1.
    for c in cons:
        m.addConstr(
            gp.quicksum(deltas[p] * x[p, c]
                        for p in pros) + deltas[c] >= M * (y[c] - 1),
            name=f"strength_m1_{c}"
        )

    # --- 1-M LOGIC (If y[c]=0) ---

    # 4. Pro Leader Definition (z[p]): If Pro p is used for ANY 1-m Con, it MUST be a leader.
    # sum(x[p,c] * (1-y[c])) <= M * z[p].
    for p in pros:
        m.addConstr(
            gp.quicksum(x[p, c] * (1 - y[c]) for c in cons) <= M * z[p],
            name=f"leader_def_{p}"
        )

    # 5. Cons Coverage Link 1-M: If Pro p is a leader (z[p]=1), ALL Cons c it covers MUST be 1-m type (y[c]=0).
    # x[p, c] + y[c] <= 1 + (1 - z[p])
    for p in pros:
        for c in cons:
            m.addConstr(
                x[p, c] + y[c] <= 1 + (1 - z[p]),
                name=f"con_type_link_{p}_{c}"
            )

    # 6. Strength Constraint 1-M: If Pro p is a leader (z[p]=1), its strength must cover ALL its assigned Cons.
    # Delta[p] + sum(Delta[c] * x[p,c] for c in Cons) >= 0 if z[p]=1.
    for p in pros:
        m.addConstr(
            deltas[p] + gp.quicksum(deltas[c] * x[p, c]
                                    for c in cons) >= M * (z[p] - 1),
            name=f"strength_1m_{p}"
        )

    # Objective: Find any feasible solution (Minimal solution is found if multiple exist)
    m.setObjective(gp.quicksum(z[p] for p in pros) +
                   gp.quicksum(y[c] for c in cons), GRB.MINIMIZE)

    # Optimize
    m.optimize()

    # --- 3. Output Results ---
    if m.status == GRB.OPTIMAL:
        print("\n--- Explanation Found (Combined 1-m and m-1) ---")

        # 1. Output (m-1) trade-offs
        print("\n--- M-1 Trade-offs ---")
        m1_cons = [c for c in cons if y[c].X > 0.5]
        if m1_cons:
            for c in m1_cons:
                assigned_pros = []
                current_sum = deltas[c]

                for p in pros:
                    if x[p, c].X > 0.5:
                        assigned_pros.append(f"{p}(+{deltas[p]})")
                        current_sum += deltas[p]

                print(
                    f"Trade-off (m-1): Con {c} ({deltas[c]}) is covered by {assigned_pros}")
                print(f"  Balance: {current_sum:.2f} >= 0")
        else:
            print("No (m-1) trade-offs used.")

        # 2. Output (1-m) trade-offs
        print("\n--- 1-M Trade-offs ---")
        m1_leaders = [p for p in pros if z[p].X > 0.5]
        if m1_leaders:
            for p in m1_leaders:
                assigned_cons = []
                current_sum = deltas[p]

                for c in cons:
                    if x[p, c].X > 0.5:
                        assigned_cons.append(f"{c}({deltas[c]})")
                        current_sum += deltas[c]

                print(
                    f"Trade-off (1-m): Pro {p} (+{deltas[p]}) covers {assigned_cons}")
                print(f"  Balance: {current_sum:.2f} >= 0")
        else:
            print("No (1-m) trade-offs used.")

    elif m.status == GRB.INFEASIBLE:
        print("\nNo combined (1-m) or (m-1) explanation exists for this comparison.")
        m.computeIIS()
        m.write(f"model_{candidate_1}_{candidate_2}_combined_final.ilp")
        print("Certificate of infeasibility written to file.")

except gp.GurobiError as e:
    print(f"Error code {e.errno}: {e}")
