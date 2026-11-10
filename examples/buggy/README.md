# Buggy example

`total_with_discount(100, 0.2)` returns 80 in the test, but the implementation
subtracts the discount fraction instead of applying it to the price.

Try the agent on it:

```bash
mini-harness run "почему падает тест total_with_discount" --root examples/buggy
```
