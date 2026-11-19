# Browser platform declarations

S-03.02.05 uses `offsetx_apollo_builder/browser/platforms.yaml`, included in wheels.
Set `OFFSETX_BROWSER_PLATFORMS` to an owner-controlled YAML file to replace the
registry. Runtime lookups read it afresh; all rows validate before any is used.
Keep the built-in rows in an override when their policies must remain active.
Removing a row removes its platform-specific policy; open-web policy still applies.

Each platform needs `id`, `label`, HTTPS `login_url` and `home_url`, nonempty
`signed_in` and `signed_out` lists, explicit `domains`, finite nonnegative
`min_seconds_between_actions`, boolean `unattended`, and positive integer
`actions_per_hour` and `actions_per_day`. Optional: `note`, `refuse`, `confirm`.
Signals match accessible names case-insensitively on word boundaries. Signed-out
signals win ties. Login URLs may belong to an external identity provider; the
home URL must belong to the declared domains. Credentials in URLs, local hosts,
duplicate IDs/domains, missing and unknown fields are rejected.

Pace, domain rules and budget lookups use this same declaration. Most-specific
domain rules win. Subdomains inherit; suffix lookalikes do not. Unknown platforms
still get a bounded default budget, and sensitive actions still require approval.
The imported PLATFORMS, RULES and DEFAULT_BUDGETS names remain startup snapshots
for compatibility; use public runtime lookups for current declarations.

No stored state migration is required. Existing connection and account IDs remain
unchanged. Roll back by unsetting the override or restoring the previous YAML;
connection records survive registry removal and reappearance. The integration
test exercises that lifecycle without a real platform or provider.
