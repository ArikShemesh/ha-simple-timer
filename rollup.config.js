import commonjs from "@rollup/plugin-commonjs";
import json from "@rollup/plugin-json";
import nodeResolve from "@rollup/plugin-node-resolve";
import terser from '@rollup/plugin-terser';
import typescript from "@rollup/plugin-typescript";
import serve from "rollup-plugin-serve";


const isProduction = process.env.NODE_ENV === 'production';
const dev = process.env.ROLLUP_WATCH;

const serveOptions = {
  contentBase: ["./dist"],
  host: "0.0.0.0",
  port: 4000,
  allowCrossOrigin: true,
  headers: {
    "Access-Control-Allow-Origin": "*",
  },
};

export default [
  {
    input: "src/timer-card.ts",
    output: {
      file: 'dist/timer-card.js',
      format: "es",
      inlineDynamicImports: true,
      sourcemap: !isProduction,
    },
    plugins: [
      typescript({
        declaration: false
      }),
      nodeResolve(),
      json(),
      commonjs(),
      ...(dev ? [serve(serveOptions)] : [terser()]),
    ]
  },
];