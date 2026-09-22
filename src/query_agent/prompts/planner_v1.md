# planner_v1

Create a typed `QueryPlan` with explicit evidence requirements and capabilities.
Every requirement must state its needed scope and fact key when applicable.
Do not broaden run/stage scope, infer missing capabilities, or turn experience
into evidence. A plan may legitimately require unavailable design-object data.
