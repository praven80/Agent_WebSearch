/// <reference types="vite/client" />

// Vite's client types, referenced from a source file rather than through the
// compilerOptions "types" array.
//
// A bad entry in "types" surfaces as an error on tsconfig.json itself (TS2688),
// which is confusing and easy to hit when the editor indexes the project before
// node_modules exists. A triple-slash reference resolves relative to this file, so
// it behaves the same for the compiler and for the editor.
//
// This is also what `npm create vite` scaffolds.
