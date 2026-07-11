# Artifacts — dossier & parity contract

The two durable artifacts `/transmute` produces. Both are XML-tagged so every downstream worker can
parse them and so the frozen dossier is a stable, cacheable prefix. Both live under the **existing**
`.workspace/shared/research/` directory — a dossier *is* comprehension research, so `/magic`,
`/conjure`, and `/weave` already know the path (no new wiring). Hand them downstream **by path only**.

**Tags on every finding:** confidence — `[C:HIGH]` triangulated (≥2 sources) · `[C:MED]` one strong
source · `[C:LOW]` single black-box/inferred. Source — `[S:live] [S:code] [S:doc] [S:network] [S:user]`.

---

## Dossier — `.workspace/shared/research/<feature>-<date>.md`

```xml
<dossier feature="…" source="…" mode="port|integrate|audit" tier="A|B|C|D"
         target_app="…" inputs="[url?,code?,docs?,none]" overall_confidence="…">
  <summary/>                                <!-- what it does, for whom, why it exists -->
  <sources>                                 <!-- what it's built from (record, never exfiltrate) -->
    <framework/> <versions/> <bundles/> <source_maps_present/> <client_config_flags/>
  </sources>
  <behavior_contract>                       <!-- the "what" — PORTABLE -->
    <triggers/> <state_machine/> <business_rules/> <outputs/>
    <events/>                               <!-- UI event → behavior → network-call map; custom events; debounce -->
  </behavior_contract>
  <io_contract>                             <!-- the interfaces -->
    <inbound/>                              <!-- params, types, validation -->
    <outbound><endpoint/><method/><request/><response/><auth/><pagination/><errors/></outbound>
    <data_model/>                           <!-- link an OpenAPI / GraphQL SDL if one exists -->
    <feature_flags/> <config/>
  </io_contract>
  <ux_contract><screens/><interactions/><copy/><states/><perceived_latency/></ux_contract>
  <vendor>
    <identified evidence="host|sdk|headers"/> <version_in_use/> <latest_available/>
    <auth_keys_limits/> <cost_model/> <upgrade_opportunity risk="…"/>
  </vendor>
  <non_functional>
    <perf p50="" p95="" payloads="" fanout=""/> <cost/> <a11y/> <reliability/> <security_privacy/>
  </non_functional>
  <edge_cases/>                             <!-- observed input → observed output -->
  <parity_baseline behavioral=".../<f>-golden/behavioral/"
                   environmental=".../<f>-golden/environmental/" masked_fields="…"/>
  <unknowns/>                               <!-- → AskUserQuestion candidates; every [C:LOW] lands here -->
  <change_plan_seed>
    <!-- PORT: what to recreate + upgrade opportunity + target seams -->
    <!-- INTEGRATE: the seam to change + the contract to preserve + kg blast radius -->
    <weave_shape/> <gates/>
  </change_plan_seed>
</dossier>
```

Fill only what the tier supports; leave the rest empty and list the gaps in `<unknowns>`. Do not
invent values — an empty, honestly-tagged field beats a confident guess.

---

## Parity contract — `.workspace/shared/research/<feature>-parity.md`

Authored in Phase B, approved by the user before any code (SKILL.md HARD-GATE #2).

```xml
<parity_contract mode="port|integrate" feature="…">
  <behavioral_parity>
    <!-- golden inputs → expected output SEMANTICS. PORTABLE. Points at the behavioral/ fixtures.
         This is exactly what the /weave evaluator loop diffs a candidate against. -->
  </behavioral_parity>
  <environmental_baseline scope="source-only">
    <!-- domain / concrete IDs / styling that MUST differ in the target. NOT asserted on a port. -->
  </environmental_baseline>
  <ux_invariants>
    <!-- what MUST NOT change for the user (vendor swap: UX identical; redesign: behavior identical) -->
  </ux_invariants>
  <gateways>
    <perf budget="p95 ≤ …, payload ≤ …"/> <cost budget="≤ … per call × … volume"/>
    <security/> <a11y budget="WCAG … unchanged-or-better"/>
  </gateways>
  <upgrade_decision>
    <!-- swap X→Y | keep current | upgrade version N→M  + migration notes / breaking changes -->
  </upgrade_decision>
  <boundary>
    <!-- INTEGRATE: anti-corruption-layer / strangler-facade seam. PORT: target-app insertion seam. -->
  </boundary>
  <rollback>
    <!-- feature-flag name · old path retained · concrete revert steps · kill-switch -->
  </rollback>
</parity_contract>
```

### Why behavioral vs environmental is load-bearing
For an **INTEGRATE** vendor swap in the same app, the golden-from-source *is* the target — behavioral
and environmental both apply. For a **PORT** into another app, the environment differs by design
(domain, data, IDs, styling); if the evaluator diffed those it would fail parity forever. So the
evaluator loop asserts **behavioral parity only**; environmental captures are kept for reference and
never asserted against the port. State this split explicitly in the contract so the loop converges.
