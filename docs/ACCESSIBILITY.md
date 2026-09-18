# Accessibility contract

S-06.02.05 makes keyboard and screen-reader access a product boundary, not a
manual polish pass.

## What the shipped UI promises

- Every user action has a keyboard path. Native buttons, links, inputs, selects
  and textareas are preferred over custom click targets.
- Keyboard focus is visible. Route changes move focus to the newly named main
  content region.
- Shared dialogs move focus inside, keep Tab/Shift+Tab inside, close on Escape
  and return focus to the opener.
- Loading, errors, progress and notifications expose status/alert semantics
  instead of relying on colour or animation.
- Images declare whether they are meaningful or decorative.
- Users who request reduced motion do not get non-essential transitions,
  animation or smooth scrolling.
- Hidden drawers are removed from keyboard and assistive-technology navigation.
- Pointer-only editing must have a keyboard equivalent that calls the same
  validated domain operation. The video timeline follows this rule.

## Video timeline keyboard controls

Focus a timeline clip with Tab.

- Left / Right: move one frame.
- Shift + Left / Right: move ten frames.
- Alt + Left / Right: trim the start.
- Ctrl/Command + Left / Right: trim the end.
- Enter or Space: select the clip.
- S: split the selected clip at the playhead.
- Delete / Backspace: remove the selected clip.
- Shift + Delete / Backspace: ripple-delete it.

The keyboard path calls the same `move_clip` and `trim_clip` operations as
pointer dragging. There is no second accessibility-only timeline state.

## Regression gates

Focused frontend evidence:

```bash
npm test --prefix frontend -- src/accessibility.test.tsx src/accessibility-source.test.ts
```

The behavioural suite covers shared dialog/focus/progress semantics and video
keyboard-operation mapping. The source gate recursively audits every shipped
React source file, so a new page is included automatically.

Full frontend evidence:

```bash
npm test --prefix frontend
npm run build --prefix frontend
```

The source gate catches obvious regressions such as clickable non-native
elements, unnamed images, custom tab stops without keyboard semantics,
literal icon-only unnamed controls and focusable controls hidden from assistive
technology.

## What this does not claim

This repository evidence is not an external WCAG certification. Browser,
screen-reader and assistive-technology combinations still need independent
acceptance testing before claiming a formal conformance level.
