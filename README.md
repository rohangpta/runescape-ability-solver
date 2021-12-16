# RuneScape Ability Solver

A program to optimize combat damage for a given timeframe on the video game RuneScape 3. Uses constraint programming, Google's ortools/CP SAT and an elementary set of constraints to construct a simplified model of RuneScape's combat

## Dependencies

- pandas (Tested with v1.3.4)
- ortools (Tested with v9.1.9490)


## Setup Instructions

Clone the repository, go to main.py and observe the very bottom for a working example (copied below)

```py
s = AbilitySolver(seconds=60, start_adren=100, style="melee")

s.init_variables()
s.add_constraints()
s.solve()
```

Modify the seconds, start adren(aline), and style parameters as desired. Note that style must be one of "magic", "melee", or "ranged".

Ensure that solver timeout and number of threads is set using:

```py
solver.parameters.max_time_in_seconds = 300
solver.parameters.num_search_workers = 8
```

## File Structure

```
final_project
│   README.md
│   main.py   
└───data
│   │   melee_data.csv
│   │   ranged_data.csv
│   │   magic_data.csv
```

`main.py` contains the actual programmatic functionality.

`data/` is a directory that contains all the data files for the different classes. These are formmatted as CSVs with columns for Ability Name, Damage, Duration, Type, and Cooldown.

# Overview and Methods

## Optimising RuneScape Combat


RuneScape's combat system presents a rich set of embedded optimisation problems. In particular, given a set of abilities, we have information about their cooldown, adrenaline usage, durations and damage values. The problem statement is as follows:

>Given some time T, give an ordered set of abilities to use so that total damage is maximised (without violating any constraints).

## Variables

We define variables `x[i, j]` for each ability `j` and timestamp `i` such that `x[i, j] == 1` iff ability j was used at timestamp i.

## Constraints - Adrenaline

The adrenaline constraint is handled using the following structured case logic.

- If the ability used at time `t` is basic, then `adrenaline[t] = adrenaline[t-1] + 9`
- If the ability used at time `t` is threshold, then `adrenaline[t-1] >= 50` must hold and `adrenaline[t] = adrenaline[t-1] - 15`
- If the ability used at time `t` is an ultimate, then `adrenaline[t-1] == 100` and `adrenaline[t] == 0`.

Note the single direction ifs here; we use half-reification for this purpose!

## Constraints - Cooldown

The cooldown constraint is handled as follows.

For each ability `j` with a cooldown `c`, let `cd` be a variable denoting the number of times it was used in the past c seconds. Namely, given our variable definitions above we have that `cd = sum(x[c, j] for c in range(max(i - c + 1, 0), i)))`. We say that if `x[i, j] == 1`, then `cd = 0` (more half-reification). This evaluates to our desired constraint since it ensures that the ability is not on cooldown whenever we use it. 


## Constraints - Duration

Most abilities last for 3 ticks (you can verify this by looking at the `.csv` files). This is because there exists a global cooldown of 3 ticks (1.8 seconds) in the game. The natural conclusion with this information is to discretize time at the granularity of 3 ticks. However, we can't do that without loss of generality because there are some abilities that have a longer duration, which are not all multiples of 3. These abilities are known as `channeled abilities`. 

Therefore, we have a duration constraint on abilities. This simply encodes the enformation that if an ability `j` with duration `d` is used at time `t`, no other ability can be used in the interval `[t+1, t+d]`. Specifically, we define another variable called `abils_used`, which is defined by summing over all abilities (booleans) at a specific timestamp. We then enforce that if `j` is used, then `abils_used` in the interval `[t+1, t+d]` is always 0.

## Constraints - Misc. and Challenges

Some constraints that were not immediately captured by the model that were otherwise 'intuitive' to us as players:

- You can only use one ability at every timestamp (`abils_used <= 1` for all `t`). 
- During Global Cooldown/Ability Durations, adrenaline is consistent. Namely, if adrenaline is `x` at time `t-1` and no ability is used at time `t-1` (usually during global cooldown or duration of ability), then adrenaline at time `t` must also be `x`. Without this constraint, we observed weird behaviour from the model where it would 'give itself' 100 adrenaline between abilities since technically, no constraints were violated.
>  This constraint arises because of our tick-level granularity as opposed to ability-level. Since the minimum gap between abilities is 3 ticks, it is the case that most 'ticks' are actually empty -- the model attempted to capitalize on this emptiness and give itself free adrenaline to use!
- Odd behaviour with variable bounds: while we define our adrenaline variables at each time (`adrenaline[i]`) to have a range of [0, 100], it is the case that if you use a basic ability with > 91 adrenaline then technically you go 'over the limit'. For whatever reason, CP solver does not treat this as 100 adrenaline -- we observed odd model behaviour. To solve this, we define variables `adren_cap[i]` which were true iff `adrenaline[i] >= 91`. In this case, (if our model chose to use a basic ability), we would simply hardcode the next adrenaline to 100. Otherwise, we set `adrenaline[i] = adrenaline[i-1] + 9`. Therefore our basic ability logic half-reifies differentially, conditioning on two boolean variables.
- Behaviour with ultimate abilities. As discussed in presentation, ultimate abilities are too powerful not to use when available. However, they present 'non-linear' constraints that cannot be easily encoded in CP-model. We attempted to encode the 20-second damage boost in CP model, but turns out it's fundamentally quadratic so CP-model errored out on us. Therefore, we had two solutions to ensure Ultimate abilities get the treatment they deserve. First, we give them an absurdly high damage value. This makes it almost always better to use an Ultimate ability in a rotation -- if you can afford to. In addition, we add a sufficient constraint on 100 adrenaline to use an ultimate ability. Specifically, we say that if `adren[i] == 100` then "Use available ultimate ability". 

> Until now, we have only been using constraints in their most literal form -- as 'necessary' requirements for execution of a model. This is reflected in our single half-reification for most constraints. However, in the case of ultimate abilities, we found that it was better to just fully reify since in this case, the greedy decision to use an ultimate ability when available often turned out to be best.


Authors: Nathaniel Lao and Rohan Gupta
