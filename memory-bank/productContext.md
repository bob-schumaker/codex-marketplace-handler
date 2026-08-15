# Product Context

`marketplace-installer` lets plugin-producing projects use one tested library
to create and assemble v3 router-plugin marketplaces. The same library supports
the current direct operational workflow and the future Copier-generated
publisher package; these are delivery paths for one installer contract, not
separate implementations.

The user outcome is a repeatable, safe path from plugin source to a validated
local marketplace. Direct users publish a validated generated plugin through
the established merge workflow. A Copier-rendered publisher instead embeds a
canonical assembly tree in a distributable wheel. Generated-payload packaging
avoids requiring a pre-existing local marketplace as build input.
