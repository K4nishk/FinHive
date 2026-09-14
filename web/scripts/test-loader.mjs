// Node's built-in test runner (`node --test`) has no TS/JSX transform or bundler
// resolution of its own. `esbuild` is already present as vite's transitive
// dependency, so this loader reuses it instead of adding a new devDependency the
// sandbox couldn't `npm install` (no registry access). If `npm ci` ever stops
// hoisting esbuild to the top level, add it explicitly to devDependencies (and
// regenerate package-lock.json).
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import esbuild from "esbuild";

const EXTENSIONS = [".tsx", ".ts"];

// Source files import extensionless ("./RoleGate"), matching tsconfig's "bundler"
// moduleResolution. Node's ESM resolver requires an explicit extension, so resolve
// it here the same way Vite would.
export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith(".") && !path.extname(specifier) && context.parentURL) {
    const baseDir = path.dirname(fileURLToPath(context.parentURL));
    for (const ext of EXTENSIONS) {
      const candidate = path.join(baseDir, specifier + ext);
      if (existsSync(candidate)) {
        return { url: pathToFileURL(candidate).href, shortCircuit: true };
      }
    }
  }
  return nextResolve(specifier, context);
}

export async function load(url, context, nextLoad) {
  if (url.endsWith(".tsx") || url.endsWith(".ts")) {
    const filePath = fileURLToPath(url);
    const source = await readFile(filePath, "utf8");
    const { code } = esbuild.transformSync(source, {
      loader: url.endsWith(".tsx") ? "tsx" : "ts",
      format: "esm",
      jsx: "automatic",
      jsxImportSource: "react",
      sourcefile: filePath,
    });
    return { format: "module", source: code, shortCircuit: true };
  }
  return nextLoad(url, context);
}
