# Expected Changes for Multi-file Refactoring Task

Rename: `calculate_total_price` -> `compute_order_total`

## Locations that must change

### utils.py
| Line | Type | Before | After |
|------|------|--------|-------|
| 6 | Function definition | `def calculate_total_price(` | `def compute_order_total(` |
| 28 | String in list | `"calculate_total_price"` | `"compute_order_total"` |

### orders.py
| Line | Type | Before | After |
|------|------|--------|-------|
| 3 | Import | `from utils import calculate_total_price` | `from utils import compute_order_total` |
| 17 | Docstring reference | `calculate_total_price` | `compute_order_total` |
| 19 | Function call | `calculate_total_price(self.items)` | `compute_order_total(self.items)` |
| 23 | Comment reference | `# calculate_total_price handles` | `# compute_order_total handles` |
| 24 | Function call | `calculate_total_price(self.items)` | `compute_order_total(self.items)` |

### reports.py
| Line | Type | Before | After |
|------|------|--------|-------|
| 3 | Import | `from utils import calculate_total_price` | `from utils import compute_order_total` |
| 9 | Docstring reference | `calculate_total_price` | `compute_order_total` |
| 22 | Function call | `calculate_total_price(order["items"])` | `compute_order_total(order["items"])` |
| 36 | Function call | `calculate_total_price(o["items"])` | `compute_order_total(o["items"])` |

### api.py
| Line | Type | Before | After |
|------|------|--------|-------|
| 5 | Import | `from utils import calculate_total_price` | `from utils import compute_order_total` |
| 19 | Comment reference | `# Delegate to calculate_total_price` | `# Delegate to compute_order_total` |
| 20 | Function call | `calculate_total_price(items)` | `compute_order_total(items)` |
| 36 | Function call | `calculate_total_price(order["items"])` | `compute_order_total(order["items"])` |

## Edge cases present

- **String literal** in `utils.py` `EXPORTED_FUNCTIONS` list references the function name
- **Docstring references** in `orders.py` and `reports.py` mention the function by name
- **Inline comments** in `orders.py` and `api.py` reference the function name
- All four files must be valid Python after the refactoring
