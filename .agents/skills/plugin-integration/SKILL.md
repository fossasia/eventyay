---
name: plugin-integration
description: Trace and change Eventyay core contracts shared with the Business and Stripe plugin repositories, including local integration setup and coordinated PR validation.
---

# Plugin integration

Read [the repository map](../../context/plugin-ecosystem.md) to identify the owner
of the behavior, then [setup and delivery](../../context/development-and-delivery.md)
when installing, testing, or preparing a release. Follow root `agents.md` and the
matching `.github/instructions/` rules.

1. Confirm Git roots, branches, and installed module paths before editing. A
   plugin directory and the package currently imported by Python may differ.
2. Trace the relevant shared signal/API and its plugin receiver. Check behavior
   with no receiver and with duplicate/failed delivery where relevant.
3. Keep core contracts in core and commercial/payment implementations in their
   owning repository. Preserve compatible entry-point names and webhook aliases.
4. Test the changed contract in core and affected consumers in their repository.
   Use [the review guide](references/contract-review.md) for fee/billing changes.
5. Prepare separate PRs against `dev`, recording revisions and compatibility.
   Use [the handoff template](assets/integration-pr.md); coordinate lock updates
   only when a released code change needs them.
