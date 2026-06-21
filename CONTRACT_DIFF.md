# CONTRACT_DIFF.md

| Test | Previous Contract | Current Behavior | Verdict | Action |
| --- | --- | --- | --- | --- |
| `test_base_adapter_contract` | `submit_order` accepts `ExecutionIntent` | `BaseExchangeAdapter.submit_order` accepts `ExchangeOrder` | INTENTIONAL_CONTRACT_CHANGE | Update `BaseExchangeAdapter.submit_order` signature to accept `ExecutionIntent \| ExchangeOrder`. |
| `test_execution_adapter_contract` | `submit_order` returns `ExecutionResult` | `PaperExchangeAdapter.submit_order` returns `Fill` (model) and has no return type hint | IMPLEMENTATION_REGRESSION | Update `PaperExchangeAdapter.submit_order` to return `ExecutionResult` and add type hint. |
