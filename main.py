import pandas as pd
from ortools.sat.python import cp_model


model = cp_model.CpModel()
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 300
# solver.parameters.num_search_workers = 1


class AbilitySolver:
    def __init__(self, seconds=10, start_adren=100, style="melee"):
        style_ = style.lower()

        if style_ not in ["magic", "melee", "ranged"]:
            raise ValueError("Style must be one of magic, melee, or ranged")

        if not isinstance(start_adren, int) or start_adren > 100 or start_adren < 0:
            raise ValueError("Please enter an integer in the range [0, 100]")

        if not isinstance(seconds, int) or seconds <= 0:
            raise ValueError("Please enter a positive integer")

        self.df = pd.read_csv(f"./data/{style_}_data.csv")
        self.NUM_ABILITIES = self.df.shape[0]
        self.TIME = int(seconds / 0.6) + 1
        self.START_ADREN = start_adren
        self.x, self.damages, self.names = {}, {}, {}
        self.abils_used = [None for _ in range(self.TIME)]
        self.adren = []
        self.adren_cap = [None for _ in range(self.TIME)]

    def init_variables(self):
        """
        Initialize Variables
        """
        self.adren = [
            model.NewIntVar(0, 100, f"Adren at time {t}") for t in range(self.TIME)
        ] + [model.NewConstant(self.START_ADREN)]

        for i in range(self.TIME):
            for j, row in self.df.iterrows():
                self.x[i, j] = model.NewBoolVar(row["Ability Name"])
                if row["Type"] == "Ultimate":
                    self.ULTIMATE_DAMAGE = row["Damage"]
                self.damages[j] = row["Damage"]
                self.names[j] = row["Ability Name"]
        for i in range(self.TIME):
            self.abils_used[i] = model.NewIntVar(0, self.NUM_ABILITIES, "")
            model.Add(
                self.abils_used[i]
                == sum(self.x[i, j] for j in range(self.NUM_ABILITIES))
            )
            self.adren_cap[i] = model.NewBoolVar("")
            model.Add(self.adren[i - 1] >= 91).OnlyEnforceIf(self.adren_cap[i])
            model.Add(self.adren[i - 1] < 91).OnlyEnforceIf(self.adren_cap[i].Not())

        self.damage_boost = [model.NewIntVar(1, 3, "") for _ in range(self.TIME)]
        self.abil_damage = [
            model.NewIntVar(0, self.ULTIMATE_DAMAGE, "") for _ in range(self.TIME)
        ]

        self.damage_sum = model.NewIntVar(
            0, self.TIME * self.ULTIMATE_DAMAGE * 2, "Sum of Damage"
        )

        self.total_damage = [
            model.NewIntVar(0, self.ULTIMATE_DAMAGE * 2, "") for _ in range(self.TIME)
        ]

    def add_constraints(self):
        """
        Add constraints to the CP Model
        """
        for i in range(self.TIME):
            for j, row in self.df.iterrows():
                dur = row["Duration"]

                # Variables x_ij if ability j was used at timestamp i

                # If abil is used, can't use any others for its duration
                for d in range(i + 1, min(i + dur, self.TIME)):
                    model.Add(self.abils_used[d] == 0).OnlyEnforceIf(self.x[i, j])

                c = row["Cooldown"]

                # Ability used only as often as cooldown
                cd = model.NewIntVar(0, self.NUM_ABILITIES, "cd")
                model.Add(cd == sum(self.x[c, j] for c in range(max(i - c + 1, 0), i)))
                model.Add(cd == 0).OnlyEnforceIf(self.x[i, j])

                # Define adren variation depending on the type of ability
                type = row["Type"]

                if type == "Basic":
                    model.Add(self.adren[i] == 100).OnlyEnforceIf(
                        [self.x[i, j], self.adren_cap[i]]
                    )
                    model.Add(self.adren[i] == self.adren[i - 1] + 9).OnlyEnforceIf(
                        [self.x[i, j], self.adren_cap[i].Not()]
                    )

                elif type == "Threshold":
                    model.Add(self.adren[i] == self.adren[i - 1] - 15).OnlyEnforceIf(
                        self.x[i, j]
                    )
                    model.Add(self.adren[i - 1] >= 50).OnlyEnforceIf(self.x[i, j])

                elif type == "Ultimate":
                    model.Add(self.adren[i - 1] == 90).OnlyEnforceIf(self.x[i, j])
                    model.Add(self.adren[i - 1] < 100).OnlyEnforceIf(self.x[i, j].Not())

                    for k in range(i, min(i + 20, self.TIME)):
                        model.Add(self.damage_boost[k] == 2).OnlyEnforceIf(self.x[i, j])

                    model.Add(self.adren[i] == 10).OnlyEnforceIf(self.x[i, j])

        for i in range(self.TIME):
            model.Add(
                self.abil_damage[i]
                == sum(
                    self.x[i, j] * self.damages[j] for j in range(self.NUM_ABILITIES)
                )
            )

        for i in range(self.TIME):
            # Ensure at most 1 ability used at any time
            model.Add(self.abils_used[i] <= 1)

            # Ensure adren consistency between abil usage (if abil not used, then set adren to be previous adren)

            b = model.NewBoolVar("")
            model.Add(self.abils_used[i] == 0).OnlyEnforceIf(b)
            model.Add(self.abils_used[i] == 1).OnlyEnforceIf(b.Not())
            model.Add(self.adren[i] == self.adren[i - 1]).OnlyEnforceIf(b)

        for i in range(self.TIME):
            model.AddMultiplicationEquality(
                self.total_damage[i], [self.abil_damage[i], self.damage_boost[i]]
            )

        model.Add(
            self.damage_sum == sum(self.total_damage[i] for i in range(self.TIME))
        )
        model.Maximize(self.damage_sum)

    def solve(self):
        output = []
        status = solver.Solve(model)
        if status != cp_model.INFEASIBLE:
            for i in range(self.TIME):
                for j in range(self.NUM_ABILITIES):
                    if solver.Value(self.x[i, j]) == 1:
                        output.append([i, solver.Value(self.adren[i]), self.names[j]])

        for i in range(self.TIME):
            print(solver.Value(self.damage_boost[i]))
        else:
            print(solver.SufficientAssumptionsForInfeasibility())

        df = pd.DataFrame(output, columns=["Tick", "Adrenaline", "Ability Name"])
        print(df)
        print(solver.ResponseStats())


s = AbilitySolver(seconds=20, start_adren=100, style="melee")

s.init_variables()
s.add_constraints()
s.solve()
