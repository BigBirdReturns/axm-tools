/*
 * This file records the selector defect found by the first local field-composition campaign.
 * The original candidate used broad [data-mode], [data-seat], and [data-zone] selectors even
 * though the body also carries those state attributes. The repaired candidate must scope all
 * control discovery, pressed-state mutation, and event binding to button[data-*] selectors.
 *
 * It is retained as an explicit defect receipt rather than silently relabeling the first
 * candidate as qualified.
 */
window.__FIELD_COMPOSITION_SELECTOR_REPAIR__ = Object.freeze({
  schema: "manzanita/useful-plant-v30-field-selector-repair@1",
  defect: "body state attributes collided with broad control selectors",
  required_control_selectors: {
    mode: "button[data-mode]",
    seat: "button[data-seat]",
    zone: "button[data-zone]",
    stop: "button[data-stop]"
  },
  first_candidate_qualified: false,
  operator_visual_acceptance: "ABSENT",
  merge_authorized: false,
  release_authorized: false,
  public_route_effect: "none",
  pages_deployment_effect: "none",
  external_effect: "none"
});
