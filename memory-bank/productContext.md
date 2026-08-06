# Product Context

The package gives plugin authors a distributable way to deliver a curated
Codex local marketplace. Installing and running one command should make the
package's plugins available without asking users to copy catalog JSON or plugin
directories themselves.

The user outcome is a repeatable, safe update path: existing content in the
same marketplace is preserved unless the package explicitly owns the plugin
entry being updated, and unrelated marketplaces are not touched.
