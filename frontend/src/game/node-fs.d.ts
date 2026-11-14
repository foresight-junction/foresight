// The two node:fs calls the tests use; the viewer has no @types/node and adds no dependency for tests.
declare module "node:fs" {
  export function readFileSync(path: string | URL, encoding: "utf-8"): string;
  export function existsSync(path: string | URL): boolean;
}
