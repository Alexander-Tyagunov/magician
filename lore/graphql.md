Common AI mistakes: N+1 queries without DataLoader; missing nullable handling (all fields can be null); over-fetching by not using fragments; forgetting to handle loading and error states.
Commands: codegen: `npm run codegen` (if graphql-codegen configured).
Gotchas: GraphQL errors can return HTTP 200 — always check `data.errors`; fragments prevent duplication across queries.
