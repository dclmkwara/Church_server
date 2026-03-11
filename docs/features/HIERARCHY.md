# Hierarchy System

## Levels
1. Nation
2. State
3. Region
4. Group
5. Location
6. Fellowship

## What Each Level Represents
- **Nation**: Country-level org.
- **State**: Administrative region under a nation.
- **Region**: Cluster of groups.
- **Group**: Cluster of locations.
- **Location**: Local church.
- **Fellowship**: Small group under a location.

## ltree Paths
A path encodes the full hierarchy (e.g., `org.234.kw.iln.ile.001`).
All scoped queries use `path <@ :scope_path` to enforce row-level access.

## Hierarchy Control
- Parent must exist before creating child.
- Child path is derived from parent.
- Updates validate scope and parent linkage.
