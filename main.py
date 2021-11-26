import pandas as pd
import ortools
from ortools.sat.python import cp_model


model = cp_model.CpModel()
solver = cp_model.CpSolver()

df = pd.read_csv("melee_data.csv")


class AbilitySolver:
    START_ADREN = 100
    NUM_ABILITIES = df.shape[0]
    TIME = 10

    def __init__(self, seconds, start_adren):
        self.TIME = int(seconds / 0.6) + 1
        self.START_ADREN = start_adren
        self.x, self.damages, self.names = {}, {}, {}
        self.abils_used = [None for _ in range(self.TIME)]
        self.adren = []

    def init_variables(self):
        """
        Initialize Variables
        """
        self.adren = [
            model.NewIntVar(0, 100, f"Adren at time {t}") for t in range(self.TIME)
        ] + [model.NewConstant(self.START_ADREN)]
        for i in range(self.TIME):
            for j, row in df.iterrows():
                self.x[i, j] = model.NewBoolVar(row["Ability Name"])
                self.damages[j] = row["Damage"]
                self.names[j] = row["Ability Name"]
        for i in range(self.TIME):
            self.abils_used[i] = model.NewIntVar(0, self.NUM_ABILITIES, "")
            model.Add(
                self.abils_used[i]
                == sum(self.x[i, j] for j in range(self.NUM_ABILITIES))
            )

    def add_constraints(self):
        """
        Add constraints to the CP Model
        """
        for i in range(self.TIME):
            for j, row in df.iterrows():
                dur = row["Duration"]

                # Variables x_ij if ability j was used at timestamp i

                # If abil is used, can't use any others for its duration
                for d in range(i + 1, min(i + dur, self.TIME)):
                    model.Add(self.abils_used[d] == 0).OnlyEnforceIf(self.x[i, j])

                c = row["Cooldown"]

                # Ability used only as often as cooldown
                model.Add(
                    sum(self.x[c, j] for c in range(max(i - c + 1, 0), i)) == 0
                ).OnlyEnforceIf(self.x[i, j])

                # Define adren variation depending on the type of ability
                type = row["Type"]

                if type == "Basic":
                    model.Add(self.adren[i] == self.adren[i - 1] + 9).OnlyEnforceIf(
                        self.x[i, j]
                    )

                elif type == "Threshold":
                    model.Add(self.adren[i] == self.adren[i - 1] - 15).OnlyEnforceIf(
                        self.x[i, j]
                    )
                    model.Add(self.adren[i - 1] >= 50).OnlyEnforceIf(self.x[i, j])

                elif type == "Ultimate":
                    model.Add(self.adren[i - 1] == 100).OnlyEnforceIf(self.x[i, j])
                    model.Add(self.adren[i] == 0).OnlyEnforceIf(self.x[i, j])

        for i in range(self.TIME):
            # Ensure at most 1 ability used at any time
            model.Add(self.abils_used[i] <= 1)

            # Ensure adren consistency between abil usage (if abil not used, then set adren to be previous adren)

            b = model.NewBoolVar("")
            model.Add(self.abils_used[i] == 0).OnlyEnforceIf(b)
            model.Add(self.abils_used[i] == 1).OnlyEnforceIf(b.Not())
            model.Add(self.adren[i] == self.adren[i - 1]).OnlyEnforceIf(b)

        model.Maximize(
            sum(
                self.x[i, j] * self.damages[j]
                for i in range(self.TIME)
                for j in range(self.NUM_ABILITIES)
            )
        )

    def solve(self):
        output = []
        solver.Solve(model)
        for i in range(self.TIME):
            for j in range(self.NUM_ABILITIES):
                if solver.Value(self.x[i, j]) == 1:
                    output.append((i, self.names[j]))

        print(solver.ResponseStats)
        print(output)


s = AbilitySolver(10.8, 100)

s.init_variables()
s.add_constraints()
s.solve()
